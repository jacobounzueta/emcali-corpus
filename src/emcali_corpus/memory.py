"""Memoria conversacional de corto plazo (SqliteSaver) y largo plazo (Store + namespace)."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    trim_messages,
)
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.base import (
    NOT_PROVIDED,
    BaseStore,
    Item,
    NotProvided,
    Op,
    Result,
    SearchItem,
)

from emcali_corpus import config

MEMORY_DIR = config.DATA_DIR / "memory"
CHECKPOINTS_DB_PATH = MEMORY_DIR / "checkpoints.sqlite"
STORE_DB_PATH = MEMORY_DIR / "store.sqlite"

DEFAULT_MAX_CONTEXT_TOKENS = 1800
DEFAULT_SUMMARIZATION_TURN_THRESHOLD = 6

NAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:me\s+llamo|mi\s+nombre\s+es|soy)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)",
        re.IGNORECASE,
    ),
)
COMPANY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:trabajo\s+en|laboro\s+en|soy\s+de\s+la\s+empresa|pertenezco\s+a)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ0-9\s.&-]{2,40}?)(?:[.,;]|$|\s+y\s+|\s+como\s+)",
        re.IGNORECASE,
    ),
)
ROLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:soy|trabajo\s+como|mi\s+cargo\s+es)\s+(ingenier[oa]|analista|gerente|arquitect[oa]|estudiante|consultor[a]?|director[a]?|auditor[a]?|contador[a]?|abogad[oa])(?:\s+de\s+[a-záéíóúñ\s]{2,25})?",
        re.IGNORECASE,
    ),
)
ESTRATO_PATTERN = re.compile(r"\bestrato\s+([1-6])\b", re.IGNORECASE)
BARRIO_PATTERN = re.compile(
    r"\b(?:vivo\s+en|barrio|sector)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ0-9\s]{3,30}?)(?:[.,;]|$|\s+estrato|\s+y\s+)",
    re.IGNORECASE,
)
PREFERENCE_PATTERN = re.compile(
    r"\b(?:prefiero|me\s+interesa|necesito\s+informaci[oó]n\s+sobre)\s+([^.,;\n]{4,60})",
    re.IGNORECASE,
)


def utc_iso() -> str:
    """Timestamp UTC ISO-8601 sin microsegundos."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def estimate_message_tokens(messages: Sequence[BaseMessage]) -> int:
    """Contador determinista de tokens (~1.35 tokens por palabra) para trim_messages."""
    total_words = 0
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        total_words += max(1, len(content.split()))
    return round(total_words * 1.35)


@dataclass(frozen=True, slots=True)
class ContextWindowReport:
    """Métricas de recorte y resumen multi-turno para observabilidad y UI."""

    total_messages_before: int
    kept_messages_after: int
    tokens_before: int
    tokens_after: int
    max_token_budget: int
    trimmed_count: int
    summarization_triggered: bool
    rolling_summary: str

    def to_dict(self) -> dict[str, Any]:
        """Serializa el estado de gestión de ventana de contexto."""
        return {
            "total_messages_before": self.total_messages_before,
            "kept_messages_after": self.kept_messages_after,
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "max_token_budget": self.max_token_budget,
            "trimmed_count": self.trimmed_count,
            "summarization_triggered": self.summarization_triggered,
            "rolling_summary": self.rolling_summary,
        }


class SummarizationMiddleware:
    """Middleware de gestión multi-turno que resume turnos antiguos y aplica trim_messages."""

    def __init__(
        self,
        *,
        max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        summarize_after_messages: int = DEFAULT_SUMMARIZATION_TURN_THRESHOLD,
    ) -> None:
        self.max_tokens = max_tokens
        self.summarize_after_messages = summarize_after_messages

    def process(
        self,
        messages: Sequence[BaseMessage],
    ) -> tuple[list[BaseMessage], ContextWindowReport]:
        """Condensa turnos antiguos cuando exceden el umbral y recorta con trim_messages."""
        msg_list = list(messages)
        tokens_before = estimate_message_tokens(msg_list)
        total_before = len(msg_list)

        rolling_summary = ""
        summarization_triggered = False

        non_system = [m for m in msg_list if not isinstance(m, SystemMessage)]
        if len(non_system) > self.summarize_after_messages:
            summarization_triggered = True
            older_slice = non_system[: -self.summarize_after_messages]
            bullet_points: list[str] = []
            for m in older_slice[-4:]:
                role = "Usuario" if isinstance(m, HumanMessage) else "Asistente"
                text = (m.content if isinstance(m.content, str) else str(m.content)).strip()
                snippet = text[:55] + ("..." if len(text) > 55 else "")
                bullet_points.append(f"- {role}: {snippet}")
            rolling_summary = "Resumen previo:\n" + "\n".join(bullet_points)

        candidate_msgs: list[BaseMessage] = list(msg_list)
        if summarization_triggered and rolling_summary:
            summary_msg = SystemMessage(content=f"[MEMORIA CORTO PLAZO]: {rolling_summary}")
            recent_keep = max(2, self.summarize_after_messages // 2)
            candidate_msgs = [summary_msg, *non_system[-recent_keep:]]

        trimmed: list[BaseMessage] = list(
            trim_messages(
                candidate_msgs,
                max_tokens=self.max_tokens,
                token_counter=estimate_message_tokens,
                strategy="last",
                include_system=True,
                allow_partial=False,
            )
        )

        tokens_after = min(tokens_before, estimate_message_tokens(trimmed))
        trimmed_count = max(0, total_before - len(trimmed))

        report = ContextWindowReport(
            total_messages_before=total_before,
            kept_messages_after=len(trimmed),
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            max_token_budget=self.max_tokens,
            trimmed_count=trimmed_count,
            summarization_triggered=summarization_triggered,
            rolling_summary=rolling_summary,
        )
        return trimmed, report


class PersistentSqliteStore(BaseStore):
    """Implementación persistente en SQLite del Store de largo plazo de LangGraph con namespaces."""

    def __init__(self, db_path: Path | str = STORE_DB_PATH) -> None:
        if str(db_path) == ":memory:":
            self.db_path_str = ":memory:"
        else:
            path_obj = Path(db_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            self.db_path_str = str(path_obj)

        self._conn = sqlite3.connect(self.db_path_str, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS langgraph_store_items (
                    namespace TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (namespace, item_key)
                )
                """
            )

    @staticmethod
    def _ns_to_str(namespace: tuple[str, ...]) -> str:
        return "/".join(namespace)

    @staticmethod
    def _str_to_ns(ns_str: str) -> tuple[str, ...]:
        return tuple(part for part in ns_str.split("/") if part)

    def put(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: Mapping[str, Any],
        index: Literal[False] | list[str] | None = None,
        *,
        ttl: float | NotProvided | None = NOT_PROVIDED,
    ) -> None:
        """Guarda o actualiza un hecho/preferencia bajo un namespace jerárquico."""
        del index, ttl
        ns_str = self._ns_to_str(namespace)
        now = utc_iso()
        existing = self.get(namespace, key)
        created_at = existing.created_at.isoformat() if existing else now
        payload = json.dumps(dict(value), ensure_ascii=False)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO langgraph_store_items (
                    namespace, item_key, value_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(namespace, item_key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (ns_str, key, payload, created_at, now),
            )

    def get(
        self,
        namespace: tuple[str, ...],
        key: str,
        *,
        refresh_ttl: bool | None = None,
    ) -> Item | None:
        """Recupera un ítem exacto por namespace y clave."""
        del refresh_ttl
        ns_str = self._ns_to_str(namespace)
        row = self._conn.execute(
            """
            SELECT namespace, item_key, value_json, created_at, updated_at
            FROM langgraph_store_items
            WHERE namespace = ? AND item_key = ?
            """,
            (ns_str, key),
        ).fetchone()
        if row is None:
            return None
        return Item(
            value=json.loads(str(row["value_json"])),
            key=str(row["item_key"]),
            namespace=self._str_to_ns(str(row["namespace"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    def delete(self, namespace: tuple[str, ...], key: str) -> None:
        """Elimina un ítem de la memoria de largo plazo."""
        ns_str = self._ns_to_str(namespace)
        with self._conn:
            self._conn.execute(
                "DELETE FROM langgraph_store_items WHERE namespace = ? AND item_key = ?",
                (ns_str, key),
            )

    def search(
        self,
        namespace_prefix: tuple[str, ...],
        *,
        query: str | None = None,
        filter: dict[str, Any] | None = None,
        limit: int = 10,
        offset: int = 0,
        refresh_ttl: bool | None = None,
    ) -> list[SearchItem]:
        """Busca ítems dentro de un prefijo de namespace (recuperación cross-thread)."""
        del refresh_ttl
        prefix_str = self._ns_to_str(namespace_prefix)
        rows = self._conn.execute(
            """
            SELECT namespace, item_key, value_json, created_at, updated_at
            FROM langgraph_store_items
            WHERE namespace = ? OR namespace LIKE ?
            ORDER BY updated_at DESC
            """,
            (prefix_str, f"{prefix_str}/%"),
        ).fetchall()

        q_tokens = [
            tok.lower() for tok in re.findall(r"[a-z0-9áéíóúñü]{2,}", (query or "").lower())
        ]
        results: list[SearchItem] = []

        for row in rows:
            val_dict: dict[str, Any] = json.loads(str(row["value_json"]))
            if filter and not all(val_dict.get(k) == v for k, v in filter.items()):
                continue

            score = 1.0
            if q_tokens:
                serialized_lower = json.dumps(val_dict, ensure_ascii=False).lower()
                matches = sum(1 for tok in q_tokens if tok in serialized_lower)
                score = round(0.5 + 0.5 * (matches / len(q_tokens)), 4)

            results.append(
                SearchItem(
                    namespace=self._str_to_ns(str(row["namespace"])),
                    key=str(row["item_key"]),
                    value=val_dict,
                    created_at=datetime.fromisoformat(str(row["created_at"])),
                    updated_at=datetime.fromisoformat(str(row["updated_at"])),
                    score=score,
                )
            )

        results.sort(key=lambda item: (item.score or 0.0, item.updated_at), reverse=True)
        return results[offset : offset + limit]

    def list_namespaces(
        self,
        *,
        prefix: tuple[str, ...] | None = None,
        suffix: tuple[str, ...] | None = None,
        max_depth: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[tuple[str, ...]]:
        """Lista los namespaces activos almacenados en el Store."""
        del suffix
        rows = self._conn.execute(
            "SELECT DISTINCT namespace FROM langgraph_store_items ORDER BY namespace"
        ).fetchall()
        namespaces: list[tuple[str, ...]] = []
        for row in rows:
            ns = self._str_to_ns(str(row["namespace"]))
            if prefix and ns[: len(prefix)] != prefix:
                continue
            if max_depth is not None:
                ns = ns[:max_depth]
            if ns not in namespaces:
                namespaces.append(ns)
        return namespaces[offset : offset + limit]

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        """Ejecuta operaciones por lotes requeridas por la interfaz BaseStore de LangGraph."""
        return [None for _ in ops]

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        """Versión asíncrona de batch para compatibilidad con BaseStore."""
        return self.batch(ops)


def extract_and_persist_user_facts(
    user_id: str,
    user_message: str,
    store: PersistentSqliteStore,
    *,
    source_thread_id: str = "",
) -> list[dict[str, Any]]:
    """Extrae hechos del perfil o preferencias del usuario y los persiste en el Store."""
    namespace = ("users", user_id, "memories")
    extracted: list[tuple[str, str, str]] = []
    clean_msg = user_message.strip()

    invalid_name_tokens = {
        "de",
        "del",
        "en",
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "usuario",
        "cliente",
        "ciudadano",
        "persona",
        "estudiante",
        "ingeniero",
        "ingeniera",
        "analista",
        "gerente",
        "director",
        "directora",
        "eder",
        "emcali",
        "nuevo",
        "nueva",
    }
    for pat in NAME_PATTERNS:
        m = pat.search(clean_msg)
        if m:
            candidate = m.group(1).strip()
            cand_tokens = set(candidate.lower().split())
            if cand_tokens and not (cand_tokens & invalid_name_tokens):
                extracted.append(("nombre_usuario", "Nombre del usuario", candidate))
                break

    for pat in COMPANY_PATTERNS:
        m = pat.search(clean_msg)
        if m:
            company = m.group(1).strip().rstrip(".,;")
            extracted.append(
                ("empresa_organizacion", "Empresa u organización donde trabaja", company)
            )
            break

    for pat in ROLE_PATTERNS:
        m = pat.search(clean_msg)
        if m:
            role = m.group(0).strip()
            extracted.append(("rol_ocupacion", "Rol u ocupación reportada", role))
            break

    m_estrato = ESTRATO_PATTERN.search(clean_msg)
    if m_estrato:
        extracted.append(
            (
                "estrato_vivienda",
                "Estrato socioeconómico del usuario",
                f"Estrato {m_estrato.group(1)}",
            )
        )

    m_barrio = BARRIO_PATTERN.search(clean_msg)
    if m_barrio:
        barrio = m_barrio.group(1).strip().rstrip(".,;")
        extracted.append(("ubicacion_barrio", "Barrio o ubicación en Cali", barrio))

    m_pref = PREFERENCE_PATTERN.search(clean_msg)
    if m_pref:
        pref = m_pref.group(1).strip().rstrip(".,;")
        extracted.append(("preferencia_interes", "Preferencia o tema de interés", pref))

    persisted_items: list[dict[str, Any]] = []
    for key, label, val in extracted:
        payload = {
            "key": key,
            "label": label,
            "value": val,
            "source_thread_id": source_thread_id,
            "raw_utterance": clean_msg,
            "updated_at": utc_iso(),
        }
        store.put(namespace, key, payload)
        persisted_items.append(payload)

    return persisted_items


def search_user_long_term_memories(
    user_id: str,
    store: PersistentSqliteStore,
    *,
    query: str = "",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Recupera las memorias de largo plazo del usuario desde su namespace usando search()."""
    items = store.search(("users", user_id), query=query or None, limit=limit)
    results: list[dict[str, Any]] = []
    for item in items:
        results.append(
            {
                "namespace": "/".join(item.namespace),
                "key": item.key,
                "label": item.value.get("label", item.key),
                "value": item.value.get("value", ""),
                "source_thread_id": item.value.get("source_thread_id", ""),
                "updated_at": item.updated_at.isoformat(),
                "score": item.score,
            }
        )
    return results


def format_memories_for_prompt(memories: Sequence[dict[str, Any]]) -> str:
    """Formatea los hechos del Store de largo plazo para inyectarlos en el prompt dinámico."""
    if not memories:
        return "Sin perfil ni preferencias previas registradas en el Store para este usuario."
    lines = [
        f"- **{m.get('label', m.get('key'))} (`{m.get('key')}`):** {m.get('value')} "
        f"*(registrado en hilo `{m.get('source_thread_id', 'previo')}`)*"
        for m in memories
    ]
    return "\n".join(lines)


class MemoryManager:
    """Administrador central de SqliteSaver (corto plazo) y PersistentSqliteStore (largo plazo)."""

    def __init__(
        self,
        *,
        checkpoints_path: Path | str = CHECKPOINTS_DB_PATH,
        store_path: Path | str = STORE_DB_PATH,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    ) -> None:
        if str(checkpoints_path) == ":memory:":
            self.checkpoints_path_str = ":memory:"
        else:
            cp_path = Path(checkpoints_path)
            cp_path.parent.mkdir(parents=True, exist_ok=True)
            self.checkpoints_path_str = str(cp_path)

        self._sqlite_conn = sqlite3.connect(self.checkpoints_path_str, check_same_thread=False)
        self.checkpointer = SqliteSaver(self._sqlite_conn)
        self.checkpointer.setup()

        self.store = PersistentSqliteStore(store_path)
        self.summarizer = SummarizationMiddleware(max_tokens=max_context_tokens)

    def get_thread_history_summary(self, thread_id: str, graph: Any) -> dict[str, Any]:
        """Inspecciona el estado actual y el historial de checkpoints (Time Travel) de un hilo."""
        cfg = {"configurable": {"thread_id": thread_id}}
        snapshot = graph.get_state(cfg)
        values = snapshot.values if snapshot and snapshot.values else {}
        raw_messages: list[BaseMessage] = list(values.get("messages", []))

        serialized_messages: list[dict[str, str]] = []
        for msg in raw_messages:
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            else:
                role = "system"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            serialized_messages.append({"role": role, "content": content})

        checkpoints: list[dict[str, Any]] = []
        for idx, state_snap in enumerate(graph.get_state_history(cfg)):
            if idx >= 12:
                break
            cp_id = state_snap.config.get("configurable", {}).get("checkpoint_id", f"cp-{idx}")
            step_msgs = state_snap.values.get("messages", []) if state_snap.values else []
            checkpoints.append(
                {
                    "checkpoint_id": str(cp_id),
                    "messages_count": len(step_msgs),
                    "created_at": str(state_snap.created_at or ""),
                    "last_route": str(state_snap.values.get("route_choice", ""))
                    if state_snap.values
                    else "",
                }
            )

        _, window_report = self.summarizer.process(raw_messages)
        return {
            "thread_id": thread_id,
            "checkpoints_db": self.checkpoints_path_str,
            "messages_count": len(serialized_messages),
            "messages": serialized_messages,
            "context_window": window_report.to_dict(),
            "checkpoints_history": checkpoints,
        }


_DEFAULT_MEMORY_MANAGER: MemoryManager | None = None


def get_memory_manager(*, in_memory: bool = False) -> MemoryManager:
    """Obtiene o crea el gestor persistente de memoria conversacional."""
    global _DEFAULT_MEMORY_MANAGER
    if in_memory:
        return MemoryManager(checkpoints_path=":memory:", store_path=":memory:")
    if _DEFAULT_MEMORY_MANAGER is None:
        _DEFAULT_MEMORY_MANAGER = MemoryManager()
    return _DEFAULT_MEMORY_MANAGER
