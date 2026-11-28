"""Rutas FastAPI del Módulo 3: IAM/RBAC, 20 Tools, Mapa Cali, PQRS, Fallas, Noticias y HITL."""

from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from emcali_corpus.news_sync import (
    build_daily_newsletter_digest,
    sync_live_emcali_news,
    sync_news_from_gold,
)
from emcali_corpus.ops_db import (
    FailureReportCreateRequest,
    FailureStatus,
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


class CitizenRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    phone_e164: str = Field(default="", max_length=20)


class ToolExecuteRequest(BaseModel):
    tool_name: str = Field(min_length=2)
    arguments: dict[str, Any] = Field(default_factory=dict)
    user_id: str = Field(default="ciudadano-cali")
    require_hitl: bool = Field(default=False)


class PqrsStatusUpdateRequest(BaseModel):
    nuevo_estado: PqrsStatus
    notas_gestion: str = Field(default="")


class FailureStatusUpdateRequest(BaseModel):
    nuevo_estado: FailureStatus
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


class UserRbacUpsertRequest(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    display_name: str = Field(min_length=2, max_length=120)
    role: UserRole = "citizen"
    password: str | None = Field(default=None)
    phone_e164: str = Field(default="")
    department: str = Field(default="")
    active: bool = True


class WhatsAppAllowlistRequest(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=20)


_E164_RE = re.compile(r"^\+\d{8,15}$")
OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"


def _read_whatsapp_allowlist() -> list[str]:
    if not OPENCLAW_CONFIG_PATH.is_file():
        return []
    raw = json.loads(OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
    allow = raw.get("channels", {}).get("whatsapp", {}).get("allowFrom", [])
    return [str(p) for p in allow if str(p).strip()]


def _openclaw_env() -> dict[str, str]:
    """Construye el entorno con XDG_RUNTIME_DIR/DBUS para operar OpenClaw desde systemd."""
    env = dict(os.environ)
    getuid = getattr(os, "getuid", None)
    if callable(getuid):
        uid = getuid()
        xdg = env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
        env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={xdg}/bus")
    return env


def _reload_openclaw_whatsapp_sync() -> bool:
    """Reinicia el gateway OpenClaw inmediatamente para aplicar cambios de allowFrom."""
    env = _openclaw_env()
    for cmd in (
        ["openclaw", "gateway", "restart"],
        ["systemctl", "--user", "restart", "openclaw-gateway.service"],
    ):
        try:
            res = subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=12,
                check=False,
            )
            if res.returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


def _send_whatsapp_notifications_async(phones: list[str], message: str) -> int:
    """Envía notificaciones proactivas por WhatsApp (Meta Cloud API si está activa, o OpenClaw)."""
    sent = 0
    meta_token = os.getenv("META_WHATSAPP_ACCESS_TOKEN", "").strip()
    meta_phone_id = os.getenv("META_WHATSAPP_PHONE_NUMBER_ID", "").strip()
    if meta_token and meta_phone_id:
        import threading

        import requests

        def _send_meta(target_digits: str) -> None:
            with contextlib.suppress(requests.RequestException):
                requests.post(
                    f"https://graph.facebook.com/v21.0/{meta_phone_id}/messages",
                    headers={
                        "Authorization": f"Bearer {meta_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": target_digits,
                        "type": "text",
                        "text": {"body": message[:4000]},
                    },
                    timeout=15,
                )

        for phone in phones:
            digits = "".join(ch for ch in phone if ch.isdigit())
            if len(digits) < 8:
                continue
            threading.Thread(target=_send_meta, args=(digits,), daemon=True).start()
            sent += 1
        return sent

    env = _openclaw_env()
    for phone in phones:
        clean = phone.strip()
        if not _E164_RE.match(clean):
            continue
        with contextlib.suppress(OSError):
            subprocess.Popen(
                [
                    "openclaw",
                    "message",
                    "send",
                    "--channel",
                    "whatsapp",
                    "--target",
                    clean,
                    "--message",
                    message,
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            sent += 1
    return sent


def _write_whatsapp_allowlist(numbers: list[str]) -> list[str]:
    cleaned = sorted(dict.fromkeys(numbers))
    if OPENCLAW_CONFIG_PATH.is_file():
        raw = json.loads(OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
        raw.setdefault("channels", {}).setdefault("whatsapp", {})["allowFrom"] = cleaned
        OPENCLAW_CONFIG_PATH.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _reload_openclaw_whatsapp_sync()
    return cleaned


def _ensure_phone_in_whatsapp_allowlist(
    phone_e164: str,
    *,
    display_name: str = "",
    send_welcome: bool = True,
) -> tuple[bool, list[str]]:
    """Agrega un teléfono al allowFrom de OpenClaw, recarga el gateway y envía saludo inicial."""
    db = get_ops_db()
    clean = db._normalize_phone_e164(phone_e164)
    if not clean or not _E164_RE.match(clean):
        return False, _read_whatsapp_allowlist()
    nums = _read_whatsapp_allowlist()
    added = clean not in nums
    if added:
        nums.append(clean)
        updated = _write_whatsapp_allowlist(nums)
        if send_welcome and OPENCLAW_CONFIG_PATH.is_file():
            saludo_nombre = f" {display_name.strip()}" if display_name.strip() else ""
            _send_whatsapp_notifications_async(
                [clean],
                (
                    f"¡Hola{saludo_nombre}, vecino! Soy Doña Melva, tu asistente virtual de "
                    "EMCALI 👋. Ya quedaste habilitado por aquí en WhatsApp; vea pues, cuando "
                    "necesites revisar tarifas, mantenimientos en tu barrio, radicar una PQRS o "
                    "reportar alguna falla en Cali, me escribes con toda confianza."
                ),
            )
        return True, updated
    return False, nums


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


@router.post("/auth/register")
def auth_register(payload: CitizenRegisterRequest) -> dict[str, Any]:
    """Auto-registro público: siempre crea rol 'citizen' (nunca escala privilegios a manager)."""
    db = get_ops_db()
    clean_user = payload.username.strip().lower()
    existing = [u for u in db.list_users_rbac() if u["username"] == clean_user]
    if existing:
        raise HTTPException(status_code=409, detail="Ese nombre de usuario ya está registrado.")
    phone = db._normalize_phone_e164(payload.phone_e164) if payload.phone_e164.strip() else ""
    if phone and not _E164_RE.match(phone):
        raise HTTPException(
            status_code=400,
            detail="El teléfono debe estar en formato E.164 (ej. +573001234567).",
        )
    try:
        db.upsert_user_rbac(
            username=clean_user,
            display_name=payload.display_name.strip(),
            role="citizen",
            password=payload.password,
            phone_e164=phone,
            department="Ciudadano Registrado",
            active=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    whatsapp_added = False
    if phone:
        whatsapp_added, _ = _ensure_phone_in_whatsapp_allowlist(
            phone,
            display_name=payload.display_name,
        )
    session = db.authenticate_user(clean_user, payload.password)
    if not session:
        raise HTTPException(status_code=500, detail="No fue posible iniciar sesión tras registro.")
    return {**session, "whatsapp_allowlisted": bool(phone), "whatsapp_newly_added": whatsapp_added}


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
    try:
        return {"status": "radicado", "ticket": db.create_pqrs(payload)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    notified = 0
    phone = db._normalize_phone_e164(str(updated.get("telefono_e164", "")))
    if phone:
        nota_txt = (
            f"\n• Respuesta / Nota de Gestión: {updated['notas_gestion']}"
            if updated.get("notas_gestion")
            else ""
        )
        msg = (
            "📋 *Actualización de PQRS — EMCALI*\n"
            f"Tu solicitud `{updated['radicado_id']}` ({updated['tipo']} · "
            f"*{str(updated['servicio']).upper()}* en *{updated['barrio']}*) "
            f"cambió a estado: *{updated['estado']}*.{nota_txt}\n"
            "Si necesitas seguimiento adicional, me escribes con confianza por aquí. "
            "— Doña Melva 👋"
        )
        notified = _send_whatsapp_notifications_async([phone], msg)
    return {"status": "updated", "ticket": updated, "whatsapp_notified": bool(notified)}


@router.post("/failures")
def create_failure_endpoint(payload: FailureReportCreateRequest) -> dict[str, Any]:
    db = get_ops_db()
    try:
        return {"status": "reported", "report": db.create_failure_report(payload)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/failures")
def list_failures_endpoint(
    servicio: str | None = None,
    barrio: str | None = None,
) -> dict[str, Any]:
    db = get_ops_db()
    reports = db.list_failure_reports(servicio=servicio, barrio=barrio)
    hotspots = db.get_failure_hotspots(servicio=servicio)
    return {"count": len(reports), "hotspots": hotspots, "items": reports}


@router.patch("/failures/{reporte_id}")
def update_failure_endpoint(
    reporte_id: str,
    payload: FailureStatusUpdateRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_manager(authorization)
    db = get_ops_db()
    updated = db.update_failure_report_status(
        reporte_id,
        nuevo_estado=payload.nuevo_estado,
        notas_gestion=payload.notas_gestion,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Reporte {reporte_id} no encontrado.")
    notified = 0
    phone = db._normalize_phone_e164(str(updated.get("telefono_e164", "")))
    if phone:
        nota_txt = (
            f"\n• Respuesta / Nota Técnica: {updated['notas_gestion']}"
            if updated.get("notas_gestion")
            else ""
        )
        msg = (
            "🛠️ *Actualización de Reporte de Falla — EMCALI*\n"
            f"Tu reporte `{updated['reporte_id']}` (*{str(updated['servicio']).upper()}* "
            f"en *{updated['barrio']}*) pasó a estado: *{updated['estado']}*.{nota_txt}\n"
            "¡Gracias por avisarnos, vecino! Cualquier novedad me escribes por aquí. "
            "— Doña Melva 👋"
        )
        notified = _send_whatsapp_notifications_async([phone], msg)
    return {"status": "updated", "report": updated, "whatsapp_notified": bool(notified)}


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
    try:
        return {"status": "activated", "maintenance": db.create_maintenance_point(enriched)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/maintenances/dispatch")
def dispatch_crew_endpoint(
    payload: DispatchCrewRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    username = _require_manager(authorization)
    db = get_ops_db()
    try:
        maint = db.dispatch_crew_for_hotspot(
            barrio=payload.barrio,
            servicio=payload.servicio,
            brigada_asignada=payload.brigada_asignada,
            notas=payload.notas,
            created_by=username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    phones = list(maint.get("notifiable_phones", []))
    notified = 0
    if phones:
        public_url = os.getenv("EMCALI_PUBLIC_URL", "https://172-183-55-204.sslip.io").rstrip("/")
        msg = (
            "🚑 *Actualización EMCALI — Brigada Despachada*\n"
            f"Se activó atención prioritaria de *{maint['servicio'].upper()}* "
            f"en *{maint['barrio']}* ({maint['comuna']}).\n"
            f"• Radicado de mantenimiento: `{maint['mantenimiento_id']}`\n"
            f"• Brigada asignada: *{maint['brigada_asignada']}*\n"
            f"• Fecha y hora: `{maint['inicio_estimado']}`\n"
            f"Puedes seguir el estado en vivo en {public_url}"
        )
        notified = _send_whatsapp_notifications_async(phones, msg)
    maint["whatsapp_notifications_queued"] = notified
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
    refresh: bool = False,
) -> dict[str, Any]:
    db = get_ops_db()
    sync_summary: dict[str, Any] | None = None
    if refresh:
        with contextlib.suppress(Exception):
            sync_summary = sync_live_emcali_news(db)
    if not db.list_news(limit=1):
        sync_news_from_gold(db)
    items = db.list_news(query=query, solo_mantenimientos=solo_mantenimientos, limit=limit)
    return {"count": len(items), "items": items, "sync": sync_summary}


@router.post("/news/sync")
def sync_news_endpoint(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_manager(authorization)
    db = get_ops_db()
    gold_res = sync_news_from_gold(db)
    live_res: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        live_res = sync_live_emcali_news(db)
    return {"status": "synced", **gold_res, **live_res}


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


# ---------------------------------------------------------------------------
# Administración IAM (Usuarios RBAC) y Allowlist WhatsApp (Manager Only)
# ---------------------------------------------------------------------------


@router.get("/admin/users")
def admin_list_users(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_manager(authorization)
    db = get_ops_db()
    items = db.list_users_rbac()
    return {"count": len(items), "items": items}


@router.post("/admin/users")
def admin_upsert_user(
    payload: UserRbacUpsertRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_manager(authorization)
    db = get_ops_db()
    try:
        user = db.upsert_user_rbac(
            username=payload.username,
            display_name=payload.display_name,
            role=payload.role,
            password=payload.password,
            phone_e164=payload.phone_e164,
            department=payload.department,
            active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    whatsapp_added = False
    if payload.active and payload.phone_e164.strip():
        whatsapp_added, _ = _ensure_phone_in_whatsapp_allowlist(
            payload.phone_e164,
            display_name=payload.display_name,
        )
    return {"status": "saved", "user": user, "whatsapp_newly_added": whatsapp_added}


@router.get("/admin/whatsapp/allowlist")
def admin_get_whatsapp_allowlist(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_manager(authorization)
    nums = _read_whatsapp_allowlist()
    return {
        "config_found": OPENCLAW_CONFIG_PATH.is_file(),
        "count": len(nums),
        "allowFrom": nums,
    }


@router.post("/admin/whatsapp/allowlist")
def admin_add_whatsapp_allowlist(
    payload: WhatsAppAllowlistRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_manager(authorization)
    db = get_ops_db()
    phone = db._normalize_phone_e164(payload.phone_e164)
    if not _E164_RE.match(phone):
        raise HTTPException(
            status_code=400,
            detail="El número debe estar en formato E.164 (ej. +573183775357).",
        )
    added, updated = _ensure_phone_in_whatsapp_allowlist(phone)
    if not added and OPENCLAW_CONFIG_PATH.is_file():
        _reload_openclaw_whatsapp_sync()
    return {"status": "added", "phone_e164": phone, "allowFrom": updated}


@router.delete("/admin/whatsapp/allowlist/{phone_e164}")
def admin_remove_whatsapp_allowlist(
    phone_e164: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_manager(authorization)
    nums = [n for n in _read_whatsapp_allowlist() if n != phone_e164.strip()]
    updated = _write_whatsapp_allowlist(nums)
    return {"status": "removed", "phone_e164": phone_e164, "allowFrom": updated}


class WhatsAppPolicyRequest(BaseModel):
    dm_policy: Literal["open", "allowlist"]


@router.get("/admin/whatsapp/policy")
def admin_get_whatsapp_policy(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_manager(authorization)
    policy = "allowlist"
    allow_from: list[str] = []
    if OPENCLAW_CONFIG_PATH.is_file():
        raw = json.loads(OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
        wa = raw.get("channels", {}).get("whatsapp", {})
        policy = str(wa.get("dmPolicy", "allowlist"))
        allow_from = [str(x) for x in wa.get("allowFrom", [])]
    return {"dm_policy": policy, "allowFrom": allow_from}


@router.post("/admin/whatsapp/policy")
def admin_set_whatsapp_policy(
    payload: WhatsAppPolicyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_manager(authorization)
    if OPENCLAW_CONFIG_PATH.is_file():
        raw = json.loads(OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
        wa = raw.setdefault("channels", {}).setdefault("whatsapp", {})
        wa["dmPolicy"] = payload.dm_policy
        if payload.dm_policy == "open":
            wa["allowFrom"] = ["*"]
        else:
            existing = [str(x) for x in wa.get("allowFrom", []) if str(x).strip() != "*"]
            wa["allowFrom"] = sorted(dict.fromkeys(existing))
        OPENCLAW_CONFIG_PATH.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _reload_openclaw_whatsapp_sync()
    return {"status": "updated", "dm_policy": payload.dm_policy}


_WA_SENDER_RE = re.compile(r"(\+\d{8,15})")


def _read_openclaw_whatsapp_interactions(limit: int = 80) -> list[dict[str, Any]]:
    """Lee en modo solo-lectura las conversaciones de WhatsApp desde openclaw-agent.sqlite."""
    agent_db = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "openclaw-agent.sqlite"
    if not agent_db.is_file():
        return []
    interactions: list[dict[str, Any]] = []
    try:
        conn = sqlite3.connect(f"file:{agent_db}?mode=ro", uri=True, timeout=3.0)
        rows = conn.execute(
            """
            SELECT te.session_id, te.seq, te.created_at, te.event_json
            FROM transcript_events te
            JOIN session_windows sw ON sw.session_id = te.session_id
            WHERE sw.channel = 'whatsapp'
            ORDER BY te.created_at ASC
            """
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        return []

    pending_user: dict[str, Any] | None = None
    last_known_sender = "whatsapp-ciudadano"
    for sess_id, seq, created_ms, raw_json in rows:
        try:
            ev = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        if ev.get("type") != "message":
            continue
        msg = ev.get("message") or {}
        role = str(msg.get("role", ""))
        ts = str(ev.get("timestamp") or "")
        content = msg.get("content")
        if role == "user":
            if isinstance(content, str):
                text = content.strip()
            elif isinstance(content, list):
                text = " ".join(
                    str(c.get("text", ""))
                    for c in content
                    if isinstance(c, dict) and c.get("type") == "text"
                ).strip()
            else:
                text = ""
            m_phone = _WA_SENDER_RE.search(raw_json)
            if m_phone:
                last_known_sender = m_phone.group(1)
            if text:
                pending_user = {
                    "trace_id": f"WA-{str(sess_id)[:6]}-{seq}",
                    "channel": "whatsapp",
                    "user_id": last_known_sender,
                    "user_role": "whatsapp",
                    "thread_id": str(sess_id),
                    "question": text,
                    "created_at": ts,
                    "created_ms": int(created_ms or 0),
                }
        elif role == "assistant" and pending_user is not None:
            ans_parts: list[str] = []
            thinking_parts: list[str] = []
            tools_used: list[str] = []
            if isinstance(content, str):
                ans_parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text" and block.get("text"):
                        ans_parts.append(str(block["text"]))
                    elif btype == "thinking" and block.get("thinking"):
                        thinking_parts.append(str(block["thinking"]))
                        m_phone = _WA_SENDER_RE.search(str(block["thinking"]))
                        if m_phone:
                            pending_user["user_id"] = m_phone.group(1)
                            last_known_sender = m_phone.group(1)
                    elif btype in {"toolCall", "tool_use"} and block.get("name"):
                        tools_used.append(str(block["name"]))
            ans_text = "\n".join(ans_parts).strip()
            if ans_text:
                lat_ms = max(0, int(created_ms or 0) - int(pending_user.get("created_ms", 0)))
                interactions.append(
                    {
                        "trace_id": pending_user["trace_id"],
                        "channel": "whatsapp",
                        "user_id": pending_user["user_id"],
                        "user_role": "whatsapp",
                        "thread_id": pending_user["thread_id"],
                        "route": "openclaw_mcp",
                        "tools_used": tools_used,
                        "latency_ms": lat_ms if lat_ms < 120_000 else 0,
                        "question": pending_user["question"],
                        "answer": ans_text,
                        "thinking": "\n".join(thinking_parts).strip(),
                        "created_at": ts or pending_user["created_at"],
                    }
                )
                pending_user = None

    interactions.reverse()
    return interactions[:limit]


@router.get("/admin/interactions")
def admin_list_interactions(
    channel: str = "todos",
    user: str = "todos",
    limit: int = 80,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Panel de observabilidad tipo LangSmith: trazas unificadas de Web y WhatsApp por usuario."""
    _require_manager(authorization)
    db = get_ops_db()
    web_items = (
        db.list_interaction_traces(channel="web", user_id=None, limit=limit)
        if channel in {"todos", "web"}
        else []
    )
    wa_items = (
        _read_openclaw_whatsapp_interactions(limit=limit)
        if channel in {"todos", "whatsapp"}
        else []
    )
    merged = [*web_items, *wa_items]
    merged.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)

    all_users = sorted({str(x.get("user_id", "anonimo")) for x in merged})
    if user and user != "todos":
        needle = user.strip().lower()
        merged = [x for x in merged if needle in str(x.get("user_id", "")).lower()]

    merged = merged[:limit]
    latencies = [int(x.get("latency_ms", 0)) for x in merged if int(x.get("latency_ms", 0)) > 0]
    tool_counts: dict[str, int] = {}
    for item in merged:
        for tool_name in item.get("tools_used", []):
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    return {
        "kpis": {
            "total_interactions": len(merged),
            "web_interactions": sum(1 for x in merged if x.get("channel") == "web"),
            "whatsapp_interactions": sum(1 for x in merged if x.get("channel") == "whatsapp"),
            "unique_users": len({str(x.get("user_id", "")) for x in merged}),
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
            "top_tools": sorted(tool_counts.items(), key=lambda kv: kv[1], reverse=True)[:8],
        },
        "users": all_users,
        "items": merged,
    }


# ---------------------------------------------------------------------------
# Meta WhatsApp Cloud API Webhook (Canal Paralelo Oficial sin tocar eSIM)
# ---------------------------------------------------------------------------


@router.get("/whatsapp/meta-webhook")
def meta_whatsapp_webhook_verify(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> PlainTextResponse:
    """Handshake oficial de verificación de Webhook para Meta Developers (WhatsApp Cloud API)."""
    expected = os.getenv("META_WHATSAPP_VERIFY_TOKEN", "emcali-melva-meta-2026").strip()
    if hub_mode == "subscribe" and hub_verify_token == expected:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verify token de Meta WhatsApp inválido.")


@router.post("/whatsapp/meta-webhook")
async def meta_whatsapp_webhook_receive(request: Request) -> dict[str, Any]:
    """Recibe mensajes de WhatsApp Cloud API (Meta Developers) y responde con Doña Melva."""
    import time

    import requests

    from emcali_corpus.agent_graph import get_conversational_agent

    payload = await request.json()
    access_token = os.getenv("META_WHATSAPP_ACCESS_TOKEN", "").strip()
    default_phone_id = os.getenv("META_WHATSAPP_PHONE_NUMBER_ID", "").strip()
    db = get_ops_db()
    processed = 0

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            phone_number_id = str(metadata.get("phone_number_id") or default_phone_id).strip()
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                sender = str(msg.get("from", "")).strip()
                text = str((msg.get("text") or {}).get("body", "")).strip()
                if not sender or not text:
                    continue

                t0 = time.perf_counter()
                phone_e164 = f"+{sender}" if sender.isdigit() else sender
                role = db.resolve_role_by_phone(phone_e164)
                agent = get_conversational_agent()
                turn = agent.invoke_turn(
                    text,
                    thread_id=f"meta-wa-{sender}",
                    user_id=phone_e164,
                    user_role=role,
                    use_llm=True,
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                turn_dict = turn.to_dict()
                router_choice = str((turn_dict.get("router") or {}).get("choice", ""))
                tools_used = [
                    str(r.get("tool", r.get("name", "")))
                    for r in (turn_dict.get("structured_reports") or [])
                    if isinstance(r, dict)
                ]
                db.log_interaction_trace(
                    channel="whatsapp",
                    user_id=phone_e164,
                    user_role=role,
                    thread_id=f"meta-wa-{sender}",
                    route=router_choice,
                    tools_used=tools_used,
                    latency_ms=latency_ms,
                    question=text,
                    answer=turn.answer,
                    thinking=turn.reasoning,
                )

                if access_token and phone_number_id:
                    with contextlib.suppress(requests.RequestException):
                        requests.post(
                            f"https://graph.facebook.com/v21.0/{phone_number_id}/messages",
                            headers={
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "text",
                                "text": {"body": turn.answer[:4000]},
                            },
                            timeout=15,
                        )
                processed += 1

    return {"status": "ok", "processed": processed}
