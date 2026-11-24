"""Pruebas del Módulo 3: 20 herramientas, RBAC, HITL, PQRS, Fallas/Hotspots y Noticias."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from emcali_corpus import ops_db as ops_db_module
from emcali_corpus.api import create_fastapi_app
from emcali_corpus.cali_geo import detect_barrios_in_text, resolve_cali_location
from emcali_corpus.news_sync import build_daily_newsletter_digest, sync_news_from_gold
from emcali_corpus.ops_db import (
    EmcaliOpsDatabase,
    FailureReportCreateRequest,
    PqrsCreateRequest,
)
from emcali_corpus.tools_m3 import (
    ALL_20_TOOLS,
    CITIZEN_TOOLS,
    MANAGER_ONLY_TOOL_NAMES,
    describe_tool_catalog,
    execute_tool_with_rbac,
)


@pytest.fixture
def isolated_ops_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EmcaliOpsDatabase:
    db = EmcaliOpsDatabase(tmp_path / "test_ops.sqlite")
    monkeypatch.setattr(ops_db_module, "_OPS_DB_SINGLETON", db)
    return db


def test_exactly_20_typed_tools_registered() -> None:
    assert len(ALL_20_TOOLS) == 20
    assert len(CITIZEN_TOOLS) == 16
    assert len(MANAGER_ONLY_TOOL_NAMES) == 4
    catalog = describe_tool_catalog()
    assert len(catalog) == 20
    for item in catalog:
        assert item["name"]
        assert item["description"]
        assert isinstance(item["parameters_schema"], dict)


def test_cali_geolocation_and_barrio_detection() -> None:
    loc = resolve_cali_location("San Fernando")
    assert loc.barrio == "San Fernando"
    assert loc.comuna == "Comuna 19"
    assert 3.3 < loc.lat < 3.6

    detected = detect_barrios_in_text(
        "Mantenimiento de acueducto en Ciudad Jardín y La Flora hoy en Cali."
    )
    names = {d.barrio for d in detected}
    assert "Ciudad Jardín" in names
    assert "La Flora" in names


def test_pqrs_contract_and_non_client_cedula(isolated_ops_db: EmcaliOpsDatabase) -> None:
    t_client = isolated_ops_db.create_pqrs(
        PqrsCreateRequest(
            tipo="Reclamo",
            servicio="energia",
            identificador_tipo="contrato",
            identificador_valor="12345678",
            nombre_ciudadano="Ana Carvajal",
            barrio="San Fernando",
            descripcion="Cobro inusual en la factura del último periodo.",
        )
    )
    t_non_client = isolated_ops_db.create_pqrs(
        PqrsCreateRequest(
            tipo="Petición",
            servicio="acueducto",
            identificador_tipo="cedula",
            identificador_valor="1144098765",
            nombre_ciudadano="Carlos Gómez",
            barrio="El Ingenio",
            descripcion="Fuga de agua en vía pública frente al parque del Ingenio.",
        )
    )
    assert t_client["radicado_id"].startswith("PQRS-2026-")
    assert t_non_client["identificador_tipo"] == "cedula"
    assert len(isolated_ops_db.list_pqrs(identificador_valor="1144098765")) == 1


def test_failure_hotspot_flagging_and_crew_dispatch(isolated_ops_db: EmcaliOpsDatabase) -> None:
    for idx in range(4):
        isolated_ops_db.create_failure_report(
            FailureReportCreateRequest(
                servicio="acueducto",
                identificador_tipo="cedula",
                identificador_valor=f"100000{idx}",
                barrio="Ciudad Jardín",
                descripcion="Baja presión y suspensión inesperada de agua en el sector.",
            )
        )
    hotspots = isolated_ops_db.get_failure_hotspots(servicio="acueducto")
    cj = next(h for h in hotspots if h["barrio"] == "Ciudad Jardín")
    assert cj["report_count"] == 4
    assert cj["severity"] == "critical_dispatch"
    assert cj["dispatch_recommended"] is True

    maint = isolated_ops_db.dispatch_crew_for_hotspot(
        barrio="Ciudad Jardín",
        servicio="acueducto",
        brigada_asignada="Brigada Sur-09",
    )
    assert maint["linked_failure_reports"] == 4
    assert maint["fuente"] == "promovido_falla"


def test_rbac_denies_citizen_and_allows_manager_with_hitl(
    isolated_ops_db: EmcaliOpsDatabase,
) -> None:
    denied = execute_tool_with_rbac(
        "activar_punto_mantenimiento",
        {
            "titulo": "Corte programado prueba",
            "servicio": "energia",
            "barrio": "Granada",
            "descripcion": "Cambio de transformador en Granada.",
        },
        role="citizen",
    )
    assert denied["ok"] is False
    assert denied["error"] == "RBAC_DENIED"

    queued = execute_tool_with_rbac(
        "activar_punto_mantenimiento",
        {
            "titulo": "Corte programado Granada",
            "servicio": "energia",
            "barrio": "Granada",
            "descripcion": "Cambio de transformador en Granada.",
        },
        role="manager",
        require_hitl=True,
    )
    assert queued["ok"] is True
    assert queued["status"] == "pending_hitl_approval"
    assert queued["hitl_action"]["action_id"].startswith("HITL-")


def test_news_sync_and_daily_newsletter(isolated_ops_db: EmcaliOpsDatabase) -> None:
    stats = sync_news_from_gold(isolated_ops_db, max_maintenance_pins=5)
    assert stats["news_ingested"] > 0
    digest = build_daily_newsletter_digest(isolated_ops_db)
    assert "Boletín Diario EMCALI" in digest["markdown_digest"]


def test_m3_fastapi_endpoints_rbac_and_map(isolated_ops_db: EmcaliOpsDatabase) -> None:
    app = create_fastapi_app()
    client = TestClient(app)

    cat = client.get("/api/tools/catalog")
    assert cat.status_code == 200
    assert cat.json()["total_tools"] == 20

    # Sin login (citizen) -> bloqueado en endpoint manager
    forbidden = client.get("/api/ops/summary")
    assert forbidden.status_code == 403

    # Login manager -> autorizado
    login = client.post(
        "/api/auth/login",
        json={"username": "rommel", "password": "emcali-ops-2026"},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    assert login.json()["role"] == "manager"

    summary = client.get("/api/ops/summary", headers={"Authorization": f"Bearer {token}"})
    assert summary.status_code == 200
    assert summary.json()["active_maintenances"] >= 3

    m_resp = client.get("/api/map/overview")
    assert m_resp.status_code == 200
    assert m_resp.json()["maintenances_count"] >= 3

    # Admin RBAC user creation
    new_u = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "jacobo",
            "display_name": "Jacobo Unzueta (Gestión)",
            "role": "manager",
            "password": "emcali-ops-2026",
            "phone_e164": "+573183775357",
        },
    )
    assert new_u.status_code == 200
    assert new_u.json()["user"]["username"] == "jacobo"

    # Consulta "Quiero radicar una PQR" debe enrutarse a m3_ops_tool y ofrecer contrato o cédula
    pqr_chat = client.post(
        "/api/chat",
        json={"question": "Quiero radicar una PQR", "use_llm": False},
    )
    assert pqr_chat.status_code == 200
    body = pqr_chat.json()
    assert body["router_decision"]["choice"] == "m3_ops_tool"
    assert "contrato" in body["answer"].lower()
    assert "cédula" in body["answer"].lower()

    # Filtro semántico de relevancia de dominio (off-topic bloqueado vía Noul)
    from emcali_corpus.router import compute_domain_relevance_score, route_query_with_jev

    off_score = compute_domain_relevance_score("¿Cuál es la derivada del coseno?")
    on_score = compute_domain_relevance_score(
        "¿Cuál es la tarifa de energía eléctrica de EMCALI en estrato 3?"
    )
    assert on_score > off_score
    off_dec = route_query_with_jev("¿Cuál es la derivada del coseno?")
    assert off_dec.choice == "direct_reply"
    assert off_dec.noul_triggered is True
    assert off_dec.box.is_out_of_scope_or_private is True

    # Validación estricta de barrios de cobertura EMCALI (Manhattan no existe en Cali)
    from emcali_corpus.cali_geo import try_resolve_cali_location
    from emcali_corpus.tools_m3 import consultar_afectacion_por_barrio

    assert try_resolve_cali_location("Manhattan") is None
    res_manhattan = consultar_afectacion_por_barrio.invoke({"barrio": "Manhattan"})
    assert res_manhattan["barrio_valido_emcali"] is False
    assert res_manhattan["error"] == "BARRIO_NO_RECONOCIDO"
    with pytest.raises(ValueError, match="no existe"):
        isolated_ops_db.create_failure_report(
            FailureReportCreateRequest(
                servicio="energia",
                identificador_tipo="cedula",
                identificador_valor="12345678",
                barrio="Manhattan",
                descripcion="Corte de luz en barrio inexistente.",
            )
        )
