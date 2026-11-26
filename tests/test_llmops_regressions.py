"""Pruebas de regresión MLOps/LLMOps: retrieval híbrido, router, RBAC y geolocalización estricta."""

from __future__ import annotations

import pytest

from emcali_corpus.assistant import load_assistant_settings
from emcali_corpus.ops_db import EmcaliOpsDatabase
from emcali_corpus.retrieval_eval import evaluate_retrieval_mode
from emcali_corpus.router import route_query_with_jev
from emcali_corpus.tools_m3 import execute_tool_with_rbac
from emcali_corpus.vector_store import EmcaliQdrantVectorStore


def test_retrieval_hybrid_regression_gate() -> None:
    """Garantiza umbrales mínimos de Recall@10 y nDCG@10 en CI sin costo de LLM."""
    store = EmcaliQdrantVectorStore(in_memory=True)
    report = evaluate_retrieval_mode(store, search_mode="hybrid")
    assert report["recall_at_10"] >= 0.90, f"Recall@10 cayó a {report['recall_at_10']:.3f}"
    assert report["ndcg_at_10"] >= 0.75, f"nDCG@10 cayó a {report['ndcg_at_10']:.3f}"


@pytest.mark.parametrize(
    ("query", "expected_choice"),
    [
        ("reportes de fallo en Nueva Tequendama", "m3_ops_tool"),
        ("¿Qué reportes de falla hay en El Ingenio?", "m3_ops_tool"),
        ("¿Quién es el gerente de EMCALI?", "rag_search"),
        ("¿Cuál es la tarifa de energía en estrato 3 en el tercer trimestre?", "structured_tool"),
        ("Calcula la derivada de arctan(x) en Python", "direct_reply"),
    ],
)
def test_router_regression_matrix(query: str, expected_choice: str) -> None:
    """Verifica estabilidad del enrutamiento System One (Jev) ante frases clave y off-topic."""
    decision = route_query_with_jev(query)
    assert decision.choice == expected_choice, (
        f"Query={query!r} enrutó a {decision.choice!r} (esperado {expected_choice!r})"
    )


def test_rbac_phone_normalization_and_manager_deny(tmp_path) -> None:
    """Valida normalización E.164 con espacios y bloqueo tools.deny para ciudadanos."""
    db = EmcaliOpsDatabase(db_path=tmp_path / "ops_test.sqlite")
    db.upsert_user_rbac(
        username="ops_mgr",
        display_name="Ops Manager",
        role="manager",
        password="secret-password-2026",
        phone_e164="+573222132215",
        department="Operaciones",
        active=True,
    )
    assert db.resolve_role_by_phone("+57 322 213 2215") == "manager"
    assert db.resolve_role_by_phone("+573222132215@s.whatsapp.net") == "manager"
    assert db.resolve_role_by_phone("+573009998877") == "citizen"

    denied = execute_tool_with_rbac(
        "generar_resumen_ejecutivo_operaciones",
        {},
        role="citizen",
    )
    assert denied["ok"] is False
    assert denied["error"] == "RBAC_DENIED"


def test_invalid_barrio_rejected_in_failure_report() -> None:
    """Verifica que barrios inexistentes (ej. Manhattan) sean rechazados sin inventar comuna."""
    res = execute_tool_with_rbac(
        "reportar_falla_servicio",
        {
            "servicio": "energia",
            "identificador_tipo": "contrato",
            "identificador_valor": "1234567",
            "nombre_ciudadano": "Prueba QA",
            "barrio": "Manhattan",
            "descripcion": "Sin energía en el sector",
        },
        role="citizen",
    )
    assert res["ok"] is False
    assert "Manhattan" in str(res.get("message", ""))


def test_assistant_settings_reads_deepseek_model_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que DEEPSEEK_MODEL del entorno sea respetado por load_assistant_settings."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    settings = load_assistant_settings()
    assert settings.model == "deepseek-v4-flash"


def test_jev_news_gatekeeper_blocks_positive_press_releases_from_map() -> None:
    """Verifica que Jev Noul vete noticias positivas y solo permita mantenimientos reales."""
    from emcali_corpus.news_sync import classify_news_event_with_jev

    good_news = classify_news_event_with_jev(
        "AUNQUE EL VERANO ES FUERTE, EL SISTEMA DE ACUEDUCTO FUNCIONA CON NORMALIDAD",
        "A pesar de la fuerte temporada de calor que afronta la ciudad, el acueducto opera bien.",
    )
    assert good_news.choice == "institutional_news"
    assert good_news.noul_triggered is True

    cartera = classify_news_event_with_jev(
        "Este viernes 27 de noviembre EMCALI realiza jornada especial de alivios "
        "y acuerdos de pago",
        "Acércate a nuestros puntos de atención para normalizar tu factura.",
    )
    assert cartera.choice == "institutional_news"
    assert cartera.noul_triggered is True

    real_maint = classify_news_event_with_jev(
        "Reparaciones y mantenimientos — Jueves 26 de noviembre de 2026",
        "EMCALI realizará suspensión temporal del servicio de acueducto en San Fernando.",
    )
    assert real_maint.choice == "operational_maintenance_pin"
    assert real_maint.noul_triggered is False
    assert real_maint.score >= 0.55
