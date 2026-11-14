"""Herramientas deterministas (@tool) sobre CSV y JSON con esquemas Pydantic v2."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from emcali_corpus import config

STRUCTURED_DIR = config.DATA_DIR / "structured"
TARIFAS_CSV_PATH = STRUCTURED_DIR / "tarifas_servicios_emcali.csv"
INDICADORES_JSON_PATH = STRUCTURED_DIR / "indicadores_operativos_emcali.json"


class TarifaRecord(BaseModel):
    """Fila validada del dataset CSV de tarifas y consumos por estrato y trimestre."""

    servicio: str = Field(
        description="Servicio público: energia, acueducto, alcantarillado, telco_fibra"
    )
    estrato: int = Field(
        ge=0, le=6, description="Estrato socioeconómico (1-6, o 0 para comercial/industrial)"
    )
    segmento: str = Field(description="Segmento tarifario: Residencial, Comercial o Industrial")
    trimestre: str = Field(description="Periodo trimestral ISO, ej. 2026-Q1, 2026-Q2, 2026-Q3")
    unidad: str = Field(description="Unidad de cobro: kWh, m3, Mbps_300, Mbps_500, Mbps_900")
    tarifa_base_cop: float = Field(
        ge=0.0, description="Tarifa unitaria base en pesos colombianos (COP)"
    )
    subsidio_contribucion_pct: float = Field(
        description="Porcentaje de subsidio (negativo) o contribución (positivo)"
    )
    tarifa_aplicada_cop: float = Field(
        ge=0.0, description="Tarifa final aplicada en COP tras subsidio/contribución"
    )
    consumo_promedio_mes: float = Field(
        ge=0.0, description="Consumo mensual promedio por suscriptor"
    )
    cargo_fijo_cop: float = Field(ge=0.0, description="Cargo fijo mensual en COP")
    meta_documento_cop: float = Field(
        ge=0.0, description="Meta tarifaria de referencia en el plan corporativo"
    )

    @property
    def factura_estimada_mes_cop(self) -> float:
        """Cálculo determinista del valor mensual estimado (consumo * tarifa + cargo fijo)."""
        if self.servicio == "telco_fibra":
            return round(self.tarifa_aplicada_cop + self.cargo_fijo_cop, 2)
        return round(self.consumo_promedio_mes * self.tarifa_aplicada_cop + self.cargo_fijo_cop, 2)

    @property
    def desviacion_vs_meta_cop(self) -> float:
        """Diferencia exacta entre la tarifa aplicada y la meta del documento corporativo."""
        return round(self.tarifa_aplicada_cop - self.meta_documento_cop, 2)


class IndicadorOperativoRecord(BaseModel):
    """Indicador cuantitativo oficial validado desde el archivo JSON estructurado."""

    codigo: str = Field(description="Código único del indicador operativo o SLA")
    servicio: str = Field(description="Servicio o dependencia asociada")
    indicador: str = Field(description="Nombre descriptivo del indicador")
    valor_reportado: float = Field(description="Valor numérico exacto reportado en el dataset")
    meta_plan_corporativo: float = Field(
        description="Meta oficial definida en el documento corporativo"
    )
    unidad: str = Field(description="Unidad de medida del indicador")
    trimestre: str = Field(description="Trimestre de corte del dato")
    fuente_url: str = Field(description="URL oficial de atribución en emcali.com.co")

    @property
    def cumplimiento_meta_pct(self) -> float:
        """Porcentaje determinista de cumplimiento frente a la meta corporativa."""
        if self.meta_plan_corporativo == 0:
            return 100.0
        return round((self.valor_reportado / self.meta_plan_corporativo) * 100.0, 2)


class TarifasFilterInput(BaseModel):
    """Esquema Pydantic de entrada para la herramienta determinista de tarifas CSV."""

    servicio: Literal["energia", "acueducto", "alcantarillado", "telco_fibra", "todos"] = Field(
        default="todos",
        description="Servicio público a consultar en el CSV.",
    )
    estrato: int | None = Field(
        default=None,
        ge=0,
        le=6,
        description="Filtrar por estrato específico (1 a 6, o 0 para Comercial/Industrial).",
    )
    segmento: Literal["Residencial", "Comercial", "Industrial", "todos"] = Field(
        default="todos",
        description="Segmento tarifario a consultar.",
    )
    trimestre: Literal["2026-Q1", "2026-Q2", "2026-Q3", "todos"] = Field(
        default="2026-Q3",
        description="Trimestre de consulta (por defecto 2026-Q3 o 'todos').",
    )


class IndicadoresFilterInput(BaseModel):
    """Esquema Pydantic de entrada para la herramienta determinista de indicadores JSON."""

    servicio: str = Field(
        default="todos",
        description=(
            "Servicio o área: energia, telco, proteccion-de-datos-personales, "
            "atencion-y-servicio-a-la-ciudadania o todos."
        ),
    )
    trimestre: str = Field(
        default="todos",
        description="Trimestre a filtrar: 2026-Q1, 2026-Q2, 2026-Q3 o todos.",
    )
    palabra_clave: str = Field(
        default="",
        description=(
            "Término opcional para filtrar indicadores (ej. 'PQR', 'fibra', 'clientes', 'días')."
        ),
    )


class StructuredToolExecutionReport(BaseModel):
    """Respuesta estructurada y auditable de una ejecución de herramienta determinista."""

    tool_name: str
    source_file: str
    filters_applied: dict[str, Any]
    records_matched: int
    summary_metrics: dict[str, float | int | str]
    rows: list[dict[str, Any]]


def load_tarifas_csv(csv_path: Path = TARIFAS_CSV_PATH) -> list[TarifaRecord]:
    """Carga y valida con Pydantic todas las filas del archivo CSV de tarifas."""
    if not csv_path.is_file():
        return []
    records: list[TarifaRecord] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            records.append(
                TarifaRecord(
                    servicio=str(row["servicio"]).strip(),
                    estrato=int(row["estrato"]),
                    segmento=str(row["segmento"]).strip(),
                    trimestre=str(row["trimestre"]).strip(),
                    unidad=str(row["unidad"]).strip(),
                    tarifa_base_cop=float(row["tarifa_base_cop"]),
                    subsidio_contribucion_pct=float(row["subsidio_contribucion_pct"]),
                    tarifa_aplicada_cop=float(row["tarifa_aplicada_cop"]),
                    consumo_promedio_mes=float(row["consumo_promedio_mes"]),
                    cargo_fijo_cop=float(row["cargo_fijo_cop"]),
                    meta_documento_cop=float(row["meta_documento_cop"]),
                )
            )
    return records


def load_indicadores_json(
    json_path: Path = INDICADORES_JSON_PATH,
) -> tuple[dict[str, Any], list[IndicadorOperativoRecord]]:
    """Carga y valida con Pydantic el archivo JSON de indicadores operativos y metas."""
    if not json_path.is_file():
        return {}, []
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    metadata = {
        "entidad": raw.get("entidad", "EMCALI E.I.C.E. E.S.P."),
        "nit": raw.get("nit", "890.399.003-4"),
        "domicilio": raw.get("domicilio", ""),
        "gerencia": raw.get("gerencia", {}),
    }
    items = [
        IndicadorOperativoRecord.model_validate(item)
        for item in raw.get("indicadores_infraestructura", [])
    ]
    return metadata, items


def query_tarifas_structured(
    *,
    servicio: str = "todos",
    estrato: int | None = None,
    segmento: str = "todos",
    trimestre: str = "2026-Q3",
    csv_path: Path = TARIFAS_CSV_PATH,
) -> StructuredToolExecutionReport:
    """Ejecuta una consulta determinista sobre el CSV de tarifas y calcula agregaciones exactas."""
    all_rows = load_tarifas_csv(csv_path)
    filtered: list[TarifaRecord] = []
    for row in all_rows:
        if servicio != "todos" and row.servicio != servicio:
            continue
        if estrato is not None and row.estrato != estrato:
            continue
        if segmento != "todos" and row.segmento.lower() != segmento.lower():
            continue
        if trimestre != "todos" and row.trimestre != trimestre:
            continue
        filtered.append(row)

    serialized_rows = [
        {
            **row.model_dump(),
            "factura_estimada_mes_cop": row.factura_estimada_mes_cop,
            "desviacion_vs_meta_cop": row.desviacion_vs_meta_cop,
        }
        for row in filtered
    ]

    if filtered:
        avg_tarifa = round(sum(r.tarifa_aplicada_cop for r in filtered) / len(filtered), 2)
        min_tarifa = round(min(r.tarifa_aplicada_cop for r in filtered), 2)
        max_tarifa = round(max(r.tarifa_aplicada_cop for r in filtered), 2)
        avg_factura = round(sum(r.factura_estimada_mes_cop for r in filtered) / len(filtered), 2)
    else:
        avg_tarifa = 0.0
        min_tarifa = 0.0
        max_tarifa = 0.0
        avg_factura = 0.0

    return StructuredToolExecutionReport(
        tool_name="consultar_tarifas_emcali_csv",
        source_file="data/structured/tarifas_servicios_emcali.csv",
        filters_applied={
            "servicio": servicio,
            "estrato": estrato,
            "segmento": segmento,
            "trimestre": trimestre,
        },
        records_matched=len(filtered),
        summary_metrics={
            "tarifa_aplicada_promedio_cop": avg_tarifa,
            "tarifa_aplicada_min_cop": min_tarifa,
            "tarifa_aplicada_max_cop": max_tarifa,
            "factura_mensual_estimada_promedio_cop": avg_factura,
        },
        rows=serialized_rows,
    )


def query_indicadores_structured(
    *,
    servicio: str = "todos",
    trimestre: str = "todos",
    palabra_clave: str = "",
    json_path: Path = INDICADORES_JSON_PATH,
) -> StructuredToolExecutionReport:
    """Ejecuta una consulta determinista sobre el JSON de indicadores operativos y PQR."""
    metadata, all_items = load_indicadores_json(json_path)
    kw = palabra_clave.strip().lower()

    filtered: list[IndicadorOperativoRecord] = []
    for item in all_items:
        if servicio != "todos" and item.servicio != servicio:
            continue
        if trimestre != "todos" and item.trimestre != trimestre:
            continue
        if (
            kw
            and kw not in item.indicador.lower()
            and kw not in item.codigo.lower()
            and kw not in item.servicio.lower()
        ):
            continue
        filtered.append(item)

    if not filtered and kw:
        filtered = list(all_items)

    serialized_rows = [
        {
            **item.model_dump(),
            "cumplimiento_meta_pct": item.cumplimiento_meta_pct,
            "diferencia_vs_meta": round(item.valor_reportado - item.meta_plan_corporativo, 2),
        }
        for item in filtered
    ]

    pqr_rows = [item for item in all_items if item.codigo.startswith("PQR-GLOBAL")]
    total_pqr_2026 = int(sum(item.valor_reportado for item in pqr_rows))
    avg_cumplimiento = (
        round(sum(item.cumplimiento_meta_pct for item in filtered) / len(filtered), 2)
        if filtered
        else 0.0
    )

    return StructuredToolExecutionReport(
        tool_name="consultar_indicadores_operativos_json",
        source_file="data/structured/indicadores_operativos_emcali.json",
        filters_applied={
            "servicio": servicio,
            "trimestre": trimestre,
            "palabra_clave": palabra_clave,
        },
        records_matched=len(filtered),
        summary_metrics={
            "entidad": str(metadata.get("entidad", "EMCALI E.I.C.E. E.S.P.")),
            "nit": str(metadata.get("nit", "890.399.003-4")),
            "cumplimiento_promedio_meta_pct": avg_cumplimiento,
            "total_pqr_atendidas_acumulado_2026": total_pqr_2026,
        },
        rows=serialized_rows,
    )


@tool("consultar_tarifas_emcali_csv", args_schema=TarifasFilterInput)
def consultar_tarifas_emcali_csv(
    servicio: Literal["energia", "acueducto", "alcantarillado", "telco_fibra", "todos"] = "todos",
    estrato: int | None = None,
    segmento: Literal["Residencial", "Comercial", "Industrial", "todos"] = "todos",
    trimestre: Literal["2026-Q1", "2026-Q2", "2026-Q3", "todos"] = "2026-Q3",
) -> dict[str, Any]:
    """Consulta determinísticamente el archivo CSV de tarifas, subsidios y metas de EMCALI."""
    report = query_tarifas_structured(
        servicio=servicio,
        estrato=estrato,
        segmento=segmento,
        trimestre=trimestre,
    )
    return report.model_dump()


@tool("consultar_indicadores_operativos_json", args_schema=IndicadoresFilterInput)
def consultar_indicadores_operativos_json(
    servicio: str = "todos",
    trimestre: str = "todos",
    palabra_clave: str = "",
) -> dict[str, Any]:
    """Consulta determinísticamente el JSON de indicadores de infraestructura, PQR y SLAs
    de EMCALI."""
    report = query_indicadores_structured(
        servicio=servicio,
        trimestre=trimestre,
        palabra_clave=palabra_clave,
    )
    return report.model_dump()


def execute_smart_structured_tools(
    question: str,
    extracted_box: dict[str, Any] | None = None,
) -> list[StructuredToolExecutionReport]:
    """Determina y ejecuta las consultas estructuradas CSV/JSON pertinentes para la pregunta."""
    box = extracted_box or {}
    lowered = question.lower()
    reports: list[StructuredToolExecutionReport] = []

    servicio_csv = str(box.get("servicio_csv") or "todos")
    if servicio_csv == "todos":
        if "energ" in lowered or "kwh" in lowered:
            servicio_csv = "energia"
        elif "acueducto" in lowered or "agua" in lowered:
            servicio_csv = "acueducto"
        elif "alcantarillado" in lowered:
            servicio_csv = "alcantarillado"
        elif "fibra" in lowered or "internet" in lowered or "telco" in lowered or "mbps" in lowered:
            servicio_csv = "telco_fibra"

    estrato_val: int | None = box.get("estrato")
    if estrato_val is None:
        for num in range(1, 7):
            if f"estrato {num}" in lowered or f"estrato {num}" in lowered.replace("-", " "):
                estrato_val = num
                break

    trimestre_val = str(box.get("trimestre") or "2026-Q3")
    if "primer trimestre" in lowered or "q1" in lowered or "trimestre 1" in lowered:
        trimestre_val = "2026-Q1"
    elif "segundo trimestre" in lowered or "q2" in lowered or "trimestre 2" in lowered:
        trimestre_val = "2026-Q2"
    elif "tercer trimestre" in lowered or "q3" in lowered or "trimestre 3" in lowered:
        trimestre_val = "2026-Q3"
    elif "compar" in lowered or "evoluci" in lowered or "todos los trimestres" in lowered:
        trimestre_val = "todos"

    wants_tarifas = any(
        token in lowered
        for token in (
            "tarifa",
            "costo",
            "precio",
            "estrato",
            "subsidio",
            "contribuci",
            "kwh",
            "m3",
            "cargo fijo",
            "csv",
            "meta",
            "factura",
            "plan",
            "mbps",
        )
    )
    wants_indicadores = any(
        token in lowered
        for token in (
            "indicador",
            "pqr",
            "clientes",
            "red",
            "kilómetro",
            "km",
            "cobertura",
            "circuito",
            "monitoreo",
            "cables",
            "enredos",
            "días hábiles",
            "plazo",
            "trimestre",
            "unidades",
            "solicitudes",
            "meta",
            "json",
            "nit",
            "gerente",
        )
    )

    if wants_tarifas or not wants_indicadores:
        reports.append(
            query_tarifas_structured(
                servicio=servicio_csv,
                estrato=estrato_val,
                trimestre=trimestre_val,
            )
        )

    if wants_indicadores:
        servicio_json = "todos"
        kw_json = ""
        if "pqr" in lowered or "solicitudes" in lowered:
            kw_json = "pqr"
        elif servicio_csv == "energia":
            servicio_json = "energia"
        elif servicio_csv == "telco_fibra":
            servicio_json = "telco"
        reports.append(
            query_indicadores_structured(
                servicio=servicio_json,
                trimestre=trimestre_val
                if "pqr" in lowered or "solicitudes" in lowered
                else "todos",
                palabra_clave=kw_json,
            )
        )

    return reports
