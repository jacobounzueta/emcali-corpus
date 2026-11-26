"""Servidor MCP propio (FastMCP) que expone las 20 herramientas de EMCALI hacia OpenClaw."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from mcp.server import MCPServer

from emcali_corpus.news_sync import build_daily_newsletter_digest, sync_news_from_gold
from emcali_corpus.ops_db import UserRole, get_ops_db
from emcali_corpus.tools_m3 import (
    ALL_20_TOOLS,
    describe_tool_catalog,
    execute_tool_with_rbac,
)

load_dotenv()

mcp = MCPServer(
    "emcali-eder-mcp",
    instructions=(
        "Servidor MCP oficial de Mile, asistente virtual de EMCALI E.I.C.E. E.S.P. "
        "Expone 20 herramientas tipadas con Pydantic v2, RBAC (citizen vs. manager), "
        "HITL para acciones sensibles, mapa de Cali y RAG híbrido sobre Qdrant."
    ),
)


def _resolve_role(phone_e164: str = "", explicit_role: str = "") -> UserRole:
    if explicit_role == "manager":
        return "manager"
    if phone_e164:
        return get_ops_db().resolve_role_by_phone(phone_e164)
    env_role = os.getenv("EMCALI_MCP_DEFAULT_ROLE", "citizen").strip().lower()
    return "manager" if env_role == "manager" else "citizen"


@mcp.tool()
def listar_catalogo_20_herramientas() -> dict[str, Any]:
    """Devuelve el catálogo completo de las 20 herramientas EMCALI y sus políticas RBAC."""
    return {"total_tools": len(ALL_20_TOOLS), "tools": describe_tool_catalog()}


@mcp.tool()
def verificar_identidad_rbac_whatsapp(phone_e164: str) -> dict[str, Any]:
    """Consulta en IAM/RBAC el usuario y rol (manager/citizen) de un número WhatsApp."""
    db = get_ops_db()
    normalized = db._normalize_phone_e164(phone_e164)
    role = db.resolve_role_by_phone(normalized)
    user = db.lookup_user_by_phone(normalized)
    return {
        "phone_e164": normalized or phone_e164,
        "role": role,
        "is_manager": role == "manager",
        "rbac_user": user,
        "manager_tools_enabled": role == "manager",
    }


@mcp.tool()
def ejecutar_herramienta_emcali(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    phone_e164: str = "",
    role: str = "",
    require_hitl: bool = True,
) -> dict[str, Any]:
    """Ejecuta cualquiera de las 20 herramientas EMCALI aplicando RBAC (tools.deny) y HITL."""
    resolved_role = _resolve_role(phone_e164=phone_e164, explicit_role=role)
    return execute_tool_with_rbac(
        tool_name,
        arguments or {},
        role=resolved_role,
        user_id=phone_e164 or f"openclaw-{resolved_role}",
        require_hitl=require_hitl,
    )


@mcp.tool()
def generar_boletin_diario_emcali(
    barrio: str = "",
    sincronizar_primero: bool = False,
) -> dict[str, Any]:
    """Genera el boletín diario de noticias y mantenimientos de EMCALI para difusión en WhatsApp."""
    db = get_ops_db()
    sync_info = sync_news_from_gold(db) if sincronizar_primero else None
    digest = build_daily_newsletter_digest(db, barrio=barrio or None)
    if sync_info is not None:
        digest["sync_info"] = sync_info
    return digest


# Registrar también las 20 herramientas individuales directamente en el servidor MCP
def _register_all_20_tools() -> None:
    for lc_tool in ALL_20_TOOLS:
        tool_name = lc_tool.name
        base_desc = (lc_tool.description or f"Herramienta EMCALI {tool_name}").strip()
        args_schema = lc_tool.args_schema
        schema_fn = getattr(args_schema, "model_json_schema", None)
        schema = (
            schema_fn()
            if callable(schema_fn)
            else (args_schema if isinstance(args_schema, dict) else {})
        )
        props = schema.get("properties", {})
        req_fields = set(schema.get("required", []))
        if props:
            arg_hints = ", ".join(f"{k}{'*' if k in req_fields else ''}" for k in props)
            tool_desc = f"{base_desc} | arguments keys: {arg_hints}"
        else:
            tool_desc = base_desc

        def _make_handler(name: str) -> Any:
            def _handler(
                arguments: dict[str, Any] | None = None,
                phone_e164: str = "",
                require_hitl: bool = False,
            ) -> dict[str, Any]:
                resolved_role = _resolve_role(phone_e164=phone_e164)
                return execute_tool_with_rbac(
                    name,
                    arguments or {},
                    role=resolved_role,
                    user_id=phone_e164 or f"openclaw-{resolved_role}",
                    require_hitl=require_hitl,
                )

            _handler.__name__ = name
            return _handler

        mcp.tool(name=tool_name, description=tool_desc)(_make_handler(tool_name))


_register_all_20_tools()


def main() -> None:
    """Punto de entrada stdio para conectar OpenClaw con emcali-eder-mcp."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
