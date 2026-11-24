"""Base de datos operativa SQLite para PQRS, fallas, mantenimientos, boletines, RBAC y HITL."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from emcali_corpus import config
from emcali_corpus.cali_geo import try_resolve_cali_location

OPS_DIR = config.DATA_DIR / "ops"
OPS_DB_PATH = OPS_DIR / "emcali_ops.sqlite"

UserRole = Literal["citizen", "manager"]
ServiceType = Literal["energia", "acueducto", "alcantarillado", "telco_fibra"]
IdentifierType = Literal["contrato", "cedula"]
PqrsType = Literal["Petición", "Queja", "Reclamo", "Sugerencia"]
PqrsStatus = Literal["Radicado", "En gestión", "Escalado", "Resuelto", "Cerrado"]
MaintenanceStatus = Literal["Activo", "En ejecución", "Finalizado"]
FailureStatus = Literal["Reportado", "Agrupado en alerta", "Brigada asignada", "Resuelto"]


def utc_now_iso() -> str:
    """Devuelve timestamp ISO-8601 en UTC."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _hash_secret(secret: str, *, salt: str | None = None) -> str:
    use_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        use_salt.encode("utf-8"),
        120_000,
    ).hex()
    return f"pbkdf2_sha256${use_salt}${digest}"


def _verify_secret(secret: str, stored_hash: str) -> bool:
    try:
        scheme, salt, expected = stored_hash.split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    candidate = _hash_secret(secret, salt=salt).split("$", 2)[2]
    return hmac.compare_digest(candidate, expected)


class PqrsCreateRequest(BaseModel):
    """Esquema Pydantic v2 para radicar una PQRS (cliente por contrato o no-cliente por cédula)."""

    tipo: PqrsType = Field(description="Tipo de solicitud: Petición, Queja, Reclamo o Sugerencia.")
    servicio: ServiceType = Field(
        description="Servicio asociado: energia, acueducto, alcantarillado o telco_fibra."
    )
    identificador_tipo: IdentifierType = Field(
        description="'contrato' para suscriptores EMCALI o 'cedula' para no clientes."
    )
    identificador_valor: str = Field(
        min_length=5,
        max_length=20,
        description="Número de contrato (suscriptor) o número de cédula (no cliente).",
    )
    nombre_ciudadano: str = Field(min_length=2, max_length=120)
    barrio: str = Field(min_length=2, max_length=100)
    descripcion: str = Field(min_length=10, max_length=1500)
    telefono_e164: str = Field(
        default="",
        description="Teléfono en formato E.164 opcional (ej. +573001234567).",
    )

    @model_validator(mode="after")
    def validate_identifier_digits(self) -> PqrsCreateRequest:
        digits = "".join(ch for ch in self.identificador_valor if ch.isdigit())
        if len(digits) < 5:
            raise ValueError(
                f"El campo {self.identificador_tipo} debe contener al menos 5 dígitos numéricos."
            )
        self.identificador_valor = digits
        return self


class FailureReportCreateRequest(BaseModel):
    """Esquema Pydantic v2 para reportar una falla de servicio con georreferenciación en Cali."""

    servicio: ServiceType = Field(description="Servicio afectado por la falla.")
    identificador_tipo: IdentifierType = Field(
        description="'contrato' si es cliente EMCALI o 'cedula' si no es cliente."
    )
    identificador_valor: str = Field(min_length=5, max_length=20)
    nombre_ciudadano: str = Field(default="Ciudadano EMCALI", min_length=2, max_length=120)
    barrio: str = Field(min_length=2, max_length=100)
    direccion: str = Field(default="", max_length=200)
    descripcion: str = Field(min_length=8, max_length=1200)
    telefono_e164: str = Field(default="")

    @model_validator(mode="after")
    def validate_identifier_digits(self) -> FailureReportCreateRequest:
        digits = "".join(ch for ch in self.identificador_valor if ch.isdigit())
        if len(digits) < 5:
            raise ValueError(
                f"El campo {self.identificador_tipo} debe contener al menos 5 dígitos numéricos."
            )
        self.identificador_valor = digits
        return self


class MaintenanceCreateRequest(BaseModel):
    """Esquema Pydantic v2 para activar un punto oficial de mantenimiento en el mapa."""

    titulo: str = Field(min_length=5, max_length=160)
    servicio: ServiceType
    barrio: str = Field(min_length=2, max_length=100)
    descripcion: str = Field(min_length=8, max_length=1500)
    brigada_asignada: str = Field(default="Brigada Operativa EMCALI", max_length=120)
    inicio_estimado: str = Field(default="")
    fin_estimado: str = Field(default="")
    fuente: Literal["scraping_emcali", "gestion_emcali", "promovido_falla"] = "gestion_emcali"
    fuente_url: str = Field(
        default="https://www.emcali.com.co/noticias/reparaciones-y-mantenimientos"
    )
    created_by: str = Field(default="gerencia-emcali")


class EmcaliOpsDatabase:
    """Capa de persistencia SQLite auditable para operaciones, RBAC, HITL y mapa de Cali."""

    def __init__(self, db_path: Path | str = OPS_DB_PATH) -> None:
        self.db_path_str = ":memory:" if str(db_path) == ":memory:" else str(Path(db_path))
        if self.db_path_str != ":memory:":
            Path(self.db_path_str).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path_str, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._seed_defaults()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users_rbac (
                    username TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('citizen', 'manager')),
                    password_hash TEXT NOT NULL,
                    phone_e164 TEXT NOT NULL DEFAULT '',
                    department TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pqrs_tickets (
                    radicado_id TEXT PRIMARY KEY,
                    tipo TEXT NOT NULL,
                    servicio TEXT NOT NULL,
                    identificador_tipo TEXT NOT NULL,
                    identificador_valor TEXT NOT NULL,
                    nombre_ciudadano TEXT NOT NULL,
                    barrio TEXT NOT NULL,
                    comuna TEXT NOT NULL,
                    telefono_e164 TEXT NOT NULL DEFAULT '',
                    descripcion TEXT NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'Radicado',
                    prioridad TEXT NOT NULL DEFAULT 'Normal',
                    notas_gestion TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS failure_reports (
                    reporte_id TEXT PRIMARY KEY,
                    servicio TEXT NOT NULL,
                    identificador_tipo TEXT NOT NULL,
                    identificador_valor TEXT NOT NULL,
                    nombre_ciudadano TEXT NOT NULL,
                    barrio TEXT NOT NULL,
                    comuna TEXT NOT NULL,
                    direccion TEXT NOT NULL DEFAULT '',
                    lat REAL NOT NULL,
                    lng REAL NOT NULL,
                    descripcion TEXT NOT NULL,
                    telefono_e164 TEXT NOT NULL DEFAULT '',
                    estado TEXT NOT NULL DEFAULT 'Reportado',
                    maintenance_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS maintenance_points (
                    mantenimiento_id TEXT PRIMARY KEY,
                    titulo TEXT NOT NULL,
                    servicio TEXT NOT NULL,
                    barrio TEXT NOT NULL,
                    comuna TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lng REAL NOT NULL,
                    descripcion TEXT NOT NULL,
                    fuente TEXT NOT NULL DEFAULT 'scraping_emcali',
                    estado TEXT NOT NULL DEFAULT 'Activo',
                    brigada_asignada TEXT NOT NULL DEFAULT '',
                    inicio_estimado TEXT NOT NULL DEFAULT '',
                    fin_estimado TEXT NOT NULL DEFAULT '',
                    fuente_url TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT 'system',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS emcali_news (
                    noticia_id TEXT PRIMARY KEY,
                    titulo TEXT NOT NULL,
                    categoria TEXT NOT NULL DEFAULT 'Institucional',
                    fecha_publicacion TEXT NOT NULL DEFAULT '',
                    resumen TEXT NOT NULL,
                    contenido TEXT NOT NULL,
                    url TEXT NOT NULL,
                    es_mantenimiento INTEGER NOT NULL DEFAULT 0,
                    barrios_json TEXT NOT NULL DEFAULT '[]',
                    scraped_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS newsletter_subscribers (
                    subscriber_id TEXT PRIMARY KEY,
                    canal TEXT NOT NULL DEFAULT 'whatsapp',
                    contacto TEXT NOT NULL UNIQUE,
                    nombre TEXT NOT NULL DEFAULT '',
                    barrio_interes TEXT NOT NULL DEFAULT 'Todos',
                    servicios_json TEXT NOT NULL DEFAULT '["energia","acueducto","telco_fibra"]',
                    frecuencia TEXT NOT NULL DEFAULT 'diaria',
                    activo INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS hitl_actions (
                    action_id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    resolved_at TEXT NOT NULL DEFAULT ''
                );
                """
            )
            self._conn.commit()

    def _seed_defaults(self) -> None:
        """Crea cuentas RBAC iniciales y puntos base si la DB está vacía."""
        now = utc_now_iso()
        manager_pass = os.getenv("EMCALI_MANAGER_PASSWORD", "emcali-ops-2026")
        citizen_pass = os.getenv("EMCALI_CITIZEN_PASSWORD", "ciudadano-2026")
        manager_phone = os.getenv("EMCALI_MANAGER_WHATSAPP_E164", "+573000000001")

        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM users_rbac")
            if int(cur.fetchone()[0]) == 0:
                self._conn.executemany(
                    """
                    INSERT INTO users_rbac (
                        username, display_name, role, password_hash,
                        phone_e164, department, active, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    [
                        (
                            "gerencia",
                            "Dirección de Operaciones EMCALI",
                            "manager",
                            _hash_secret(manager_pass),
                            manager_phone,
                            "Gerencia de Operaciones y Mantenimiento",
                            now,
                        ),
                        (
                            "rommel",
                            "Rommel Prieto (Gestión EMCALI)",
                            "manager",
                            _hash_secret(manager_pass),
                            manager_phone,
                            "Analítica & Operaciones IA",
                            now,
                        ),
                        (
                            "ciudadano",
                            "Usuario Ciudadano Cali",
                            "citizen",
                            _hash_secret(citizen_pass),
                            "",
                            "Público General",
                            now,
                        ),
                    ],
                )
                self._conn.commit()

            # Semilla inicial de mantenimientos y fallas para que el mapa nunca arranque vacío
            cur_m = self._conn.execute("SELECT COUNT(*) FROM maintenance_points")
            if int(cur_m.fetchone()[0]) == 0:
                seed_maint = [
                    MaintenanceCreateRequest(
                        titulo="Mantenimiento preventivo red de acueducto - San Fernando",
                        servicio="acueducto",
                        barrio="San Fernando",
                        descripcion=(
                            "Optimización de válvulas de presión y lavado de tubería matriz "
                            "sobre la Calle 5 con Carrera 34."
                        ),
                        brigada_asignada="Brigada Acueducto Sur-01",
                        inicio_estimado=f"{now[:10]} 08:00",
                        fin_estimado=f"{now[:10]} 16:00",
                        fuente="scraping_emcali",
                    ),
                    MaintenanceCreateRequest(
                        titulo="Modernización de transformador y circuito - La Flora",
                        servicio="energia",
                        barrio="La Flora",
                        descripcion=(
                            "Cambio de transformador trifásico y poda técnica de seguridad "
                            "en el corredor de la Avenida 3N."
                        ),
                        brigada_asignada="Brigada Energía Norte-03",
                        inicio_estimado=f"{now[:10]} 07:30",
                        fin_estimado=f"{now[:10]} 15:00",
                        fuente="scraping_emcali",
                    ),
                    MaintenanceCreateRequest(
                        titulo="Empalme de fibra óptica troncal - El Ingenio",
                        servicio="telco_fibra",
                        barrio="El Ingenio",
                        descripcion=(
                            "Migración de nodos FTTH para mejorar estabilidad de planes "
                            "de 500 y 900 Mbps en Comuna 17."
                        ),
                        brigada_asignada="Brigada Telco Sur-02",
                        inicio_estimado=f"{now[:10]} 09:00",
                        fin_estimado=f"{now[:10]} 14:00",
                        fuente="scraping_emcali",
                    ),
                ]
                for item in seed_maint:
                    self.create_maintenance_point(item)

    # ------------------------------------------------------------------
    # IAM / RBAC
    # ------------------------------------------------------------------
    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        """Valida credenciales RBAC y emite un token de sesión persistente."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM users_rbac WHERE username = ? AND active = 1",
                (username.strip().lower(),),
            ).fetchone()
            if row is None or not _verify_secret(password, str(row["password_hash"])):
                return None
            token = f"emcali_{secrets.token_urlsafe(24)}"
            now = utc_now_iso()
            self._conn.execute(
                """
                INSERT INTO auth_sessions (token, username, role, display_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token, row["username"], row["role"], row["display_name"], now),
            )
            self._conn.commit()
            return {
                "token": token,
                "username": row["username"],
                "display_name": row["display_name"],
                "role": row["role"],
                "department": row["department"],
                "created_at": now,
            }

    def resolve_session_token(self, token: str | None) -> dict[str, Any] | None:
        """Resuelve un Bearer token a su identidad RBAC."""
        if not token:
            return None
        clean = token.replace("Bearer ", "").strip()
        with self._lock:
            row = self._conn.execute(
                (
                    "SELECT token, username, role, display_name, created_at "
                    "FROM auth_sessions WHERE token = ?"
                ),
                (clean,),
            ).fetchone()
            return dict(row) if row else None

    def resolve_role_by_phone(self, phone_e164: str) -> UserRole:
        """Determina el rol RBAC a partir del número E.164 de WhatsApp (allowlist de gestión)."""
        clean = phone_e164.strip()
        if not clean:
            return "citizen"
        allowlist_env = os.getenv("EMCALI_MANAGER_WHATSAPP_ALLOWLIST", "")
        allowed_phones = {p.strip() for p in allowlist_env.split(",") if p.strip()}
        if clean in allowed_phones:
            return "manager"
        with self._lock:
            row = self._conn.execute(
                "SELECT role FROM users_rbac WHERE phone_e164 = ? AND active = 1",
                (clean,),
            ).fetchone()
            if row and row["role"] == "manager":
                return "manager"
        return "citizen"

    def list_users_rbac(self) -> list[dict[str, Any]]:
        """Lista todos los usuarios RBAC sin exponer hashes de contraseña."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT username, display_name, role, phone_e164, department, active, created_at
                FROM users_rbac
                ORDER BY role DESC, username ASC
                """
            ).fetchall()
        return [{**dict(r), "active": bool(r["active"])} for r in rows]

    def upsert_user_rbac(
        self,
        *,
        username: str,
        display_name: str,
        role: UserRole,
        password: str | None = None,
        phone_e164: str = "",
        department: str = "",
        active: bool = True,
    ) -> dict[str, Any]:
        """Crea o actualiza un usuario RBAC (solo accesible desde Gestión EMCALI)."""
        clean_user = username.strip().lower()
        now = utc_now_iso()
        with self._lock:
            existing = self._conn.execute(
                "SELECT password_hash FROM users_rbac WHERE username = ?", (clean_user,)
            ).fetchone()
            if existing:
                pw_hash = (
                    _hash_secret(password)
                    if password and password.strip()
                    else str(existing["password_hash"])
                )
                self._conn.execute(
                    """
                    UPDATE users_rbac
                    SET display_name = ?, role = ?, password_hash = ?,
                        phone_e164 = ?, department = ?, active = ?
                    WHERE username = ?
                    """,
                    (
                        display_name.strip(),
                        role,
                        pw_hash,
                        phone_e164.strip(),
                        department.strip(),
                        1 if active else 0,
                        clean_user,
                    ),
                )
            else:
                if not password or len(password.strip()) < 4:
                    raise ValueError("La contraseña debe tener al menos 4 caracteres.")
                self._conn.execute(
                    """
                    INSERT INTO users_rbac (
                        username, display_name, role, password_hash,
                        phone_e164, department, active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clean_user,
                        display_name.strip(),
                        role,
                        _hash_secret(password.strip()),
                        phone_e164.strip(),
                        department.strip(),
                        1 if active else 0,
                        now,
                    ),
                )
            self._conn.commit()
            row = self._conn.execute(
                """
                SELECT username, display_name, role, phone_e164, department, active, created_at
                FROM users_rbac WHERE username = ?
                """,
                (clean_user,),
            ).fetchone()
        return {**dict(row), "active": bool(row["active"])}

    # ------------------------------------------------------------------
    # PQRS
    # ------------------------------------------------------------------
    def create_pqrs(self, req: PqrsCreateRequest) -> dict[str, Any]:
        loc = try_resolve_cali_location(req.barrio)
        if loc is None:
            raise ValueError(
                f"El barrio '{req.barrio}' no figura en la cobertura oficial de EMCALI "
                "(Cali Comunas 1-22, Yumbo, Jamundí, Candelaria y Puerto Tejada). "
                "Por favor verifica el barrio o indica la comuna."
            )
        now = utc_now_iso()
        radicado_id = f"PQRS-2026-{uuid.uuid4().hex[:6].upper()}"
        prioridad = "Alta" if req.tipo in {"Reclamo", "Queja"} else "Normal"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO pqrs_tickets (
                    radicado_id, tipo, servicio, identificador_tipo, identificador_valor,
                    nombre_ciudadano, barrio, comuna, telefono_e164, descripcion,
                    estado, prioridad, notas_gestion, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Radicado', ?, '', ?, ?)
                """,
                (
                    radicado_id,
                    req.tipo,
                    req.servicio,
                    req.identificador_tipo,
                    req.identificador_valor,
                    req.nombre_ciudadano.strip(),
                    loc.barrio if loc.barrio != "Cali (Centro)" else req.barrio.strip(),
                    loc.comuna,
                    req.telefono_e164.strip(),
                    req.descripcion.strip(),
                    prioridad,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM pqrs_tickets WHERE radicado_id = ?", (radicado_id,)
            ).fetchone()
        return dict(row)

    def get_pqrs(self, radicado_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pqrs_tickets WHERE UPPER(radicado_id) = UPPER(?)",
                (radicado_id.strip(),),
            ).fetchone()
        return dict(row) if row else None

    def list_pqrs(
        self,
        *,
        identificador_valor: str | None = None,
        servicio: str | None = None,
        estado: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if identificador_valor:
            digits = "".join(ch for ch in identificador_valor if ch.isdigit())
            clauses.append("identificador_valor = ?")
            params.append(digits or identificador_valor.strip())
        if servicio and servicio != "todos":
            clauses.append("servicio = ?")
            params.append(servicio)
        if estado and estado != "todos":
            clauses.append("estado = ?")
            params.append(estado)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM pqrs_tickets {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def update_pqrs_status(
        self,
        radicado_id: str,
        *,
        nuevo_estado: PqrsStatus,
        notas_gestion: str = "",
    ) -> dict[str, Any] | None:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE pqrs_tickets
                SET estado = ?, notas_gestion = ?, updated_at = ?
                WHERE UPPER(radicado_id) = UPPER(?)
                """,
                (nuevo_estado, notas_gestion.strip(), now, radicado_id.strip()),
            )
            self._conn.commit()
            if cur.rowcount == 0:
                return None
            row = self._conn.execute(
                "SELECT * FROM pqrs_tickets WHERE UPPER(radicado_id) = UPPER(?)",
                (radicado_id.strip(),),
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Reportes de Fallas y Detección de Hotspots para Brigadas
    # ------------------------------------------------------------------
    def create_failure_report(self, req: FailureReportCreateRequest) -> dict[str, Any]:
        loc = try_resolve_cali_location(f"{req.barrio} {req.direccion}")
        if loc is None:
            raise ValueError(
                f"El barrio '{req.barrio}' no existe en el catálogo de cobertura de EMCALI "
                "(Cali Comunas 1-22, Yumbo, Jamundí, Candelaria y Puerto Tejada). "
                "Verifica el nombre del barrio o indica tu comuna."
            )
        now = utc_now_iso()
        reporte_id = f"FALLA-2026-{uuid.uuid4().hex[:6].upper()}"
        barrio_name = loc.barrio if loc.barrio != "Cali (Centro)" else req.barrio.strip()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO failure_reports (
                    reporte_id, servicio, identificador_tipo, identificador_valor,
                    nombre_ciudadano, barrio, comuna, direccion, lat, lng,
                    descripcion, telefono_e164, estado, maintenance_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Reportado', '', ?)
                """,
                (
                    reporte_id,
                    req.servicio,
                    req.identificador_tipo,
                    req.identificador_valor,
                    req.nombre_ciudadano.strip(),
                    barrio_name,
                    loc.comuna,
                    req.direccion.strip(),
                    loc.lat,
                    loc.lng,
                    req.descripcion.strip(),
                    req.telefono_e164.strip(),
                    now,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM failure_reports WHERE reporte_id = ?", (reporte_id,)
            ).fetchone()
        report = dict(row)
        # Adjunta el estado actual del hotspot en ese barrio/servicio
        hotspots = self.get_failure_hotspots(servicio=req.servicio)
        matching = [h for h in hotspots if h["barrio"].lower() == barrio_name.lower()]
        report["hotspot_info"] = matching[0] if matching else None
        return report

    def list_failure_reports(
        self,
        *,
        servicio: str | None = None,
        barrio: str | None = None,
        estado: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if servicio and servicio != "todos":
            clauses.append("servicio = ?")
            params.append(servicio)
        if barrio:
            clauses.append("LOWER(barrio) LIKE ?")
            params.append(f"%{barrio.strip().lower()}%")
        if estado and estado != "todos":
            clauses.append("estado = ?")
            params.append(estado)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM failure_reports {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def get_failure_hotspots(self, *, servicio: str | None = None) -> list[dict[str, Any]]:
        """Agrupa reportes abiertos por (barrio, servicio) y calcula severidad para brigadas."""
        clauses = ["estado != 'Resuelto'"]
        params: list[Any] = []
        if servicio and servicio != "todos":
            clauses.append("servicio = ?")
            params.append(servicio)
        where = f"WHERE {' AND '.join(clauses)}"
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT
                    barrio,
                    comuna,
                    servicio,
                    AVG(lat) AS lat,
                    AVG(lng) AS lng,
                    COUNT(*) AS report_count,
                    MAX(created_at) AS latest_report_at,
                    GROUP_CONCAT(reporte_id, ',') AS report_ids
                FROM failure_reports
                {where}
                GROUP BY barrio, comuna, servicio
                ORDER BY report_count DESC, latest_report_at DESC
                """,
                params,
            ).fetchall()

        hotspots: list[dict[str, Any]] = []
        for r in rows:
            count = int(r["report_count"])
            if count >= 4:
                severity = "critical_dispatch"
                label = "Brigada Sugerida (Crítico)"
            elif count >= 2:
                severity = "warning_cluster"
                label = "Alerta de Acumulación"
            else:
                severity = "watch_single"
                label = "Reporte Individual"
            hotspots.append(
                {
                    "barrio": r["barrio"],
                    "comuna": r["comuna"],
                    "servicio": r["servicio"],
                    "lat": round(float(r["lat"]), 6),
                    "lng": round(float(r["lng"]), 6),
                    "report_count": count,
                    "severity": severity,
                    "severity_label": label,
                    "dispatch_recommended": count >= 2,
                    "latest_report_at": r["latest_report_at"],
                    "report_ids": str(r["report_ids"] or "").split(","),
                }
            )
        return hotspots

    # ------------------------------------------------------------------
    # Mantenimientos Oficiales & Mapa de Cali
    # ------------------------------------------------------------------
    def create_maintenance_point(self, req: MaintenanceCreateRequest) -> dict[str, Any]:
        loc = try_resolve_cali_location(req.barrio)
        if loc is None:
            raise ValueError(
                f"El barrio '{req.barrio}' no figura en la cobertura oficial de EMCALI."
            )
        now = utc_now_iso()
        maint_id = f"MANT-2026-{uuid.uuid4().hex[:6].upper()}"
        barrio_name = loc.barrio if loc.barrio != "Cali (Centro)" else req.barrio.strip()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO maintenance_points (
                    mantenimiento_id, titulo, servicio, barrio, comuna, lat, lng,
                    descripcion, fuente, estado, brigada_asignada, inicio_estimado,
                    fin_estimado, fuente_url, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Activo', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    maint_id,
                    req.titulo.strip(),
                    req.servicio,
                    barrio_name,
                    loc.comuna,
                    loc.lat,
                    loc.lng,
                    req.descripcion.strip(),
                    req.fuente,
                    req.brigada_asignada.strip(),
                    req.inicio_estimado.strip() or now[:16],
                    req.fin_estimado.strip() or "Por confirmar",
                    req.fuente_url.strip(),
                    req.created_by.strip(),
                    now,
                    now,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM maintenance_points WHERE mantenimiento_id = ?", (maint_id,)
            ).fetchone()
        return dict(row)

    def dispatch_crew_for_hotspot(
        self,
        *,
        barrio: str,
        servicio: ServiceType,
        brigada_asignada: str,
        notas: str = "",
        created_by: str = "gerencia",
    ) -> dict[str, Any]:
        """Promueve un hotspot de fallas a mantenimiento oficial y asigna brigada."""
        loc = try_resolve_cali_location(barrio)
        if loc is None:
            raise ValueError(f"El barrio '{barrio}' no figura en la cobertura oficial de EMCALI.")
        target_barrio = loc.barrio
        maint = self.create_maintenance_point(
            MaintenanceCreateRequest(
                titulo=(f"Despliegue de brigada por fallas ({servicio}) — {target_barrio}"),
                servicio=servicio,
                barrio=target_barrio,
                descripcion=(
                    notas.strip()
                    or f"Atención priorizada por reportes ciudadanos acumulados de {servicio} "
                    f"en {target_barrio}."
                ),
                brigada_asignada=brigada_asignada,
                fuente="promovido_falla",
                created_by=created_by,
            )
        )
        with self._lock:
            phone_rows = self._conn.execute(
                """
                SELECT DISTINCT telefono_e164 FROM failure_reports
                WHERE LOWER(barrio) = LOWER(?) AND servicio = ?
                  AND estado != 'Resuelto' AND telefono_e164 != ''
                """,
                (target_barrio, servicio),
            ).fetchall()
            sub_rows = self._conn.execute(
                """
                SELECT DISTINCT contacto FROM newsletter_subscribers
                WHERE activo = 1 AND canal = 'whatsapp'
                  AND (LOWER(barrio_interes) = LOWER(?) OR LOWER(barrio_interes) = 'todos')
                """,
                (target_barrio,),
            ).fetchall()
            cur = self._conn.execute(
                """
                UPDATE failure_reports
                SET estado = 'Brigada asignada', maintenance_id = ?
                WHERE LOWER(barrio) = LOWER(?) AND servicio = ? AND estado != 'Resuelto'
                """,
                (maint["mantenimiento_id"], target_barrio, servicio),
            )
            self._conn.commit()
            linked_count = cur.rowcount
        phones = sorted(
            {
                str(r[0]).strip()
                for r in (*phone_rows, *sub_rows)
                if str(r[0]).strip().startswith("+")
            }
        )
        maint["linked_failure_reports"] = linked_count
        maint["notifiable_phones"] = phones
        return maint

    def close_maintenance_point(
        self,
        mantenimiento_id: str,
        *,
        notas_cierre: str = "",
    ) -> dict[str, Any] | None:
        now = utc_now_iso()
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM maintenance_points WHERE UPPER(mantenimiento_id) = UPPER(?)",
                (mantenimiento_id.strip(),),
            ).fetchone()
            if not existing:
                return None
            updated_desc = str(existing["descripcion"])
            if notas_cierre.strip():
                updated_desc = f"{updated_desc} | Cierre: {notas_cierre.strip()}"
            self._conn.execute(
                """
                UPDATE maintenance_points
                SET estado = 'Finalizado', descripcion = ?, updated_at = ?
                WHERE UPPER(mantenimiento_id) = UPPER(?)
                """,
                (updated_desc, now, mantenimiento_id.strip()),
            )
            self._conn.execute(
                """
                UPDATE failure_reports
                SET estado = 'Resuelto'
                WHERE UPPER(maintenance_id) = UPPER(?)
                """,
                (mantenimiento_id.strip(),),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM maintenance_points WHERE UPPER(mantenimiento_id) = UPPER(?)",
                (mantenimiento_id.strip(),),
            ).fetchone()
        return dict(row) if row else None

    def list_maintenance_points(
        self,
        *,
        servicio: str | None = None,
        barrio: str | None = None,
        solo_activos: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if solo_activos:
            clauses.append("estado != 'Finalizado'")
        if servicio and servicio != "todos":
            clauses.append("servicio = ?")
            params.append(servicio)
        if barrio:
            clauses.append("LOWER(barrio) LIKE ?")
            params.append(f"%{barrio.strip().lower()}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM maintenance_points {where} ORDER BY updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Noticias & Boletín OpenClaw
    # ------------------------------------------------------------------
    def upsert_news_item(
        self,
        *,
        noticia_id: str,
        titulo: str,
        categoria: str,
        fecha_publicacion: str,
        resumen: str,
        contenido: str,
        url: str,
        es_mantenimiento: bool = False,
        barrios: list[str] | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        barrios_json = json.dumps(barrios or [], ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO emcali_news (
                    noticia_id, titulo, categoria, fecha_publicacion, resumen,
                    contenido, url, es_mantenimiento, barrios_json, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(noticia_id) DO UPDATE SET
                    titulo=excluded.titulo,
                    categoria=excluded.categoria,
                    fecha_publicacion=excluded.fecha_publicacion,
                    resumen=excluded.resumen,
                    contenido=excluded.contenido,
                    url=excluded.url,
                    es_mantenimiento=excluded.es_mantenimiento,
                    barrios_json=excluded.barrios_json,
                    scraped_at=excluded.scraped_at
                """,
                (
                    noticia_id,
                    titulo.strip(),
                    categoria.strip(),
                    fecha_publicacion.strip(),
                    resumen.strip(),
                    contenido.strip(),
                    url.strip(),
                    1 if es_mantenimiento else 0,
                    barrios_json,
                    now,
                ),
            )
            self._conn.commit()
        return {
            "noticia_id": noticia_id,
            "titulo": titulo.strip(),
            "categoria": categoria.strip(),
            "fecha_publicacion": fecha_publicacion.strip(),
            "resumen": resumen.strip(),
            "url": url.strip(),
            "es_mantenimiento": es_mantenimiento,
            "barrios": barrios or [],
            "scraped_at": now,
        }

    def list_news(
        self,
        *,
        query: str = "",
        solo_mantenimientos: bool = False,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if solo_mantenimientos:
            clauses.append("es_mantenimiento = 1")
        if query.strip():
            kw = f"%{query.strip().lower()}%"
            clauses.append(
                "(LOWER(titulo) LIKE ? OR LOWER(resumen) LIKE ? OR LOWER(contenido) LIKE ?)"
            )
            params.extend([kw, kw, kw])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM emcali_news {where}
                ORDER BY
                    CASE WHEN fecha_publicacion GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                         THEN fecha_publicacion ELSE '0000-00-00' END DESC,
                    scraped_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            item["es_mantenimiento"] = bool(item["es_mantenimiento"])
            item["barrios"] = json.loads(str(item.pop("barrios_json", "[]")))
            out.append(item)
        return out

    def subscribe_newsletter(
        self,
        *,
        contacto: str,
        canal: Literal["whatsapp", "web", "telegram"] = "whatsapp",
        nombre: str = "",
        barrio_interes: str = "Todos",
        servicios: list[str] | None = None,
        frecuencia: Literal["diaria", "semanal"] = "diaria",
    ) -> dict[str, Any]:
        now = utc_now_iso()
        sub_id = f"SUB-{uuid.uuid4().hex[:6].upper()}"
        serv_list = servicios or ["energia", "acueducto", "telco_fibra"]
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO newsletter_subscribers (
                    subscriber_id, canal, contacto, nombre, barrio_interes,
                    servicios_json, frecuencia, activo, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(contacto) DO UPDATE SET
                    canal=excluded.canal,
                    nombre=excluded.nombre,
                    barrio_interes=excluded.barrio_interes,
                    servicios_json=excluded.servicios_json,
                    frecuencia=excluded.frecuencia,
                    activo=1
                """,
                (
                    sub_id,
                    canal,
                    contacto.strip(),
                    nombre.strip(),
                    barrio_interes.strip() or "Todos",
                    json.dumps(serv_list, ensure_ascii=False),
                    frecuencia,
                    now,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM newsletter_subscribers WHERE contacto = ?", (contacto.strip(),)
            ).fetchone()
        data = dict(row)
        data["servicios"] = json.loads(str(data.pop("servicios_json", "[]")))
        data["activo"] = bool(data["activo"])
        return data

    def list_newsletter_subscribers(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM newsletter_subscribers WHERE activo = 1 ORDER BY created_at DESC"
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            item["servicios"] = json.loads(str(item.pop("servicios_json", "[]")))
            item["activo"] = bool(item["activo"])
            out.append(item)
        return out

    # ------------------------------------------------------------------
    # HITL (Human-in-the-Loop) Pending Actions
    # ------------------------------------------------------------------
    def create_hitl_action(
        self,
        *,
        tool_name: str,
        user_id: str,
        role: UserRole,
        summary: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now_iso()
        action_id = f"HITL-{uuid.uuid4().hex[:6].upper()}"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO hitl_actions (
                    action_id, tool_name, user_id, role, summary, payload_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    action_id,
                    tool_name,
                    user_id,
                    role,
                    summary,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                ),
            )
            self._conn.commit()
        return {
            "action_id": action_id,
            "tool_name": tool_name,
            "user_id": user_id,
            "role": role,
            "summary": summary,
            "payload": payload,
            "status": "pending",
            "created_at": now,
        }

    def list_hitl_actions(self, *, status: str = "pending") -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hitl_actions WHERE status = ? ORDER BY created_at DESC LIMIT 50",
                (status,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            item["payload"] = json.loads(str(item.pop("payload_json", "{}")))
            item["result"] = json.loads(str(item.pop("result_json", "{}")))
            out.append(item)
        return out

    def resolve_hitl_action(
        self,
        action_id: str,
        *,
        approved: bool,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        now = utc_now_iso()
        status = "approved" if approved else "rejected"
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE hitl_actions
                SET status = ?, result_json = ?, resolved_at = ?
                WHERE UPPER(action_id) = UPPER(?) AND status = 'pending'
                """,
                (status, json.dumps(result or {}, ensure_ascii=False), now, action_id.strip()),
            )
            self._conn.commit()
            if cur.rowcount == 0:
                return None
            row = self._conn.execute(
                "SELECT * FROM hitl_actions WHERE UPPER(action_id) = UPPER(?)",
                (action_id.strip(),),
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["payload"] = json.loads(str(item.pop("payload_json", "{}")))
        item["result"] = json.loads(str(item.pop("result_json", "{}")))
        return item

    # ------------------------------------------------------------------
    # Resumen Ejecutivo de Operaciones (RBAC Manager)
    # ------------------------------------------------------------------
    def executive_summary(self) -> dict[str, Any]:
        with self._lock:
            pqrs_by_status = dict(
                self._conn.execute(
                    "SELECT estado, COUNT(*) FROM pqrs_tickets GROUP BY estado"
                ).fetchall()
            )
            pqrs_by_service = dict(
                self._conn.execute(
                    "SELECT servicio, COUNT(*) FROM pqrs_tickets GROUP BY servicio"
                ).fetchall()
            )
            active_maint = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM maintenance_points WHERE estado != 'Finalizado'"
                ).fetchone()[0]
            )
            open_failures = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM failure_reports WHERE estado != 'Resuelto'"
                ).fetchone()[0]
            )
            news_count = int(self._conn.execute("SELECT COUNT(*) FROM emcali_news").fetchone()[0])
            subs_count = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM newsletter_subscribers WHERE activo = 1"
                ).fetchone()[0]
            )
            pending_hitl = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM hitl_actions WHERE status = 'pending'"
                ).fetchone()[0]
            )

        hotspots = self.get_failure_hotspots()
        return {
            "generated_at": utc_now_iso(),
            "pqrs_total": sum(pqrs_by_status.values()),
            "pqrs_by_status": pqrs_by_status,
            "pqrs_by_service": pqrs_by_service,
            "active_maintenances": active_maint,
            "open_failure_reports": open_failures,
            "hotspots_needing_dispatch": [h for h in hotspots if h["dispatch_recommended"]],
            "all_hotspots": hotspots,
            "news_indexed": news_count,
            "newsletter_subscribers": subs_count,
            "pending_hitl_approvals": pending_hitl,
        }


_OPS_DB_LOCK = threading.Lock()
_OPS_DB_SINGLETON: EmcaliOpsDatabase | None = None


def get_ops_db(*, in_memory: bool = False) -> EmcaliOpsDatabase:
    """Devuelve el singleton thread-safe de la base de datos operativa SQLite."""
    global _OPS_DB_SINGLETON
    if in_memory:
        return EmcaliOpsDatabase(":memory:")
    with _OPS_DB_LOCK:
        if _OPS_DB_SINGLETON is None:
            _OPS_DB_SINGLETON = EmcaliOpsDatabase(OPS_DB_PATH)
        return _OPS_DB_SINGLETON
