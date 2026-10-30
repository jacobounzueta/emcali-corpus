"""Plantillas y estrategias de Prompt Engineering para Q&A, Resumen y FAQ."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptStrategy:
    """Estrategia de prompt para experimentación y control de alucinaciones."""

    key: str
    name: str
    description: str
    instructions: str


PROMPT_STRATEGIES: dict[str, PromptStrategy] = {
    "estricto_citado": PromptStrategy(
        key="estricto_citado",
        name="Zero-Shot Estructurado con Anclaje Estricto y Citación (Recomendado)",
        description=(
            "Define rol institucional, reglas duras anti-alucinación, rechazo explícito de "
            "consultas fuera de contexto o transaccionales privadas y citación obligatoria de URLs."
        ),
        instructions=(
            "Eres el asistente virtual oficial de información pública de "
            "**EMCALI E.I.C.E. E.S.P.** "
            "(Empresas Municipales de Cali, Valle del Cauca, Colombia).\n\n"
            "### REGLAS INQUEBRANTABLES DE RESPUESTA (ANTI-ALUCINACIÓN)\n"
            "1. **Anclaje exclusivo en el contexto:** Responde ÚNICAMENTE con base en la "
            "`BASE DE CONOCIMIENTO OFICIAL` incluida al final de este prompt de sistema.\n"
            "2. **Prohibido inventar datos:** NUNCA inventes tarifas, números de teléfono, "
            "direcciones de sedes, horarios, porcentajes, enlaces ni requisitos que no aparezcan "
            "explícitamente en el contexto.\n"
            "3. **Información no disponible o fuera de alcance:** Si la respuesta no se encuentra "
            "en el contexto proporcionado, o si el usuario pregunta sobre temas ajenos a EMCALI, "
            'responde textualmente: *"No cuento con esa información en la base de conocimiento '
            'pública oficial de EMCALI disponible en este momento."* e indica qué temas '
            "relacionados sí puedes responder según el contexto.\n"
            "4. **Límite transaccional y de privacidad:** Si el usuario solicita consultar el "
            "saldo de su factura personal, radicar una PQR con datos privados o realizar un pago "
            "en el chat, aclara que este asistente es informativo y oriéntalo a los canales "
            "oficiales de atención y pago documentados en el contexto.\n"
            "5. **Citación obligatoria de fuentes:** Al final de tu respuesta, incluye una sección "
            "`### Fuentes oficiales` con viñetas en formato Markdown `[Título de la página](URL)` "
            "usando únicamente las URLs presentes en el contexto.\n"
            "6. **Tono y formato:** Mantén un tono claro, respetuoso, institucional y en español, "
            "organizando la respuesta con subtítulos o listas cuando facilite la lectura."
        ),
    ),
    "razonamiento_guiado": PromptStrategy(
        key="razonamiento_guiado",
        name="Verificación Paso a Paso (Grounded Reasoning + Evidencia)",
        description=(
            "Instruye al modelo a identificar primero las secciones relevantes del corpus, "
            "contrastar las cifras o requisitos exactos y luego redactar la respuesta verificada."
        ),
        instructions=(
            "Eres el analista y asistente documental de **EMCALI E.I.C.E. E.S.P.**.\n\n"
            "Antes de responder cualquier pregunta del ciudadano, aplica el siguiente protocolo:\n"
            "1. **Localización de evidencia:** Identifica qué documento(s) y sección(es) de la "
            "`BASE DE CONOCIMIENTO OFICIAL` contienen la información solicitada.\n"
            "2. **Verificación de fidelidad:** Comprueba que cada cifra, canal de atención, "
            "requisito o tarifa provenga literalmente del texto. Si un dato específico no "
            "aparece en el contexto, decláralo de forma explícita sin suponerlo.\n"
            "3. **Estructura de salida:**\n"
            "   - **Respuesta directa:** Síntesis clara y precisa para el usuario.\n"
            "   - **Detalles y requisitos:** Puntos clave extraídos del documento.\n"
            "   - **Fuentes oficiales:** Enlaces `[Título](URL)` tomados del bloque utilizado."
        ),
    ),
    "minimal_zero_shot": PromptStrategy(
        key="minimal_zero_shot",
        name="Zero-Shot Básico (Línea Base de Experimentación)",
        description=(
            "Prompt mínimo usado como línea base experimental para comparar el efecto de las "
            "restricciones explícitas anti-alucinación y las reglas de citación."
        ),
        instructions=(
            "Eres un asistente de preguntas y respuestas sobre EMCALI. Responde la pregunta del "
            "usuario en español basándote únicamente en el contexto proporcionado a continuación. "
            "Si la respuesta no está en el contexto, di que no tienes esa información."
        ),
    ),
}

DEFAULT_STRATEGY_KEY = "estricto_citado"


def build_qa_system_prompt(
    consolidated_context: str,
    *,
    strategy_key: str = DEFAULT_STRATEGY_KEY,
    custom_instructions: str | None = None,
) -> str:
    """Construye el prompt de sistema completo consolidando instrucciones y base de conocimiento."""
    strategy = PROMPT_STRATEGIES.get(strategy_key, PROMPT_STRATEGIES[DEFAULT_STRATEGY_KEY])
    instructions = (custom_instructions or strategy.instructions).strip()
    return (
        f"{instructions}\n\n"
        "================================================================================\n"
        "BASE DE CONOCIMIENTO OFICIAL CONSOLIDADA (CONTEXTO ÚNICO PERMITIDO)\n"
        "================================================================================\n\n"
        f"{consolidated_context.strip()}\n"
    )


def build_summary_prompt(
    consolidated_context: str,
    *,
    focus_topic: str = "",
) -> tuple[str, str]:
    """Construye los mensajes (system, user) para la tarea de Resumen Ejecutivo."""
    system_prompt = build_qa_system_prompt(
        consolidated_context,
        strategy_key="estricto_citado",
    )
    topic_clause = (
        f"enfocado específicamente en **{focus_topic.strip()}**"
        if focus_topic.strip()
        else "integral de todas las secciones cargadas en el contexto"
    )
    user_prompt = (
        f"Genera un **Resumen Ejecutivo Institucional** {topic_clause}, basándote únicamente "
        "en la base de conocimiento proporcionada.\n\n"
        "Estructura tu resumen con las siguientes secciones en Markdown:\n"
        "1. **Propósito e Identidad Institucional**: Qué es EMCALI, su misión, visión o alcance "
        "según los documentos disponibles.\n"
        "2. **Servicios y Líneas de Acción Principales**: Síntesis de los servicios cubiertos "
        "(Energía, Acueducto y Alcantarillado, Telecomunicaciones, Sostenibilidad, etc.).\n"
        "3. **Datos, Indicadores y Trámites Destacados**: Cifras, programas, tarifas o "
        "mecanismos de atención al ciudadano explícitos en el texto.\n"
        "4. **Fuentes Oficiales Consultadas**: Lista de enlaces `[Título](URL)` empleados."
    )
    return system_prompt, user_prompt


def build_faq_prompt(
    consolidated_context: str,
    *,
    num_questions: int = 8,
    focus_topic: str = "",
) -> tuple[str, str]:
    """Construye los mensajes (system, user) para la tarea de generación de FAQ."""
    system_prompt = build_qa_system_prompt(
        consolidated_context,
        strategy_key="estricto_citado",
    )
    topic_clause = (
        f"sobre el tema **{focus_topic.strip()}**"
        if focus_topic.strip()
        else "cubriendo las principales dudas de un ciudadano o cliente de EMCALI"
    )
    user_prompt = (
        f"Genera un catálogo oficial de **{num_questions} Preguntas Frecuentes (FAQ)** "
        f"{topic_clause}, extraídas estrictamente del contexto proporcionado.\n\n"
        "Para cada pregunta sigue exactamente este formato en Markdown:\n"
        "### N. ¿[Pregunta clara y realista de un usuario]?\n"
        "- **Categoría:** [Sección o servicio de EMCALI]\n"
        "- **Respuesta:** [Respuesta precisa y verificable basada únicamente en el contexto]\n"
        "- **Fuente oficial:** [Título de la página](URL)\n"
    )
    return system_prompt, user_prompt
