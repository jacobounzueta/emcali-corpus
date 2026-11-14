"""Router Agent con compuerta System One (Jev: Choice, Noul, Score y Box)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

RouteChoice = Literal[
    "direct_reply",
    "structured_tool",
    "rag_search",
    "hybrid_multi_tool",
]

GREETING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^\s*(?:¡?hola!?|buenos\s+d[ií]as|buenas\s+tardes|buenas\s+noches|saludos|"
        r"hey|oye|qu[eé]\s+tal|gracias|muchas\s+gracias|ok|listo|perfecto|eder|éder)"
        r"(?:[,.\s!¡?¿]+(?:hola|buenos\s+d[ií]as|buenas\s+tardes|buenas\s+noches|"
        r"saludos|c[oó]mo\s+est[aá]s|qu[eé]\s+tal|eder|éder|emcali|asistente))*[!.?\s]*$",
        re.IGNORECASE,
    ),
)

SELF_MEMORY_Intro_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^\s*(hola[,.\s]+)?(me\s+llamo|mi\s+nombre\s+es|trabajo\s+en|soy\s+[a-záéíóúñ]+\s+y\s+trabajo)",
        re.IGNORECASE,
    ),
)

SELF_MEMORY_QUERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(c[oó]mo\s+me\s+llamo|cu[aá]l\s+es\s+mi\s+nombre|d[oó]nde\s+trabajo|"
        r"en\s+qu[eé]\s+empresa\s+trabajo|qu[eé]\s+recuerdas\s+de\s+m[ií]|"
        r"cu[aá]l\s+es\s+mi\s+perfil|en\s+qu[eé]\s+estrato\s+vivo|"
        r"qu[eé]\s+sabes\s+sobre\s+m[ií])\b",
        re.IGNORECASE,
    ),
)

OUT_OF_SCOPE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(metro\s+subterr[aá]neo\s+de\s+bogot[aá]|vuelos\s+internacionales|"
        r"receta\s+de\s+cocina|campe[oó]n\s+del\s+mundial|"
        r"mi\s+contrato\s+es\s+el\s+\d+|mi\s+c[eé]dula\s+es\s+[\d.]+.*cu[aá]nto\s+debo\s+pagar|"
        r"(?:cancelar|terminar|anular|suspender|retirar|dar\s+de\s+baja)\s+(?:mi|el|un)?\s*"
        r"(?:contrato|servicio|plan|suscripci[oó]n)|"
        r"consultar\s+mi\s+factura|cu[aá]nto\s+debo|mi\s+saldo\s+actual)\b",
        re.IGNORECASE,
    ),
)

OFF_TOPIC_GENERAL_PATTERN = re.compile(
    r"\b(derivada|integral|arctan|arccot|seno|coseno|tangente|l[ií]mite|c[aá]lculo|"
    r"[aá]lgebra|ecuaci[oó]n|matriz|polinomio|logaritmo|graficar|simular|"
    r"python|numpy|matplotlib|sympy|pandas|javascript|typescript|java|c\+\+|"
    r"c[oó]digo\s+en|script\s+en|poema|chiste|hor[oó]scopo|receta)\b",
    re.IGNORECASE,
)

EMCALI_DOMAIN_ANCHORS: tuple[str, ...] = (
    "emcali",
    "tarifa",
    "tarifas",
    "estrato",
    "pqr",
    "acueducto",
    "alcantarillado",
    "energía",
    "energia",
    "fibra",
    "telco",
    "ley 1581",
    "datos personales",
    "sostenibilidad",
    "factura",
    "contrato",
    "pse",
    "gerente",
    "transparencia",
    "sede",
)

STRUCTURED_KEYWORDS: tuple[str, ...] = (
    "csv",
    "json",
    "tarifa",
    "tarifas",
    "estrato 1",
    "estrato 2",
    "estrato 3",
    "estrato 4",
    "estrato 5",
    "estrato 6",
    "primer trimestre",
    "segundo trimestre",
    "tercer trimestre",
    "2026-q1",
    "2026-q2",
    "2026-q3",
    "kwh",
    "cargo fijo",
    "subsidio",
    "contribución",
    "contribucion",
    "cuántas solicitudes",
    "cuantas solicitudes",
    "cuántas unidades",
    "cuantas unidades",
    "valor exacto",
    "promedio",
)

RAG_DOCUMENT_KEYWORDS: tuple[str, ...] = (
    "documento",
    "corpus",
    "política",
    "politica",
    "normatividad",
    "ley 1581",
    "ley 1712",
    "ley 1757",
    "misión",
    "mision",
    "visión",
    "vision",
    "factura digital",
    "formato zip",
    "medios de pago",
    "pse",
    "sostenibilidad",
    "quiénes somos",
    "quienes somos",
    "compromiso",
    "planta",
    "tratamiento",
    "derechos del titular",
    "aviso de privacidad",
    "canales de atención",
    "canales de atencion",
    "inyección",
    "inyeccion",
    "blindaje",
    "auditoría de seguridad",
    "auditoria de seguridad",
    "ignora las instrucciones",
)

COMPARISON_MIXED_KEYWORDS: tuple[str, ...] = (
    "compara",
    "comparar",
    "comparación",
    "comparacion",
    "contrasta",
    "versus",
    "vs",
    "frente a",
    "combina",
    "meta del documento",
    "tanto en el documento como en el csv",
    "diferencia entre la meta",
)


class JevBoxExtraction(BaseModel):
    """Primitiva Box de Jev: extracción estructurada de entidades y filtros de la consulta."""

    section_filter: str | None = Field(
        default=None,
        description="Sección del corpus detectada para filtrar el payload en Qdrant.",
    )
    servicio_csv: str = Field(
        default="todos",
        description=(
            "Servicio detectado para filtrar el CSV/JSON (energia, acueducto, "
            "alcantarillado, telco_fibra)."
        ),
    )
    estrato: int | None = Field(
        default=None,
        description="Estrato socioeconómico detectado (1 a 6).",
    )
    trimestre: str = Field(
        default="2026-Q3",
        description="Trimestre objetivo detectado (2026-Q1, 2026-Q2, 2026-Q3 o todos).",
    )
    is_greeting_or_chitchat: bool = Field(default=False)
    is_user_memory_operation: bool = Field(default=False)
    is_out_of_scope_or_private: bool = Field(default=False)
    is_security_canary_probe: bool = Field(default=False)


class JevRouterDecision(BaseModel):
    """Salida completa del Gatekeeper System One (Jev: Choice, Noul, Score, Box)."""

    choice: RouteChoice = Field(
        description="Primitiva Choice: ruta seleccionada por el Router Agent."
    )
    noul_triggered: bool = Field(
        default=False,
        description=(
            "Primitiva Noul: True cuando el gatekeeper bloquea búsquedas innecesarias "
            "(saludos, memoria pura o fuera de alcance)."
        ),
    )
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Primitiva Score: nivel de confianza calibrado [0.0, 1.0] de la decisión.",
    )
    box: JevBoxExtraction = Field(
        description="Primitiva Box: entidades estructuradas extraídas de la consulta."
    )
    rationale: str = Field(
        description="Justificación trazable de por qué el router eligió esta ruta."
    )
    tools_to_invoke: list[str] = Field(
        default_factory=list,
        description="Nombres de las herramientas (@tool) que se ejecutarán en este turno.",
    )


def _extract_box(question: str) -> JevBoxExtraction:
    """Extrae slots estructurados (Box) a partir de la consulta del usuario."""
    lowered = question.lower().strip()

    section_filter: str | None = None
    servicio_csv = "todos"

    if any(k in lowered for k in ("energía", "energia", "kwh", "transformador", "circuito")):
        section_filter = "energia"
        servicio_csv = "energia"
    elif any(k in lowered for k in ("acueducto", "agua potable", "m3")):
        section_filter = "acueducto"
        servicio_csv = "acueducto"
    elif "alcantarillado" in lowered or "aguas residuales" in lowered:
        section_filter = "acueducto"
        servicio_csv = "alcantarillado"
    elif any(
        k in lowered
        for k in ("telco", "telecomunicaciones", "fibra óptica", "fibra optica", "mbps", "enredos")
    ):
        section_filter = "telco"
        servicio_csv = "telco_fibra"
    elif any(k in lowered for k in ("datos personales", "ley 1581", "privacidad", "titular")):
        section_filter = "proteccion-de-datos-personales"
    elif any(k in lowered for k in ("factura digital", "formato zip")):
        section_filter = "terminos-condiciones-uso-factura-digital"
    elif any(k in lowered for k in ("sostenibilidad", "ambiental", "ley 1757")):
        section_filter = "sostenibilidad"
    elif any(
        k in lowered
        for k in ("misión", "mision", "visión", "vision", "transparencia", "normatividad")
    ):
        section_filter = "transparencia"
    elif any(
        k in lowered
        for k in ("gerente", "roger mina", "quiénes somos", "quienes somos", "centro digital")
    ):
        section_filter = "about"
    elif any(k in lowered for k in ("pse", "medios de pago", "metodos de pago")):
        section_filter = "atencion-y-servicio-a-la-ciudadania"

    estrato_val: int | None = None
    m_est = re.search(r"\bestrato\s*([1-6])\b", lowered)
    if m_est:
        estrato_val = int(m_est.group(1))

    trimestre = "2026-Q3"
    if any(k in lowered for k in ("primer trimestre", "2026-q1", "q1", "trimestre 1")):
        trimestre = "2026-Q1"
    elif any(k in lowered for k in ("segundo trimestre", "2026-q2", "q2", "trimestre 2")):
        trimestre = "2026-Q2"
    elif any(k in lowered for k in ("tercer trimestre", "2026-q3", "q3", "trimestre 3")):
        trimestre = "2026-Q3"
    elif any(
        k in lowered
        for k in ("todos los trimestres", "evolución trimestral", "evolucion trimestral")
    ):
        trimestre = "todos"

    is_greeting = any(p.search(lowered) for p in GREETING_PATTERNS)
    is_mem_intro = any(p.search(lowered) for p in SELF_MEMORY_Intro_PATTERNS) and "?" not in lowered
    is_mem_query = any(p.search(lowered) for p in SELF_MEMORY_QUERY_PATTERNS)
    has_domain_anchor = any(anchor in lowered for anchor in EMCALI_DOMAIN_ANCHORS)
    is_out = any(p.search(lowered) for p in OUT_OF_SCOPE_PATTERNS) or (
        bool(OFF_TOPIC_GENERAL_PATTERN.search(lowered)) and not has_domain_anchor
    )
    is_canary = any(
        k in lowered
        for k in (
            "inyección",
            "inyeccion",
            "blindaje",
            "ignora las instrucciones",
            "auditoría de seguridad",
            "auditoria de seguridad",
            "prompt injection",
        )
    )

    return JevBoxExtraction(
        section_filter=section_filter,
        servicio_csv=servicio_csv,
        estrato=estrato_val,
        trimestre=trimestre,
        is_greeting_or_chitchat=is_greeting,
        is_user_memory_operation=is_mem_intro or is_mem_query,
        is_out_of_scope_or_private=is_out,
        is_security_canary_probe=is_canary,
    )


def route_query_with_jev(question: str) -> JevRouterDecision:
    """Evalúa la consulta mediante las 4 primitivas Jev (Choice, Noul, Score, Box)."""
    clean_q = question.strip()
    lowered = clean_q.lower()
    box = _extract_box(clean_q)

    # 1. Compuerta Noul: Saludos triviales, memoria de usuario o fuera de alcance
    if box.is_greeting_or_chitchat:
        return JevRouterDecision(
            choice="direct_reply",
            noul_triggered=True,
            score=0.99,
            box=box,
            rationale=(
                "Jev Noul Gate activada: saludo o interacción conversacional trivial. "
                "Se responde directamente sin ejecutar búsquedas en Qdrant ni herramientas "
                "CSV/JSON."
            ),
            tools_to_invoke=[],
        )

    if box.is_user_memory_operation:
        return JevRouterDecision(
            choice="direct_reply",
            noul_triggered=True,
            score=0.97,
            box=box,
            rationale=(
                "Jev Noul Gate activada: turno de registro o consulta de memoria del perfil "
                "del usuario "
                "(Checkpointer / Store). Se resuelve desde la capa de memoria sin gastar "
                "búsquedas vectoriales."
            ),
            tools_to_invoke=[],
        )

    if box.is_out_of_scope_or_private:
        return JevRouterDecision(
            choice="direct_reply",
            noul_triggered=True,
            score=0.96,
            box=box,
            rationale=(
                "Jev Noul Gate activada: consulta fuera de alcance institucional o solicitud "
                "transaccional privada. Se aplica rechazo seguro sin invocar herramientas "
                "innecesarias."
            ),
            tools_to_invoke=[],
        )

    # 2. Caso de auditoría de blindaje RAG (Caso 5)
    if box.is_security_canary_probe:
        return JevRouterDecision(
            choice="rag_search",
            noul_triggered=False,
            score=0.98,
            box=box,
            rationale=(
                "Jev Choice=rag_search: prueba de blindaje contra inyección indirecta sobre "
                "documentos "
                "recuperados de Qdrant con delimitador de datos pasivos."
            ),
            tools_to_invoke=["buscar_corpus_qdrant"],
        )

    struct_hits = sum(1 for kw in STRUCTURED_KEYWORDS if kw in lowered)
    rag_hits = sum(1 for kw in RAG_DOCUMENT_KEYWORDS if kw in lowered)
    mixed_hits = sum(1 for kw in COMPARISON_MIXED_KEYWORDS if kw in lowered)

    # 3. Enrutamiento Mixto (Caso 4: combina CSV/JSON estructurado + RAG documental Qdrant)
    if mixed_hits > 0 or (struct_hits >= 1 and rag_hits >= 1):
        confidence = min(0.98, round(0.84 + 0.04 * (struct_hits + rag_hits + mixed_hits), 2))
        return JevRouterDecision(
            choice="hybrid_multi_tool",
            noul_triggered=False,
            score=confidence,
            box=box,
            rationale=(
                "Jev Choice=hybrid_multi_tool: la consulta exige cruzar cifras exactas del "
                "CSV/JSON "
                "(validado con Pydantic) con contexto normativo/documental recuperado de Qdrant."
            ),
            tools_to_invoke=[
                "consultar_tarifas_emcali_csv",
                "consultar_indicadores_operativos_json",
                "buscar_corpus_qdrant",
            ],
        )

    # 4. Herramienta determinista CSV/JSON (Caso 3)
    if struct_hits >= 1 and rag_hits == 0:
        confidence = min(0.97, round(0.85 + 0.04 * struct_hits, 2))
        return JevRouterDecision(
            choice="structured_tool",
            noul_triggered=False,
            score=confidence,
            box=box,
            rationale=(
                "Jev Choice=structured_tool: consulta cuantitativa/tabular sobre tarifas, "
                "estratos, "
                "trimestres o indicadores PQR. Se delega a la @tool determinista con esquema "
                "Pydantic."
            ),
            tools_to_invoke=[
                "consultar_tarifas_emcali_csv",
                "consultar_indicadores_operativos_json",
            ],
        )

    # 5. Por defecto: RAG documental sobre Qdrant (Caso 1)
    confidence = min(0.95, round(0.80 + 0.03 * max(1, rag_hits), 2))
    return JevRouterDecision(
        choice="rag_search",
        noul_triggered=False,
        score=confidence,
        box=box,
        rationale=(
            "Jev Choice=rag_search: consulta documental sobre servicios, normatividad o canales "
            "de EMCALI. Se recupera top-k en Qdrant con índice ANN HNSW y filtro de payload."
        ),
        tools_to_invoke=["buscar_corpus_qdrant"],
    )


def serialize_router_decision(decision: JevRouterDecision) -> dict[str, Any]:
    """Convierte la decisión Jev en diccionario JSON serializable."""
    return decision.model_dump()
