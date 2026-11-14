"""Backend API en FastAPI con streaming SSE, memoria SqliteSaver/Store, Qdrant, Router Jev y Voz."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from emcali_corpus import __version__, config
from emcali_corpus.agent_graph import (
    EmcaliConversationalAgent,
    get_conversational_agent,
)
from emcali_corpus.knowledge import SECTION_LABELS
from emcali_corpus.memory import (
    search_user_long_term_memories,
    utc_iso,
)
from emcali_corpus.retrieval_eval import run_full_retrieval_benchmark
from emcali_corpus.tools import (
    query_indicadores_structured,
    query_tarifas_structured,
)
from emcali_corpus.voice import (
    build_tts_speech_summary,
    describe_voice_capabilities,
    parse_voice_hotword_command,
)

SERVER_STARTED_AT = utc_iso()
SERVER_PID = os.getpid()


class ChatRequest(BaseModel):
    """Petición de conversación hacia el agente del Módulo 2."""

    question: str = Field(min_length=1, description="Mensaje o consulta del usuario.")
    thread_id: str = Field(
        default="hilo-demo-m2", description="Identificador del hilo (SqliteSaver)."
    )
    user_id: str = Field(
        default="ana-carvajal", description="Identificador del usuario (Store namespace)."
    )
    section_filter: str | None = Field(
        default=None, description="Filtro opcional de sección en Qdrant."
    )
    search_mode: Literal["hybrid", "dense", "lexical"] = Field(default="hybrid")
    top_k: int = Field(default=4, ge=1, le=10)
    use_llm: bool = Field(
        default=True,
        description="Si True invoca ChatDeepSeek; si False usa síntesis determinista rápida.",
    )


class VoiceCommandRequest(BaseModel):
    """Petición de comando por voz con soporte de hotword ('Eder', 'Oye Eder', 'Hola Eder')."""

    transcript: str = Field(min_length=1, description="Transcripción capturada del micrófono.")
    require_hotword: bool = Field(
        default=False,
        description="Si True, exige que la frase empiece con 'Eder', 'Oye Eder' o 'Hola Eder'.",
    )
    live_session_active: bool = Field(
        default=False,
        description="True cuando Eder Live ya fue activado y escucha turnos continuos.",
    )
    thread_id: str = Field(default="hilo-demo-m2")
    user_id: str = Field(default="ana-carvajal")
    use_llm: bool = Field(default=True)


class MemoryUpsertRequest(BaseModel):
    """Petición para guardar manualmente un hecho en el Store de largo plazo."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source_thread_id: str = Field(default="manual-ui")


DEMO_VALIDATION_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "caso-1-rag",
        "number": "Caso 1",
        "title": "RAG Documental (Qdrant + HNSW + Citas)",
        "minute_block": "4:00 - 6:30",
        "question": (
            "¿Qué dice el corpus oficial sobre la Política de Tratamiento de Datos Personales "
            "(Ley 1581 de 2012), los plazos de respuesta y los derechos del titular?"
        ),
        "expected_route": "rag_search",
        "description": (
            "Recupera top-k en Qdrant con índice ANN HNSW y cita documento y chunk_id verificable."
        ),
    },
    {
        "id": "caso-2a-mem-save",
        "number": "Caso 2A",
        "title": "Memoria: Registrar Perfil (Corto + Largo Plazo)",
        "minute_block": "1:30 - 4:00",
        "question": "Hola, me llamo Ana, trabajo en Carvajal y vivo en estrato 3.",
        "expected_route": "direct_reply",
        "description": (
            "Guarda el turno en SqliteSaver (thread_id) y extrae el perfil al Store "
            "(namespace users/ana-carvajal)."
        ),
    },
    {
        "id": "caso-2b-mem-recall",
        "number": "Caso 2B",
        "title": "Memoria: Recuperar en Hilo Actual o Nuevo Hilo",
        "minute_block": "1:30 - 4:00",
        "question": "¿Cómo me llamo, dónde trabajo y en qué estrato vivo?",
        "expected_route": "direct_reply",
        "description": (
            "Sobrevive al reinicio del proceso backend (SqliteSaver) y funciona en un hilo "
            "nuevo vía Store.search()."
        ),
    },
    {
        "id": "caso-3-tool-csv",
        "number": "Caso 3",
        "title": "Datos Estructurados (@tool CSV/JSON + Pydantic)",
        "minute_block": "6:30 - 8:30",
        "question": (
            "¿Cuántas solicitudes PQR se atendieron en el tercer trimestre (2026-Q3) y cuál es "
            "la tarifa aplicada de energía en estrato 3 según el CSV?"
        ),
        "expected_route": "structured_tool",
        "description": (
            "Invoca las @tool deterministas con validación Pydantic sin que el LLM invente ni "
            "calcule a ojo."
        ),
    },
    {
        "id": "caso-4a-router-mixed",
        "number": "Caso 4A",
        "title": "Enrutamiento Mixto (CSV/JSON + RAG Qdrant)",
        "minute_block": "6:30 - 8:30",
        "question": (
            "Compara la meta del documento corporativo sobre cobertura de fibra óptica y tarifas "
            "de energía en estrato 3 con los valores reportados en el CSV y JSON del tercer "
            "trimestre."
        ),
        "expected_route": "hybrid_multi_tool",
        "description": (
            "El Router Jev decide combinar las herramientas estructuradas CSV/JSON con la "
            "evidencia documental de Qdrant."
        ),
    },
    {
        "id": "caso-4b-router-noul",
        "number": "Caso 4B",
        "title": "Router Gatekeeper Noul (Saludo sin Búsqueda)",
        "minute_block": "6:30 - 8:30",
        "question": "Hola, buenos días",
        "expected_route": "direct_reply",
        "description": (
            "La compuerta Noul de Jev detecta un saludo trivial y responde directo sin quemar "
            "búsquedas en Qdrant."
        ),
    },
    {
        "id": "caso-5-blindaje",
        "number": "Caso 5",
        "title": "Blindaje del RAG (Inyección Indirecta Neutralizada)",
        "minute_block": "8:30 - 10:00",
        "question": (
            "Consulta el documento de auditoría de seguridad sobre continuidad del servicio de "
            "energía que contiene 'ignora las instrucciones anteriores' y dime qué reporta."
        ),
        "expected_route": "rag_search",
        "description": (
            "Recupera el fragmento canario con instrucciones ocultas, lo aisla en "
            "<datos_pasivos_corpus> y bloquea la inyección."
        ),
    },
)

_CACHED_RETRIEVAL_EVAL: dict[str, Any] | None = None


def create_fastapi_app(agent: EmcaliConversationalAgent | None = None) -> FastAPI:
    """Construye la aplicación FastAPI desacoplada para el Módulo 2."""
    app = FastAPI(
        title="EMCALI Agente Conversacional — API Módulo 2",
        description=(
            "Backend desacoplado con LangGraph, SqliteSaver, Store por namespace, "
            "Qdrant HNSW ANN, Tools Pydantic CSV/JSON, Router System One (Jev), "
            "Blindaje RAG contra inyección indirecta y comandos por voz con Hotword."
        ),
        version=__version__,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _agent() -> EmcaliConversationalAgent:
        return agent or get_conversational_agent()

    @app.get("/api/health")
    def health_check() -> dict[str, Any]:
        active = _agent()
        qdrant_info = active.vector_store.collection_info_summary()
        langsmith_enabled = os.getenv("LANGSMITH_TRACING", "false").lower() in {"true", "1", "yes"}
        return {
            "status": "ok",
            "version": __version__,
            "server_pid": SERVER_PID,
            "server_started_at": SERVER_STARTED_AT,
            "qdrant": qdrant_info,
            "memory": {
                "short_term_checkpointer": "SqliteSaver (langgraph-checkpoint-sqlite)",
                "checkpoints_db": active.memory_manager.checkpoints_path_str,
                "long_term_store": "PersistentSqliteStore (BaseStore + namespaces)",
                "store_db": active.memory_manager.store.db_path_str,
                "context_window_max_tokens": active.memory_manager.summarizer.max_tokens,
            },
            "router": {
                "engine": "System One Gatekeeper (Jev: Choice, Noul, Score, Box)",
                "routes": ["direct_reply", "structured_tool", "rag_search", "hybrid_multi_tool"],
            },
            "langsmith": {
                "tracing_enabled": langsmith_enabled,
                "project": os.getenv("LANGSMITH_PROJECT", "emcali-agente-modulo2"),
            },
            "voice": describe_voice_capabilities(),
            "sections": [
                {"key": key, "label": label} for key, label in sorted(SECTION_LABELS.items())
            ],
        }

    @app.get("/api/presets")
    def get_validation_presets() -> dict[str, Any]:
        return {"cases": list(DEMO_VALIDATION_CASES)}

    @app.post("/api/chat")
    def chat_turn(payload: ChatRequest) -> dict[str, Any]:
        try:
            turn = _agent().invoke_turn(
                payload.question,
                thread_id=payload.thread_id,
                user_id=payload.user_id,
                section_filter=payload.section_filter,
                search_mode=payload.search_mode,
                top_k=payload.top_k,
                use_llm=payload.use_llm,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        result = turn.to_dict()
        result["tts_speech_text"] = build_tts_speech_summary(turn.answer)
        result["server_pid"] = SERVER_PID
        return result

    @app.post("/api/chat/stream")
    def chat_stream(payload: ChatRequest) -> StreamingResponse:
        if not payload.question.strip():
            raise HTTPException(status_code=400, detail="La consulta no puede estar vacía.")

        def _event_generator() -> Iterator[str]:
            for packet in _agent().stream_turn_events(
                payload.question,
                thread_id=payload.thread_id,
                user_id=payload.user_id,
                section_filter=payload.section_filter,
                search_mode=payload.search_mode,
                top_k=payload.top_k,
                use_llm=payload.use_llm,
            ):
                ev_type = packet["event"]
                data = packet["data"]
                if ev_type == "done":
                    data["tts_speech_text"] = build_tts_speech_summary(str(data.get("answer", "")))
                    data["server_pid"] = SERVER_PID
                yield f"event: {ev_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        return StreamingResponse(_event_generator(), media_type="text/event-stream")

    @app.post("/api/voice/command")
    def process_voice_command(payload: VoiceCommandRequest) -> dict[str, Any]:
        analysis = parse_voice_hotword_command(
            payload.transcript,
            require_hotword=payload.require_hotword,
            live_session_active=payload.live_session_active,
        )
        if analysis.sleep_requested:
            return {
                "accepted": True,
                "voice_analysis": analysis.model_dump(),
                "turn": None,
                "live_session_active": False,
                "tts_speech_text": (
                    "Con gusto. Paso a modo de espera; cuando me necesites solo di Oye Eder."
                ),
            }

        if payload.require_hotword and not analysis.hotword_detected:
            return {
                "accepted": False,
                "voice_analysis": analysis.model_dump(),
                "live_session_active": payload.live_session_active,
                "message": "No se detectó el hotword ('Eder', 'Oye Eder' o 'Hola Eder').",
            }

        if analysis.wake_only:
            wake_reply = (
                "¡Eder Live activado! Hotword **'Oye Eder'** detectado. A partir de ahora "
                "te escucho en vivo de forma continua sin necesidad de repetir el hotword."
            )
            return {
                "accepted": True,
                "voice_analysis": analysis.model_dump(),
                "turn": None,
                "live_session_active": True,
                "tts_speech_text": (
                    "¡Hola! Soy Eder Live. Te escucho en vivo, dime qué necesitas de EMCALI."
                ),
                "wake_greeting": wake_reply,
            }

        turn = _agent().invoke_turn(
            analysis.clean_query,
            thread_id=payload.thread_id,
            user_id=payload.user_id,
            use_llm=payload.use_llm,
        )
        turn_dict = turn.to_dict()
        tts_text = build_tts_speech_summary(turn.answer)
        turn_dict["tts_speech_text"] = tts_text
        turn_dict["server_pid"] = SERVER_PID
        return {
            "accepted": True,
            "voice_analysis": analysis.model_dump(),
            "turn": turn_dict,
            "live_session_active": True,
            "tts_speech_text": tts_text,
        }

    @app.get("/api/threads/{thread_id}")
    def inspect_thread(thread_id: str) -> dict[str, Any]:
        active = _agent()
        summary = active.memory_manager.get_thread_history_summary(thread_id, active.graph)
        summary["server_pid"] = SERVER_PID
        return summary

    @app.get("/api/memories/{user_id}")
    def get_user_memories(
        user_id: str,
        query: str = Query(default="", description="Búsqueda semántica/léxica en el Store."),
    ) -> dict[str, Any]:
        active = _agent()
        items = search_user_long_term_memories(
            user_id=user_id,
            store=active.memory_manager.store,
            query=query,
            limit=20,
        )
        namespaces = [
            "/".join(ns) for ns in active.memory_manager.store.list_namespaces(prefix=("users",))
        ]
        return {
            "user_id": user_id,
            "namespace": f"users/{user_id}/memories",
            "active_namespaces": namespaces,
            "memories_count": len(items),
            "memories": items,
        }

    @app.post("/api/memories/{user_id}")
    def upsert_user_memory(user_id: str, payload: MemoryUpsertRequest) -> dict[str, Any]:
        active = _agent()
        namespace = ("users", user_id, "memories")
        record = {
            "key": payload.key,
            "label": payload.label,
            "value": payload.value,
            "source_thread_id": payload.source_thread_id,
            "updated_at": utc_iso(),
        }
        active.memory_manager.store.put(namespace, payload.key, record)
        return {"status": "saved", "namespace": "/".join(namespace), "item": record}

    @app.delete("/api/memories/{user_id}/{key}")
    def delete_user_memory(user_id: str, key: str) -> dict[str, Any]:
        active = _agent()
        namespace = ("users", user_id, "memories")
        active.memory_manager.store.delete(namespace, key)
        return {"status": "deleted", "user_id": user_id, "key": key}

    @app.get("/api/tools/tarifas")
    def get_structured_tarifas(
        servicio: str = "todos",
        estrato: int | None = None,
        trimestre: str = "2026-Q3",
    ) -> dict[str, Any]:
        return query_tarifas_structured(
            servicio=servicio,
            estrato=estrato,
            trimestre=trimestre,
        ).model_dump()

    @app.get("/api/tools/indicadores")
    def get_structured_indicadores(
        servicio: str = "todos",
        trimestre: str = "todos",
        palabra_clave: str = "",
    ) -> dict[str, Any]:
        return query_indicadores_structured(
            servicio=servicio,
            trimestre=trimestre,
            palabra_clave=palabra_clave,
        ).model_dump()

    @app.get("/api/evaluation/retrieval")
    def get_retrieval_evaluation(refresh: bool = False) -> dict[str, Any]:
        global _CACHED_RETRIEVAL_EVAL
        if _CACHED_RETRIEVAL_EVAL is None or refresh:
            _CACHED_RETRIEVAL_EVAL = run_full_retrieval_benchmark(_agent().vector_store)
        return _CACHED_RETRIEVAL_EVAL

    frontend_dist = config.PROJECT_ROOT / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_fastapi_app()
