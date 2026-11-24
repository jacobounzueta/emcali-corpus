"""Catálogo completo de 20 herramientas (@tool) tipadas con Pydantic v2, RBAC y HITL (Módulo 3)."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from emcali_corpus.cali_geo import resolve_cali_location
from emcali_corpus.memory import (
    get_memory_manager,
    search_user_long_term_memories,
    utc_iso,
)
from emcali_corpus.news_sync import build_daily_newsletter_digest, sync_news_from_gold
from emcali_corpus.ops_db import (
    FailureReportCreateRequest,
    IdentifierType,
    MaintenanceCreateRequest,
    PqrsCreateRequest,
    PqrsStatus,
    PqrsType,
    ServiceType,
    UserRole,
    get_ops_db,
)
from emcali_corpus.tools import (
    consultar_indicadores_operativos_json,
    consultar_tarifas_emcali_csv,
    load_tarifas_csv,
    query_tarifas_structured,
)
from emcali_corpus.vector_store import RagSearchInput, get_vector_store

# ---------------------------------------------------------------------------
# Esquemas Pydantic v2 de entrada para las 18 herramientas nuevas (+2 existentes = 20)
# ---------------------------------------------------------------------------


class SimularFacturaInput(BaseModel):
    servicio: ServiceType = Field(description="Servicio público a simular.")
    estrato: int = Field(ge=0, le=6, description="Estrato (1-6) o 0 para Comercial/Industrial.")
    consumo_mes: float = Field(
        gt=0.0,
        description=(
            "Consumo mensual estimado en kWh (energía), m3 (acueducto/alcantarillado) o 1 fibra."
        ),
    )
    trimestre: Literal["2026-Q1", "2026-Q2", "2026-Q3"] = Field(default="2026-Q3")


class CompararTarifasInput(BaseModel):
    servicio: ServiceType = Field(description="Servicio público a comparar entre trimestres.")
    estrato: int = Field(ge=0, le=6, description="Estrato socioeconómico a comparar.")


class ConsultarNoticiasInput(BaseModel):
    palabra_clave: str = Field(default="", description="Tema, barrio o palabra clave a buscar.")
    solo_mantenimientos: bool = Field(
        default=False,
        description="Si True, filtra únicamente noticias de reparaciones y mantenimientos.",
    )
    limite: int = Field(default=6, ge=1, le=20)


class ListarMantenimientosInput(BaseModel):
    servicio: Literal["energia", "acueducto", "alcantarillado", "telco_fibra", "todos"] = Field(
        default="todos"
    )
    barrio: str = Field(default="", description="Filtro opcional por barrio de Cali.")
    solo_activos: bool = Field(default=True)


class AfectacionBarrioInput(BaseModel):
    barrio: str = Field(min_length=2, description="Nombre del barrio o comuna de Cali.")


class SuscribirBoletinInput(BaseModel):
    contacto: str = Field(
        min_length=5,
        description="Número de WhatsApp en formato E.164 (ej. +573001234567) o correo/usuario.",
    )
    canal: Literal["whatsapp", "web", "telegram"] = Field(default="whatsapp")
    nombre: str = Field(default="", description="Nombre del ciudadano suscriptor.")
    barrio_interes: str = Field(default="Todos", description="Barrio prioritario para alertas.")
    frecuencia: Literal["diaria", "semanal"] = Field(default="diaria")


class RadicarPqrsInput(BaseModel):
    tipo: PqrsType = Field(description="Petición, Queja, Reclamo o Sugerencia.")
    servicio: ServiceType
    identificador_tipo: IdentifierType = Field(
        description="'contrato' (cliente EMCALI) o 'cedula' (no cliente)."
    )
    identificador_valor: str = Field(min_length=5, max_length=20)
    nombre_ciudadano: str = Field(min_length=2, max_length=120)
    barrio: str = Field(min_length=2, max_length=100)
    descripcion: str = Field(min_length=10, max_length=1500)
    telefono_e164: str = Field(default="")


class ReportarFallaInput(BaseModel):
    servicio: ServiceType
    identificador_tipo: IdentifierType = Field(
        description="'contrato' (cliente EMCALI) o 'cedula' (no cliente)."
    )
    identificador_valor: str = Field(min_length=5, max_length=20)
    nombre_ciudadano: str = Field(default="Ciudadano EMCALI", min_length=2, max_length=120)
    barrio: str = Field(min_length=2, max_length=100)
    direccion: str = Field(default="")
    descripcion: str = Field(min_length=8, max_length=1200)
    telefono_e164: str = Field(default="")


class ConsultarRadicadoInput(BaseModel):
    radicado_id: str = Field(
        min_length=5,
        description="Código del radicado (ej. PQRS-2026-XXXXXX o FALLA-2026-XXXXXX).",
    )


class ListarMisRadicadosInput(BaseModel):
    identificador_valor: str = Field(
        min_length=5,
        description="Número de contrato o cédula del ciudadano.",
    )


class CanalesAtencionInput(BaseModel):
    tipo_tramite: Literal["pagos", "pqrs", "fallas", "presencial", "todos"] = Field(default="todos")


class GuardarPreferenciaInput(BaseModel):
    user_id: str = Field(default="ciudadano-cali")
    clave: str = Field(min_length=2, description="Ej. ubicacion_barrio, estrato_vivienda, nombre.")
    etiqueta: str = Field(min_length=2, description="Etiqueta legible del dato.")
    valor: str = Field(min_length=1, description="Valor a recordar en memoria de largo plazo.")


class ConsultarPerfilMemoriaInput(BaseModel):
    user_id: str = Field(default="ciudadano-cali")
    consulta: str = Field(default="")


class ActivarMantenimientoInput(BaseModel):
    titulo: str = Field(min_length=5, max_length=160)
    servicio: ServiceType
    barrio: str = Field(min_length=2, max_length=100)
    descripcion: str = Field(min_length=8, max_length=1500)
    brigada_asignada: str = Field(default="Brigada Operativa EMCALI")
    inicio_estimado: str = Field(default="")
    fin_estimado: str = Field(default="")


class AsignarBrigadaInput(BaseModel):
    barrio: str = Field(min_length=2, description="Barrio con reportes de falla acumulados.")
    servicio: ServiceType
    brigada_asignada: str = Field(
        min_length=3,
        description="Nombre o código de la cuadrilla/brigada despachada.",
    )
    notas: str = Field(default="")


class GestionarEstadoPqrsInput(BaseModel):
    radicado_id: str = Field(min_length=5)
    nuevo_estado: PqrsStatus
    notas_gestion: str = Field(default="")


class ResumenEjecutivoInput(BaseModel):
    sincronizar_noticias: bool = Field(
        default=False,
        description=(
            "Si True, ejecuta sincronización de noticias y mantenimientos antes del reporte."
        ),
    )
    incluir_boletin: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Implementación de las 18 nuevas @tool (+2 de tools.py = 20 herramientas)
# ---------------------------------------------------------------------------


@tool("simular_factura_mensual", args_schema=SimularFacturaInput)
def simular_factura_mensual(
    servicio: ServiceType,
    estrato: int,
    consumo_mes: float,
    trimestre: Literal["2026-Q1", "2026-Q2", "2026-Q3"] = "2026-Q3",
) -> dict[str, Any]:
    """Simula determinísticamente el valor mensual de la factura EMCALI usando tarifas oficiales."""
    report = query_tarifas_structured(servicio=servicio, estrato=estrato, trimestre=trimestre)
    if not report.rows:
        return {
            "found": False,
            "message": (
                f"No se encontró tarifa oficial para {servicio} estrato {estrato} en {trimestre}."
            ),
        }
    row = report.rows[0]
    if servicio == "telco_fibra":
        total = round(float(row["tarifa_aplicada_cop"]) + float(row["cargo_fijo_cop"]), 2)
    else:
        total = round(
            consumo_mes * float(row["tarifa_aplicada_cop"]) + float(row["cargo_fijo_cop"]), 2
        )
    return {
        "found": True,
        "servicio": servicio,
        "estrato": estrato,
        "trimestre": trimestre,
        "consumo_simulado": consumo_mes,
        "unidad": row["unidad"],
        "tarifa_aplicada_cop": row["tarifa_aplicada_cop"],
        "subsidio_contribucion_pct": row["subsidio_contribucion_pct"],
        "cargo_fijo_cop": row["cargo_fijo_cop"],
        "factura_simulada_cop": total,
    }


@tool("comparar_tarifas_trimestres", args_schema=CompararTarifasInput)
def comparar_tarifas_trimestres(servicio: ServiceType, estrato: int) -> dict[str, Any]:
    """Compara la evolución exacta de tarifas EMCALI entre 2026-Q1, 2026-Q2 y 2026-Q3."""
    rows = [r for r in load_tarifas_csv() if r.servicio == servicio and r.estrato == estrato]
    rows.sort(key=lambda r: r.trimestre)
    if not rows:
        return {"found": False, "servicio": servicio, "estrato": estrato, "series": []}
    first, last = rows[0], rows[-1]
    delta = round(last.tarifa_aplicada_cop - first.tarifa_aplicada_cop, 2)
    pct = (
        round((delta / first.tarifa_aplicada_cop) * 100.0, 2) if first.tarifa_aplicada_cop else 0.0
    )
    return {
        "found": True,
        "servicio": servicio,
        "estrato": estrato,
        "delta_cop": delta,
        "variacion_pct": pct,
        "series": [
            {
                "trimestre": r.trimestre,
                "tarifa_aplicada_cop": r.tarifa_aplicada_cop,
                "cargo_fijo_cop": r.cargo_fijo_cop,
                "factura_estimada_mes_cop": r.factura_estimada_mes_cop,
            }
            for r in rows
        ],
    }


@tool("consultar_noticias_emcali", args_schema=ConsultarNoticiasInput)
def consultar_noticias_emcali(
    palabra_clave: str = "",
    solo_mantenimientos: bool = False,
    limite: int = 6,
) -> dict[str, Any]:
    """Consulta noticias recientes y boletines oficiales scrapeados de emcali.com.co."""
    db = get_ops_db()
    if not db.list_news(limit=1):
        sync_news_from_gold(db)
    items = db.list_news(
        query=palabra_clave,
        solo_mantenimientos=solo_mantenimientos,
        limit=limite,
    )
    return {
        "count": len(items),
        "palabra_clave": palabra_clave,
        "solo_mantenimientos": solo_mantenimientos,
        "noticias": [
            {
                "noticia_id": n["noticia_id"],
                "titulo": n["titulo"],
                "categoria": n["categoria"],
                "fecha_publicacion": n["fecha_publicacion"],
                "barrios": n["barrios"],
                "resumen": n["resumen"],
                "url": n["url"],
            }
            for n in items
        ],
    }


@tool("listar_mantenimientos_activos", args_schema=ListarMantenimientosInput)
def listar_mantenimientos_activos(
    servicio: Literal["energia", "acueducto", "alcantarillado", "telco_fibra", "todos"] = "todos",
    barrio: str = "",
    solo_activos: bool = True,
) -> dict[str, Any]:
    """Lista los puntos de mantenimiento y reparación georreferenciados en Cali."""
    db = get_ops_db()
    points = db.list_maintenance_points(
        servicio=servicio,
        barrio=barrio or None,
        solo_activos=solo_activos,
    )
    return {"count": len(points), "mantenimientos": points}


@tool("consultar_afectacion_por_barrio", args_schema=AfectacionBarrioInput)
def consultar_afectacion_por_barrio(barrio: str) -> dict[str, Any]:
    """Verifica mantenimientos oficiales y reportes ciudadanos de fallas en un barrio de Cali."""
    db = get_ops_db()
    loc = resolve_cali_location(barrio)
    target = loc.barrio if loc.barrio != "Cali (Centro)" else barrio.strip()
    maint = db.list_maintenance_points(barrio=target, solo_activos=True)
    failures = db.list_failure_reports(barrio=target, limit=25)
    open_failures = [f for f in failures if f["estado"] != "Resuelto"]
    return {
        "barrio_consultado": target,
        "comuna": loc.comuna,
        "coordenadas": {"lat": loc.lat, "lng": loc.lng},
        "mantenimientos_activos": maint,
        "reportes_falla_abiertos": len(open_failures),
        "tiene_afectacion": bool(maint or open_failures),
    }


@tool("suscribir_boletin_mantenimientos", args_schema=SuscribirBoletinInput)
def suscribir_boletin_mantenimientos(
    contacto: str,
    canal: Literal["whatsapp", "web", "telegram"] = "whatsapp",
    nombre: str = "",
    barrio_interes: str = "Todos",
    frecuencia: Literal["diaria", "semanal"] = "diaria",
) -> dict[str, Any]:
    """Suscribe al ciudadano al boletín diario de noticias y mantenimientos de OpenClaw."""
    db = get_ops_db()
    sub = db.subscribe_newsletter(
        contacto=contacto,
        canal=canal,
        nombre=nombre,
        barrio_interes=barrio_interes,
        frecuencia=frecuencia,
    )
    return {"status": "subscribed", "subscriber": sub}


@tool("radicar_pqrs_ciudadano", args_schema=RadicarPqrsInput)
def radicar_pqrs_ciudadano(
    tipo: PqrsType,
    servicio: ServiceType,
    identificador_tipo: IdentifierType,
    identificador_valor: str,
    nombre_ciudadano: str,
    barrio: str,
    descripcion: str,
    telefono_e164: str = "",
) -> dict[str, Any]:
    """Radica una PQRS oficial de EMCALI (contrato para clientes o cédula para no clientes)."""
    db = get_ops_db()
    req = PqrsCreateRequest(
        tipo=tipo,
        servicio=servicio,
        identificador_tipo=identificador_tipo,
        identificador_valor=identificador_valor,
        nombre_ciudadano=nombre_ciudadano,
        barrio=barrio,
        descripcion=descripcion,
        telefono_e164=telefono_e164,
    )
    ticket = db.create_pqrs(req)
    return {"status": "radicado", "ticket": ticket}


@tool("reportar_falla_servicio", args_schema=ReportarFallaInput)
def reportar_falla_servicio(
    servicio: ServiceType,
    identificador_tipo: IdentifierType,
    identificador_valor: str,
    barrio: str,
    descripcion: str,
    nombre_ciudadano: str = "Ciudadano EMCALI",
    direccion: str = "",
    telefono_e164: str = "",
) -> dict[str, Any]:
    """Registra una falla de servicio en Cali y actualiza las banderas de hotspots para brigadas."""
    db = get_ops_db()
    req = FailureReportCreateRequest(
        servicio=servicio,
        identificador_tipo=identificador_tipo,
        identificador_valor=identificador_valor,
        nombre_ciudadano=nombre_ciudadano,
        barrio=barrio,
        direccion=direccion,
        descripcion=descripcion,
        telefono_e164=telefono_e164,
    )
    report = db.create_failure_report(req)
    return {"status": "reported", "report": report}


@tool("consultar_estado_radicado", args_schema=ConsultarRadicadoInput)
def consultar_estado_radicado(radicado_id: str) -> dict[str, Any]:
    """Consulta el estado actual de un radicado PQRS o reporte de falla por su código."""
    db = get_ops_db()
    pqrs = db.get_pqrs(radicado_id)
    if pqrs:
        return {"found": True, "kind": "pqrs", "record": pqrs}
    failures = db.list_failure_reports(limit=200)
    for f in failures:
        if str(f["reporte_id"]).upper() == radicado_id.strip().upper():
            return {"found": True, "kind": "failure_report", "record": f}
    return {"found": False, "radicado_id": radicado_id}


@tool("listar_mis_radicados", args_schema=ListarMisRadicadosInput)
def listar_mis_radicados(identificador_valor: str) -> dict[str, Any]:
    """Lista todas las PQRS y reportes de fallas asociados a un número de contrato o cédula."""
    db = get_ops_db()
    digits = "".join(ch for ch in identificador_valor if ch.isdigit())
    pqrs = db.list_pqrs(identificador_valor=digits)
    failures = [
        f for f in db.list_failure_reports(limit=200) if str(f["identificador_valor"]) == digits
    ]
    return {
        "identificador_valor": digits,
        "pqrs_count": len(pqrs),
        "failure_reports_count": len(failures),
        "pqrs": pqrs,
        "failure_reports": failures,
    }


@tool("buscar_corpus_institucional_qdrant", args_schema=RagSearchInput)
def buscar_corpus_institucional_qdrant(
    query: str,
    section_filter: str | None = None,
    top_k: int = 5,
    search_mode: Literal["hybrid", "dense", "lexical"] = "hybrid",
) -> dict[str, Any]:
    """Recupera fragmentos verificados del corpus EMCALI en Qdrant con búsqueda híbrida y citas."""
    store = get_vector_store()
    hits = store.search(
        query,
        top_k=top_k,
        section_filter=section_filter,
        search_mode=search_mode,
    )
    return {
        "query": query,
        "hits_count": len(hits),
        "citations": [h.to_citation_dict() for h in hits],
    }


@tool("consultar_canales_y_puntos_atencion", args_schema=CanalesAtencionInput)
def consultar_canales_y_puntos_atencion(
    tipo_tramite: Literal["pagos", "pqrs", "fallas", "presencial", "todos"] = "todos",
) -> dict[str, Any]:
    """Devuelve los canales oficiales de atención presencial, telefónica y digital de EMCALI."""
    canales = {
        "telefonico": {
            "linea_gratuita_cali": "177",
            "linea_fija_nacional": "(602) 5240177",
            "horario": "24/7 para reporte de daños y emergencias; L-V 7:00-17:00 trámites.",
        },
        "pagos": {
            "portal_pse": "https://www.emcali.com.co/atencion-y-servicio-a-la-ciudadania/metodos-de-pago",
            "puntos_fisicos": ["SuperGIROS", "Efecty", "Gane", "Bancos autorizados"],
        },
        "pqrs": {
            "portal_web": "https://www.emcali.com.co/atencion-y-servicio-a-la-ciudadania",
            "modalidades": ["Cliente con número de contrato", "No cliente con número de cédula"],
            "plazo_legal": "15 días hábiles (Ley 142 de 1994 / Ley 1755 de 2015).",
        },
        "presencial": [
            {"sede": "CAM Torre EMCALI", "direccion": "Av. 2N # 10-70, Comuna 3"},
            {"sede": "CALI Sur / Cosmocentro", "direccion": "Calle 5 # 50-103"},
            {"sede": "CALI Norte / Versalles", "direccion": "Av. 3N # 23-45"},
        ],
    }
    if tipo_tramite != "todos" and tipo_tramite in canales:
        return {"tipo_tramite": tipo_tramite, "canal": canales[tipo_tramite]}
    return {"tipo_tramite": "todos", "canales": canales}


@tool("guardar_preferencia_usuario", args_schema=GuardarPreferenciaInput)
def guardar_preferencia_usuario(
    clave: str,
    etiqueta: str,
    valor: str,
    user_id: str = "ciudadano-cali",
) -> dict[str, Any]:
    """Guarda un dato del perfil del usuario en el Store persistente de largo plazo."""
    mm = get_memory_manager()
    ns = ("users", user_id, "memories")
    record = {
        "key": clave.strip().lower(),
        "label": etiqueta.strip(),
        "value": valor.strip(),
        "source_thread_id": "tool-m3",
        "updated_at": utc_iso(),
    }
    mm.store.put(ns, record["key"], record)
    return {"status": "saved", "namespace": "/".join(ns), "item": record}


@tool("consultar_perfil_memoria_usuario", args_schema=ConsultarPerfilMemoriaInput)
def consultar_perfil_memoria_usuario(
    user_id: str = "ciudadano-cali",
    consulta: str = "",
) -> dict[str, Any]:
    """Lee de forma auditable las preferencias y perfil almacenado del usuario."""
    mm = get_memory_manager()
    items = search_user_long_term_memories(user_id=user_id, store=mm.store, query=consulta)
    return {"user_id": user_id, "count": len(items), "memories": items}


# --- Herramientas Exclusivas de Gestión / Operaciones EMCALI (RBAC Manager Only) ---


@tool("activar_punto_mantenimiento", args_schema=ActivarMantenimientoInput)
def activar_punto_mantenimiento(
    titulo: str,
    servicio: ServiceType,
    barrio: str,
    descripcion: str,
    brigada_asignada: str = "Brigada Operativa EMCALI",
    inicio_estimado: str = "",
    fin_estimado: str = "",
) -> dict[str, Any]:
    """[SOLO GESTIÓN EMCALI] Activa un punto de mantenimiento en vivo sobre el mapa de Cali."""
    db = get_ops_db()
    req = MaintenanceCreateRequest(
        titulo=titulo,
        servicio=servicio,
        barrio=barrio,
        descripcion=descripcion,
        brigada_asignada=brigada_asignada,
        inicio_estimado=inicio_estimado,
        fin_estimado=fin_estimado,
        fuente="gestion_emcali",
        created_by="gerencia",
    )
    point = db.create_maintenance_point(req)
    return {"status": "activated", "maintenance": point}


@tool("asignar_brigada_reparacion", args_schema=AsignarBrigadaInput)
def asignar_brigada_reparacion(
    barrio: str,
    servicio: ServiceType,
    brigada_asignada: str,
    notas: str = "",
) -> dict[str, Any]:
    """[SOLO GESTIÓN EMCALI] Despacha una brigada a un hotspot de fallas y lo activa en el mapa."""
    db = get_ops_db()
    maint = db.dispatch_crew_for_hotspot(
        barrio=barrio,
        servicio=servicio,
        brigada_asignada=brigada_asignada,
        notas=notas,
    )
    return {"status": "dispatched", "maintenance": maint}


@tool("gestionar_estado_pqrs", args_schema=GestionarEstadoPqrsInput)
def gestionar_estado_pqrs(
    radicado_id: str,
    nuevo_estado: PqrsStatus,
    notas_gestion: str = "",
) -> dict[str, Any]:
    """[SOLO GESTIÓN EMCALI] Actualiza el estado operativo de un radicado PQRS."""
    db = get_ops_db()
    updated = db.update_pqrs_status(
        radicado_id,
        nuevo_estado=nuevo_estado,
        notas_gestion=notas_gestion,
    )
    if not updated:
        return {"found": False, "radicado_id": radicado_id}
    return {"found": True, "status": "updated", "ticket": updated}


@tool("generar_resumen_ejecutivo_operaciones", args_schema=ResumenEjecutivoInput)
def generar_resumen_ejecutivo_operaciones(
    sincronizar_noticias: bool = False,
    incluir_boletin: bool = False,
) -> dict[str, Any]:
    """[SOLO GESTIÓN EMCALI] Genera KPIs en vivo de PQRS, fallas, hotspots y mantenimientos."""
    db = get_ops_db()
    sync_report = sync_news_from_gold(db) if sincronizar_noticias else None
    summary = db.executive_summary()
    if sync_report is not None:
        summary["news_sync"] = sync_report
    if incluir_boletin:
        summary["daily_newsletter"] = build_daily_newsletter_digest(db)
    return summary


# ---------------------------------------------------------------------------
# Registro Canónico de las 20 Herramientas + Políticas RBAC y HITL
# ---------------------------------------------------------------------------

CITIZEN_TOOLS: tuple[BaseTool, ...] = (
    # Dominio A: Tarifas & Indicadores (4)
    consultar_tarifas_emcali_csv,
    consultar_indicadores_operativos_json,
    simular_factura_mensual,
    comparar_tarifas_trimestres,
    # Dominio B: Noticias, Mantenimientos & Mapa (4)
    consultar_noticias_emcali,
    listar_mantenimientos_activos,
    consultar_afectacion_por_barrio,
    suscribir_boletin_mantenimientos,
    # Dominio C: PQRS & Fallas (4)
    radicar_pqrs_ciudadano,
    reportar_falla_servicio,
    consultar_estado_radicado,
    listar_mis_radicados,
    # Dominio D: RAG, Memoria & Canales (4)
    buscar_corpus_institucional_qdrant,
    consultar_canales_y_puntos_atencion,
    guardar_preferencia_usuario,
    consultar_perfil_memoria_usuario,
)

MANAGER_ONLY_TOOLS: tuple[BaseTool, ...] = (
    # Dominio E: Gestión & Operaciones EMCALI (4)
    activar_punto_mantenimiento,
    asignar_brigada_reparacion,
    gestionar_estado_pqrs,
    generar_resumen_ejecutivo_operaciones,
)

ALL_20_TOOLS: tuple[BaseTool, ...] = (*CITIZEN_TOOLS, *MANAGER_ONLY_TOOLS)

TOOL_BY_NAME: dict[str, BaseTool] = {t.name: t for t in ALL_20_TOOLS}
MANAGER_ONLY_TOOL_NAMES: frozenset[str] = frozenset(t.name for t in MANAGER_ONLY_TOOLS)
HITL_SENSITIVE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "radicar_pqrs_ciudadano",
        "activar_punto_mantenimiento",
        "asignar_brigada_reparacion",
        "gestionar_estado_pqrs",
    }
)


def get_tools_for_role(role: UserRole = "citizen") -> list[BaseTool]:
    """Devuelve las herramientas autorizadas según el rol RBAC (tools.deny para citizen)."""
    if role == "manager":
        return list(ALL_20_TOOLS)
    return list(CITIZEN_TOOLS)


def describe_tool_catalog() -> list[dict[str, Any]]:
    """Describe las 20 herramientas con su esquema Pydantic, rol requerido y política HITL."""
    catalog: list[dict[str, Any]] = []
    for idx, t in enumerate(ALL_20_TOOLS, start=1):
        schema_cls = t.args_schema
        json_schema = (
            schema_cls.model_json_schema()
            if isinstance(schema_cls, type) and issubclass(schema_cls, BaseModel)
            else {}
        )
        catalog.append(
            {
                "index": idx,
                "name": t.name,
                "description": (t.description or "").strip(),
                "required_role": "manager" if t.name in MANAGER_ONLY_TOOL_NAMES else "citizen",
                "hitl_protected": t.name in HITL_SENSITIVE_TOOL_NAMES,
                "parameters_schema": json_schema,
            }
        )
    return catalog


def execute_tool_with_rbac(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    role: UserRole = "citizen",
    user_id: str = "ciudadano-cali",
    require_hitl: bool = False,
) -> dict[str, Any]:
    """Ejecuta una herramienta del catálogo aplicando RBAC (tools.deny) y compuerta HITL."""
    if tool_name not in TOOL_BY_NAME:
        return {"ok": False, "error": "TOOL_NOT_FOUND", "tool_name": tool_name}

    if role != "manager" and tool_name in MANAGER_ONLY_TOOL_NAMES:
        return {
            "ok": False,
            "error": "RBAC_DENIED",
            "tool_name": tool_name,
            "required_role": "manager",
            "current_role": role,
            "message": (
                f"Acceso denegado por política RBAC (`tools.deny`): la herramienta `{tool_name}` "
                "requiere rol autenticado de Gestión/Operaciones EMCALI."
            ),
        }

    if require_hitl and tool_name in HITL_SENSITIVE_TOOL_NAMES:
        db = get_ops_db()
        pending = db.create_hitl_action(
            tool_name=tool_name,
            user_id=user_id,
            role=role,
            summary=f"Confirmar ejecución de `{tool_name}` con parámetros: {arguments}",
            payload=arguments,
        )
        return {
            "ok": True,
            "status": "pending_hitl_approval",
            "hitl_action": pending,
            "message": (
                f"Acción sensible `{tool_name}` en espera de confirmación humana (HITL). "
                f"Código: `{pending['action_id']}`."
            ),
        }

    tool_fn = TOOL_BY_NAME[tool_name]
    result = tool_fn.invoke(arguments)
    return {"ok": True, "status": "executed", "tool_name": tool_name, "result": result}
