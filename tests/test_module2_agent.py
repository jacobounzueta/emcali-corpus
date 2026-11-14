"""Pruebas unitarias y de integración del Módulo 2: Memoria, Tools, Qdrant, Router Jev,
Blindaje, Voz y API."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from emcali_corpus.agent_graph import EmcaliConversationalAgent
from emcali_corpus.api import create_fastapi_app
from emcali_corpus.knowledge import KnowledgeChunk
from emcali_corpus.memory import (
    MemoryManager,
    PersistentSqliteStore,
    SummarizationMiddleware,
    extract_and_persist_user_facts,
    search_user_long_term_memories,
)
from emcali_corpus.retrieval_eval import evaluate_retrieval_mode
from emcali_corpus.router import route_query_with_jev
from emcali_corpus.security import (
    CANARY_INJECTION_CHUNK,
    build_passive_context_block,
    wrap_chunk_as_passive_data,
)
from emcali_corpus.tools import (
    consultar_indicadores_operativos_json,
    consultar_tarifas_emcali_csv,
    query_indicadores_structured,
    query_tarifas_structured,
)
from emcali_corpus.vector_store import EmcaliQdrantVectorStore
from emcali_corpus.voice import (
    build_tts_speech_summary,
    parse_voice_hotword_command,
)


def _sample_chunks() -> list[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            chunk_id="proteccion-de-datos-personales/proteccion-de-datos-personales#c01",
            section="proteccion-de-datos-personales",
            slug="proteccion-de-datos-personales",
            title="Protección de datos personales",
            source_url="https://www.emcali.com.co/proteccion-de-datos-personales",
            heading_path="Protección de datos personales > Ley 1581 de 2012",
            text=(
                "EMCALI E.I.C.E. E.S.P. con NIT 890.399.003-4 y domicilio en el CAM Torre EMCALI "
                "garantiza los derechos de conocer, actualizar y rectificar datos personales según "
                "la Ley 1581 de 2012. Las consultas se responden en máximo 10 días hábiles y los "
                "reclamos en 15 días hábiles. Línea de atención 177 y 602 5240177."
            ),
            word_count=52,
            char_count=340,
        ),
        KnowledgeChunk(
            chunk_id="telco/telco#c01",
            section="telco",
            slug="telco",
            title="Telecomunicaciones EMCALI",
            source_url="https://www.emcali.com.co/telco",
            heading_path="Telco > Fibra Óptica",
            text=(
                "EMCALI Telecomunicaciones cuenta con 92% de cobertura de fibra óptica en Cali, "
                "soporte 24/7, diagnóstico remoto y la Operación Cali sin enredos con 57 mil "
                "metros "
                "de cable desmontado."
            ),
            word_count=33,
            char_count=210,
        ),
        CANARY_INJECTION_CHUNK,
    ]


def test_sqlite_checkpointer_survives_process_restart(tmp_path: Path) -> None:
    """Verifica Criterio 1.1: SqliteSaver persiste el thread_id cuando se recrea el agente."""
    cp_db = tmp_path / "checkpoints.sqlite"
    store_db = tmp_path / "store.sqlite"
    chunks = _sample_chunks()

    # Proceso 1: usuario inicia conversación en hilo-persistente-01
    mem1 = MemoryManager(checkpoints_path=cp_db, store_path=store_db)
    vs1 = EmcaliQdrantVectorStore(in_memory=True, chunks=chunks)
    agent1 = EmcaliConversationalAgent(vector_store=vs1, memory_manager=mem1)
    out1 = agent1.invoke_turn(
        "Hola, me llamo Ana y trabajo en Carvajal.",
        thread_id="hilo-persistente-01",
        user_id="ana-01",
        use_llm=False,
    )
    assert "Ana" in out1.answer
    mem1._sqlite_conn.close()

    # Proceso 2 (simula reinicio de servidor): nuevo MemoryManager sobre el mismo archivo SQLite
    mem2 = MemoryManager(checkpoints_path=cp_db, store_path=store_db)
    vs2 = EmcaliQdrantVectorStore(in_memory=True, chunks=chunks)
    agent2 = EmcaliConversationalAgent(vector_store=vs2, memory_manager=mem2)

    history = mem2.get_thread_history_summary("hilo-persistente-01", agent2.graph)
    assert history["messages_count"] >= 2

    # Además, en un HILO NUEVO ("hilo-nuevo-02"), el Store recupera dónde trabaja Ana (Criterio 1.3)
    out2 = agent2.invoke_turn(
        "¿Dónde trabajo y cómo me llamo?",
        thread_id="hilo-nuevo-02",
        user_id="ana-01",
        use_llm=False,
    )
    assert "Ana" in out2.answer
    assert "Carvajal" in out2.answer


def test_summarization_middleware_and_trim_messages() -> None:
    """Verifica Criterio 1.2: trim_messages + SummarizationMiddleware recortan y resumen turnos."""
    middleware = SummarizationMiddleware(max_tokens=120, summarize_after_messages=4)
    long_conversation = [
        HumanMessage(
            content=f"Turno {i}: consulta extensa sobre servicios públicos de EMCALI en Cali."
        )
        if i % 2 == 0
        else AIMessage(
            content=f"Respuesta {i}: detalle institucional verificado del servicio público."
        )
        for i in range(10)
    ]

    trimmed, report = middleware.process(long_conversation)
    assert report.summarization_triggered is True
    assert report.rolling_summary != ""
    assert report.tokens_after <= report.tokens_before
    assert len(trimmed) < len(long_conversation)


def test_long_term_store_namespace_search() -> None:
    """Verifica Criterio 1.3: Store con namespace guarda hechos y los recupera con search()."""
    store = PersistentSqliteStore(":memory:")
    saved = extract_and_persist_user_facts(
        user_id="rommel-uao",
        user_message="Me llamo Rommel, trabajo en EMCALI y vivo en estrato 4.",
        store=store,
        source_thread_id="thread-a",
    )
    assert len(saved) >= 2

    found = search_user_long_term_memories("rommel-uao", store, query="empresa estrato")
    keys = {item["key"] for item in found}
    assert "nombre_usuario" in keys
    assert "empresa_organizacion" in keys
    assert "estrato_vivienda" in keys


def test_deterministic_csv_and_json_tools_with_pydantic() -> None:
    """Verifica Criterio 2.1: @tool sobre CSV/JSON valida con Pydantic y entrega cifras exactas."""
    csv_report = query_tarifas_structured(servicio="energia", estrato=3, trimestre="2026-Q3")
    assert csv_report.records_matched == 1
    row = csv_report.rows[0]
    assert row["tarifa_base_cop"] == 880.0
    assert row["subsidio_contribucion_pct"] == -15.0
    assert row["tarifa_aplicada_cop"] == 748.0

    tool_out = consultar_tarifas_emcali_csv.invoke(
        {"servicio": "energia", "estrato": 3, "segmento": "Residencial", "trimestre": "2026-Q3"}
    )
    assert tool_out["records_matched"] == 1

    json_report = query_indicadores_structured(
        servicio="atencion-y-servicio-a-la-ciudadania", trimestre="2026-Q3"
    )
    assert json_report.records_matched == 1
    assert json_report.rows[0]["valor_reportado"] == 47390

    json_tool_out = consultar_indicadores_operativos_json.invoke(
        {"servicio": "energia", "trimestre": "2026-Q3", "palabra_clave": "clientes"}
    )
    assert json_tool_out["records_matched"] >= 1


def test_qdrant_ann_hybrid_search_and_payload_filter() -> None:
    """Verifica Criterio 2.2: Qdrant con índice HNSW, filtro de payload y cita de fuente."""
    vs = EmcaliQdrantVectorStore(in_memory=True, chunks=_sample_chunks())
    info = vs.collection_info_summary()
    assert info["indexed_points"] == 3
    assert "HNSW" in info["ann_index_type"]

    hits = vs.search(
        "Ley 1581 días hábiles reclamos", top_k=2, section_filter="proteccion-de-datos-personales"
    )
    assert len(hits) == 1
    assert hits[0].chunk.section == "proteccion-de-datos-personales"
    assert "https://www.emcali.com.co" in hits[0].chunk.source_url


def test_router_jev_choices_and_noul_gate() -> None:
    """Verifica Criterio 2.3: Router Jev no busca en saludos y separa CSV, RAG y Mixto."""
    greeting_dec = route_query_with_jev("Hola, buenos días")
    assert greeting_dec.choice == "direct_reply"
    assert greeting_dec.noul_triggered is True
    assert greeting_dec.tools_to_invoke == []

    cancel_dec = route_query_with_jev("¿Dónde puedo cancelar mi contrato con EMCALI?")
    assert cancel_dec.choice == "direct_reply"
    assert cancel_dec.noul_triggered is True
    assert cancel_dec.box.is_out_of_scope_or_private is True

    csv_dec = route_query_with_jev(
        "¿Cuál es la tarifa en el CSV para estrato 3 en el tercer trimestre?"
    )
    assert csv_dec.choice == "structured_tool"
    assert csv_dec.box.estrato == 3
    assert csv_dec.box.trimestre == "2026-Q3"

    rag_dec = route_query_with_jev(
        "¿Qué dice el documento sobre la Ley 1581 y derechos del titular?"
    )
    assert rag_dec.choice == "rag_search"
    assert rag_dec.box.section_filter == "proteccion-de-datos-personales"

    mixed_dec = route_query_with_jev(
        "Compara la meta del documento corporativo con las tarifas del CSV en el tercer trimestre"
    )
    assert mixed_dec.choice == "hybrid_multi_tool"
    assert "buscar_corpus_qdrant" in mixed_dec.tools_to_invoke
    assert "consultar_tarifas_emcali_csv" in mixed_dec.tools_to_invoke


def test_rag_shield_blocks_indirect_prompt_injection() -> None:
    """Verifica Criterio 2.4 y Caso 5: el blindaje detecta y neutraliza inyección indirecta."""
    shielded = wrap_chunk_as_passive_data(CANARY_INJECTION_CHUNK)
    assert shielded.injection_detected is True
    assert shielded.risk_level == "high"
    assert "override_previous_instructions" in shielded.matched_rules
    assert "100% gratuito en 2026" not in shielded.sanitized_text
    assert "<datos_pasivos_corpus" in shielded.passive_xml_block

    block, items = build_passive_context_block([CANARY_INJECTION_CHUNK])
    assert len(items) == 1
    assert "DATOS PASIVOS" in block


def test_voice_hotword_and_tts_processing() -> None:
    """Verifica el módulo de voz con hotwords 'Eder', 'Oye Eder', 'Hola Eder' y fonética."""
    for wake_phrase in ("Eder", "Oye Eder", "Hola Eder"):
        cmd = parse_voice_hotword_command(
            f"{wake_phrase}, ¿cuántas pe cu erre se atendieron en el tercer trimestre?",
            require_hotword=True,
        )
        assert cmd.hotword_detected is True
        assert "PQR" in cmd.clean_query
        assert not cmd.clean_query.lower().startswith("eder")
        assert not cmd.clean_query.lower().startswith("oye")
        assert not cmd.clean_query.lower().startswith("hola")

    rejected = parse_voice_hotword_command("¿Cuál es la tarifa de energía?", require_hotword=True)
    assert rejected.hotword_detected is False

    # En modo Eder Live (live_session_active=True), acepta turnos continuos sin repetir el hotword
    live_turn = parse_voice_hotword_command(
        "¿Y cuál es la tarifa de energía en estrato 3?",
        require_hotword=True,
        live_session_active=True,
    )
    assert live_turn.hotword_detected is True
    assert live_turn.should_enter_live is True
    assert "estrato 3" in live_turn.clean_query

    # Frase de cierre ("Gracias Eder") vuelve a espera
    sleep_cmd = parse_voice_hotword_command(
        "Gracias Eder",
        require_hotword=True,
        live_session_active=True,
    )
    assert sleep_cmd.sleep_requested is True
    assert sleep_cmd.should_enter_live is False

    tts = build_tts_speech_summary(
        "📊 La tarifa es **748 COP** 🛡️. Consulta "
        "[Tarifas](https://www.emcali.com.co/energia).\n\n### 🔗 Fuentes Oficiales\n- link"
    )
    assert "https://" not in tts
    assert "📊" not in tts
    assert "🛡️" not in tts
    assert "748 COP" in tts


def test_fastapi_endpoints_and_retrieval_metrics() -> None:
    """Verifica los endpoints del backend FastAPI y el cálculo de Recall@10 / nDCG@10."""
    vs = EmcaliQdrantVectorStore(in_memory=True, chunks=_sample_chunks())
    mem = MemoryManager(checkpoints_path=":memory:", store_path=":memory:")
    agent = EmcaliConversationalAgent(vector_store=vs, memory_manager=mem)
    client = TestClient(create_fastapi_app(agent))

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    chat_res = client.post(
        "/api/chat",
        json={
            "question": "¿Cuántas solicitudes PQR se atendieron en el tercer trimestre?",
            "thread_id": "test-api-thread",
            "user_id": "test-user",
            "use_llm": False,
        },
    )
    assert chat_res.status_code == 200
    body = chat_res.json()
    assert body["router_decision"]["choice"] == "structured_tool"
    assert "47,390" in body["answer"] or "47390" in body["answer"]

    voice_res = client.post(
        "/api/voice/command",
        json={
            "transcript": "Oye Eder, hola me llamo Carlos y trabajo en Celsia",
            "require_hotword": True,
            "thread_id": "test-voice-thread",
            "user_id": "carlos-user",
            "use_llm": False,
        },
    )
    assert voice_res.status_code == 200
    v_body = voice_res.json()
    assert v_body["accepted"] is True
    assert v_body["voice_analysis"]["hotword_detected"] is True

    eval_metrics = evaluate_retrieval_mode(vs, search_mode="hybrid", queries=())
    assert eval_metrics["queries_evaluated"] == 0


def test_router_blocks_off_topic_math_and_python_queries() -> None:
    """Verifica que la compuerta Noul rechaza consultas de cálculo o programación sin alucinar."""
    vs = EmcaliQdrantVectorStore(in_memory=True, chunks=_sample_chunks())
    mem = MemoryManager(checkpoints_path=":memory:", store_path=":memory:")
    agent = EmcaliConversationalAgent(vector_store=vs, memory_manager=mem)

    for query in (
        "¿Cuál es la derivada de arctan(x)?",
        "¿Cómo simular y graficar esa función en python?",
    ):
        decision = route_query_with_jev(query)
        assert decision.choice == "direct_reply"
        assert decision.noul_triggered is True
        assert decision.box.is_out_of_scope_or_private is True

        out = agent.invoke_turn(query, thread_id="test-offtopic", user_id="test-user", use_llm=True)
        assert "EMCALI" in out.answer
        assert "1 / (1 + x" not in out.answer
        assert "matplotlib" not in out.answer.lower()
        assert "3.120" not in out.answer
