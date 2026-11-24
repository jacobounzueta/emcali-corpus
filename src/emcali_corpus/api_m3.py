"""Rutas FastAPI del Módulo 3: IAM/RBAC, 20 Tools, Mapa Cali, PQRS, Fallas, Noticias y HITL."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from emcali_corpus.news_sync import build_daily_newsletter_digest, sync_news_from_gold
from emcali_corpus.ops_db import (
    FailureReportCreateRequest,
    MaintenanceCreateRequest,
    PqrsCreateRequest,
    PqrsStatus,
    ServiceType,
    UserRole,
    get_ops_db,
)
from emcali_corpus.tools_m3 import (
    ALL_20_TOOLS,
    HITL_SENSITIVE_TOOL_NAMES,
    MANAGER_ONLY_TOOL_NAMES,
    describe_tool_catalog,
    execute_tool_with_rbac,
)
from emcali_corpus.umap_diagnostics import compute_umap_diagnostics

router = APIRouter(prefix="/api", tags=["modulo-3-ops"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=2)
    password: str = Field(min_length=2)


class ToolExecuteRequest(BaseModel):
    tool_name: str = Field(min_length=2)
    arguments: dict[str, Any] = Field(default_factory=dict)
    user_id: str = Field(default="ciudadano-cali")
    require_hitl: bool = Field(default=False)


class PqrsStatusUpdateRequest(BaseModel):
    nuevo_estado: PqrsStatus
    notas_gestion: str = Field(default="")


class DispatchCrewRequest(BaseModel):
    barrio: str = Field(min_length=2)
    servicio: ServiceType
    brigada_asignada: str = Field(min_length=3)
    notas: str = Field(default="")


class CloseMaintenanceRequest(BaseModel):
    notas_cierre: str = Field(default="")


class NewsletterSubscribeRequest(BaseModel):
    contacto: str = Field(min_length=5)
    canal: Literal["whatsapp", "web", "telegram"] = Field(default="whatsapp")
    nombre: str = Field(default="")
    barrio_interes: str = Field(default="Todos")
    frecuencia: Literal["diaria", "semanal"] = Field(default="diaria")


class HitlResolveRequest(BaseModel):
    approved: bool


def _resolve_role_and_user(authorization: str | None) -> tuple[UserRole, str]:
    db = get_ops_db()
    session = db.resolve_session_token(authorization)
    if session and session.get("role") == "manager":
        return "manager", str(session["username"])
    if session:
        return "citizen", str(session["username"])
    return "citizen", "ciudadano-publico"


def _require_manager(authorization: str | None) -> str:
    role, username = _resolve_role_and_user(authorization)
    if role != "manager":
        raise HTTPException(
            status_code=403,
            detail=("Acceso denegado (RBAC): se requiere sesión autenticada de Gestión EMCALI."),
        )
    return username


# ---------------------------------------------------------------------------
# IAM / RBAC
# ---------------------------------------------------------------------------


@router.post("/auth/login")
def auth_login(payload: LoginRequest) -> dict[str, Any]:
    db = get_ops_db()
    session = db.authenticate_user(payload.username, payload.password)
    if not session:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    return session


@router.get("/auth/me")
def auth_me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    db = get_ops_db()
    session = db.resolve_session_token(authorization)
    if not session:
        return {
            "authenticated": False,
            "role": "citizen",
            "display_name": "Ciudadano (Acceso Público)",
        }
    return {"authenticated": True, **session}


# ---------------------------------------------------------------------------
# Catálogo y Ejecución de las 20 Herramientas (RBAC + HITL)
# ---------------------------------------------------------------------------


@router.get("/tools/catalog")
def get_tools_catalog() -> dict[str, Any]:
    catalog = describe_tool_catalog()
    return {
        "total_tools": len(ALL_20_TOOLS),
        "citizen_tools_count": len(ALL_20_TOOLS) - len(MANAGER_ONLY_TOOL_NAMES),
        "manager_only_tools_count": len(MANAGER_ONLY_TOOL_NAMES),
        "hitl_protected_tools": sorted(HITL_SENSITIVE_TOOL_NAMES),
        "tools": catalog,
    }


@router.post("/tools/execute")
def execute_catalog_tool(
    payload: ToolExecuteRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    role, username = _resolve_role_and_user(authorization)
    result = execute_tool_with_rbac(
        payload.tool_name,
        payload.arguments,
        role=role,
        user_id=payload.user_id or username,
        require_hitl=payload.require_hitl,
    )
    if not result.get("ok") and result.get("error") == "RBAC_DENIED":
        raise HTTPException(status_code=403, detail=result["message"])
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Tool error"))
    return result


# ---------------------------------------------------------------------------
# Mapa Interactivo de Cali (Mantenimientos Oficiales + Hotspots de Fallas)
# ---------------------------------------------------------------------------


@router.get("/map/overview")
def get_cali_map_overview(
    servicio: str = "todos",
    solo_activos: bool = True,
) -> dict[str, Any]:
    db = get_ops_db()
    maint = db.list_maintenance_points(servicio=servicio, solo_activos=solo_activos)
    hotspots = db.get_failure_hotspots(servicio=servicio)
    failures = db.list_failure_reports(servicio=servicio, limit=100)
    return {
        "center": {"lat": 3.4516, "lng": -76.5320, "zoom": 12},
        "maintenances_count": len(maint),
        "hotspots_count": len(hotspots),
        "open_failures_count": len([f for f in failures if f["estado"] != "Resuelto"]),
        "maintenances": maint,
        "failure_hotspots": hotspots,
        "failure_reports": failures,
    }


# ---------------------------------------------------------------------------
# PQRS y Reportes de Fallas (Contrato o Cédula)
# ---------------------------------------------------------------------------


@router.post("/pqrs")
def create_pqrs_endpoint(payload: PqrsCreateRequest) -> dict[str, Any]:
    db = get_ops_db()
    return {"status": "radicado", "ticket": db.create_pqrs(payload)}


@router.get("/pqrs")
def list_pqrs_endpoint(
    identificador_valor: str | None = None,
    servicio: str | None = None,
    estado: str | None = None,
) -> dict[str, Any]:
    db = get_ops_db()
    items = db.list_pqrs(
        identificador_valor=identificador_valor,
        servicio=servicio,
        estado=estado,
    )
    return {"count": len(items), "items": items}


@router.patch("/pqrs/{radicado_id}")
def update_pqrs_endpoint(
    radicado_id: str,
    payload: PqrsStatusUpdateRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_manager(authorization)
    db = get_ops_db()
    updated = db.update_pqrs_status(
        radicado_id,
        nuevo_estado=payload.nuevo_estado,
        notas_gestion=payload.notas_gestion,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Radicado {radicado_id} no encontrado.")
    return {"status": "updated", "ticket": updated}


@router.post("/failures")
def create_failure_endpoint(payload: FailureReportCreateRequest) -> dict[str, Any]:
    db = get_ops_db()
    return {"status": "reported", "report": db.create_failure_report(payload)}


@router.get("/failures")
def list_failures_endpoint(
    servicio: str | None = None,
    barrio: str | None = None,
) -> dict[str, Any]:
    db = get_ops_db()
    reports = db.list_failure_reports(servicio=servicio, barrio=barrio)
    hotspots = db.get_failure_hotspots(servicio=servicio)
    return {"count": len(reports), "hotspots": hotspots, "items": reports}


# ---------------------------------------------------------------------------
# Mantenimientos Oficiales & Despacho de Brigadas (Manager Only)
# ---------------------------------------------------------------------------


@router.post("/maintenances")
def create_maintenance_endpoint(
    payload: MaintenanceCreateRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    username = _require_manager(authorization)
    db = get_ops_db()
    enriched = payload.model_copy(update={"created_by": username, "fuente": "gestion_emcali"})
    return {"status": "activated", "maintenance": db.create_maintenance_point(enriched)}


@router.post("/maintenances/dispatch")
def dispatch_crew_endpoint(
    payload: DispatchCrewRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    username = _require_manager(authorization)
    db = get_ops_db()
    maint = db.dispatch_crew_for_hotspot(
        barrio=payload.barrio,
        servicio=payload.servicio,
        brigada_asignada=payload.brigada_asignada,
        notas=payload.notas,
        created_by=username,
    )
    return {"status": "dispatched", "maintenance": maint}


@router.patch("/maintenances/{mantenimiento_id}/close")
def close_maintenance_endpoint(
    mantenimiento_id: str,
    payload: CloseMaintenanceRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_manager(authorization)
    db = get_ops_db()
    closed = db.close_maintenance_point(mantenimiento_id, notas_cierre=payload.notas_cierre)
    if not closed:
        raise HTTPException(status_code=404, detail="Punto de mantenimiento no encontrado.")
    return {"status": "closed", "maintenance": closed}


# ---------------------------------------------------------------------------
# Noticias, Sincronización Diaria y Boletín OpenClaw
# ---------------------------------------------------------------------------


@router.get("/news")
def list_news_endpoint(
    query: str = "",
    solo_mantenimientos: bool = False,
    limit: int = 15,
) -> dict[str, Any]:
    db = get_ops_db()
    if not db.list_news(limit=1):
        sync_news_from_gold(db)
    items = db.list_news(query=query, solo_mantenimientos=solo_mantenimientos, limit=limit)
    return {"count": len(items), "items": items}


@router.post("/news/sync")
def sync_news_endpoint(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_manager(authorization)
    db = get_ops_db()
    return {"status": "synced", **sync_news_from_gold(db)}


@router.get("/newsletter/digest")
def newsletter_digest_endpoint(barrio: str | None = None) -> dict[str, Any]:
    db = get_ops_db()
    if not db.list_news(limit=1):
        sync_news_from_gold(db)
    return build_daily_newsletter_digest(db, barrio=barrio)


@router.post("/newsletter/subscribe")
def newsletter_subscribe_endpoint(payload: NewsletterSubscribeRequest) -> dict[str, Any]:
    db = get_ops_db()
    sub = db.subscribe_newsletter(
        contacto=payload.contacto,
        canal=payload.canal,
        nombre=payload.nombre,
        barrio_interes=payload.barrio_interes,
        frecuencia=payload.frecuencia,
    )
    return {"status": "subscribed", "subscriber": sub}


# ---------------------------------------------------------------------------
# HITL (Human-in-the-Loop) & Resumen Ejecutivo
# ---------------------------------------------------------------------------


@router.get("/hitl/pending")
def list_hitl_pending() -> dict[str, Any]:
    db = get_ops_db()
    items = db.list_hitl_actions(status="pending")
    return {"count": len(items), "items": items}


@router.post("/hitl/{action_id}/resolve")
def resolve_hitl_endpoint(
    action_id: str,
    payload: HitlResolveRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    db = get_ops_db()
    pending = [a for a in db.list_hitl_actions(status="pending") if a["action_id"] == action_id]
    if not pending:
        raise HTTPException(status_code=404, detail="Acción HITL pendiente no encontrada.")
    action = pending[0]
    role, _ = _resolve_role_and_user(authorization)
    if action["tool_name"] in MANAGER_ONLY_TOOL_NAMES and role != "manager":
        raise HTTPException(
            status_code=403,
            detail="Solo un usuario de Gestión EMCALI puede aprobar esta acción HITL.",
        )

    exec_result: dict[str, Any] = {}
    if payload.approved:
        exec_result = execute_tool_with_rbac(
            str(action["tool_name"]),
            dict(action["payload"]),
            role="manager" if action["tool_name"] in MANAGER_ONLY_TOOL_NAMES else role,
            user_id=str(action["user_id"]),
            require_hitl=False,
        )
    resolved = db.resolve_hitl_action(action_id, approved=payload.approved, result=exec_result)
    return {"status": "resolved", "action": resolved}


@router.get("/ops/summary")
def ops_executive_summary(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_manager(authorization)
    db = get_ops_db()
    return db.executive_summary()


@router.get("/evaluation/umap")
def get_umap_projection(refresh: bool = False) -> dict[str, Any]:
    """Devuelve la proyección UMAP 2D del corpus EMCALI + consultas + PQRS/Fallas."""
    return compute_umap_diagnostics(force_refresh=refresh)
