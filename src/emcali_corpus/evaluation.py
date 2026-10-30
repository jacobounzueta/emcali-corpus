"""Batería de pruebas (22 preguntas) y evaluación automática del sistema Q&A."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from emcali_corpus import config
from emcali_corpus.assistant import AssistantReply, AssistantSettings, answer_question
from emcali_corpus.knowledge import KnowledgeBaseBundle, consolidate_knowledge_base
from emcali_corpus.prompts import DEFAULT_STRATEGY_KEY

EVALUATION_REPORT_PATH = config.PROJECT_ROOT / "docs" / "evaluacion_preguntas.md"


@dataclass(frozen=True, slots=True)
class BenchmarkQuestion:
    """Pregunta de prueba dentro del alcance definido para EMCALI."""

    id: int
    category: str
    question: str
    expected_keywords: tuple[str, ...]
    expected_section: str
    is_out_of_scope: bool = False


@dataclass(frozen=True, slots=True)
class QuestionEvaluation:
    """Resultado de evaluar una respuesta del sistema Q&A frente a una pregunta del benchmark."""

    item: BenchmarkQuestion
    answer: str
    matched_keywords: tuple[str, ...]
    keyword_recall: float
    has_source_citation: bool
    passed: bool


BENCHMARK_QUESTIONS: tuple[BenchmarkQuestion, ...] = (
    BenchmarkQuestion(
        id=1,
        category="Identidad y Gobierno Corporativo",
        question=(
            "¿Quién es el Gerente General de EMCALI y quiénes lideran las unidades de "
            "Energía, Acueducto y Telecomunicaciones?"
        ),
        expected_keywords=(
            "Roger Mina",
            "Mario Germán Ocaña",
            "Diego Fernando Carabali",
            "Roberto Carlos Angulo",
        ),
        expected_section="about",
    ),
    BenchmarkQuestion(
        id=2,
        category="Identidad y Gobierno Corporativo",
        question=(
            "¿Cuál es el NIT de EMCALI E.I.C.E. E.S.P. y dónde queda su domicilio "
            "principal en Cali?"
        ),
        expected_keywords=("890.399.003-4", "CAM", "TORRE EMCALI"),
        expected_section="proteccion-de-datos-personales",
    ),
    BenchmarkQuestion(
        id=3,
        category="Identidad y Gobierno Corporativo",
        question=(
            "¿En qué consiste el proceso de transformación actual de EMCALI y qué "
            "iniciativas destaca en innovación y sostenibilidad?"
        ),
        expected_keywords=("Centro Digital", "fibra óptica", "paneles solares", "La Reforma"),
        expected_section="about",
    ),
    BenchmarkQuestion(
        id=4,
        category="Servicio de Energía",
        question=(
            "¿Cuántos clientes atiende EMCALI en el servicio de energía y qué "
            "infraestructura de red reporta?"
        ),
        expected_keywords=("790.000", "19.000", "750", "3.000"),
        expected_section="energia",
    ),
    BenchmarkQuestion(
        id=5,
        category="Servicio de Energía",
        question=(
            "¿Qué trámites y opciones de atención ofrece la sección de Energía de "
            "EMCALI para los usuarios?"
        ),
        expected_keywords=("PQRS", "factura", "falla", "tarifas"),
        expected_section="energia",
    ),
    BenchmarkQuestion(
        id=6,
        category="Servicio de Energía",
        question=(
            "¿Qué información publica EMCALI sobre las tarifas del servicio de energía eléctrica?"
        ),
        expected_keywords=("tarifas", "energía", "emcali.com.co"),
        expected_section="energia",
    ),
    BenchmarkQuestion(
        id=7,
        category="Acueducto y Alcantarillado",
        question="¿Cuál es el compromiso de EMCALI en el servicio de Acueducto y Alcantarillado?",
        expected_keywords=(
            "agua potable",
            "aguas residuales",
            "plantas de tratamiento",
            "saneamiento",
        ),
        expected_section="acueducto",
    ),
    BenchmarkQuestion(
        id=8,
        category="Acueducto y Alcantarillado",
        question=(
            "¿Qué informes técnicos o ambientales publica EMCALI dentro de la sección "
            "de Acueducto y Alcantarillado?"
        ),
        expected_keywords=("calidad", "agua", "vertimientos", "alcantarillado"),
        expected_section="acueducto",
    ),
    BenchmarkQuestion(
        id=9,
        category="Acueducto y Alcantarillado",
        question=(
            "¿Dónde se pueden consultar las tarifas vigentes de acueducto y "
            "alcantarillado en EMCALI?"
        ),
        expected_keywords=("tarifas", "acueducto", "emcali.com.co"),
        expected_section="acueducto",
    ),
    BenchmarkQuestion(
        id=10,
        category="Telecomunicaciones (Telco)",
        question=(
            "¿Qué ventajas y características tienen los planes de fibra óptica de "
            "EMCALI Telecomunicaciones?"
        ),
        expected_keywords=("fibra óptica", "24/7", "diagnóstico remoto", "factura"),
        expected_section="telco",
    ),
    BenchmarkQuestion(
        id=11,
        category="Telecomunicaciones (Telco)",
        question=(
            "¿Qué cobertura de fibra óptica reporta EMCALI en Cali y qué documentos "
            "ofrece para usuarios de servicios fijos?"
        ),
        expected_keywords=("92%", "Contrato único", "Guía de Uso"),
        expected_section="telco",
    ),
    BenchmarkQuestion(
        id=12,
        category="Telecomunicaciones (Telco)",
        question=(
            "¿Qué es la 'Operación Cali sin enredos' mencionada en la sección de "
            "Telecomunicaciones?"
        ),
        expected_keywords=("cable", "57 mil", "desmonte"),
        expected_section="telco",
    ),
    BenchmarkQuestion(
        id=13,
        category="Atención al Ciudadano y Pagos",
        question=(
            "¿Cuáles son las líneas telefónicas y los canales presenciales de atención "
            "al ciudadano de EMCALI?"
        ),
        expected_keywords=("177", "5240177", "CAP", "CALI"),
        expected_section="proteccion-de-datos-personales",
    ),
    BenchmarkQuestion(
        id=14,
        category="Atención al Ciudadano y Pagos",
        question=(
            "¿Qué medios de pago electrónicos menciona EMCALI para pagar las facturas "
            "de servicios públicos?"
        ),
        expected_keywords=("PSE", "canales de pago", "metodos-de-pago"),
        expected_section="atencion-y-servicio-a-la-ciudadania",
    ),
    BenchmarkQuestion(
        id=15,
        category="Factura Digital",
        question=(
            "¿En qué formato se entrega la Factura Digital de EMCALI por correo "
            "electrónico y en qué se diferencia de la factura electrónica?"
        ),
        expected_keywords=("ZIP", "correo electrónico", "DIAN"),
        expected_section="terminos-condiciones-uso-factura-digital",
    ),
    BenchmarkQuestion(
        id=16,
        category="Factura Digital",
        question=(
            "¿Qué ocurre si el correo de la Factura Digital es rechazado o el buzón "
            "del usuario está lleno, y cómo puede volver a la factura física?"
        ),
        expected_keywords=("impresión física", "próximo periodo", "Centros de Atención"),
        expected_section="terminos-condiciones-uso-factura-digital",
    ),
    BenchmarkQuestion(
        id=17,
        category="Protección de Datos Personales",
        question=(
            "Según la Política de Tratamiento de Datos Personales de EMCALI "
            "(Ley 1581 de 2012), ¿cuántos días hábiles máximo tardan en responderse "
            "las consultas y los reclamos?"
        ),
        expected_keywords=("10", "15", "días hábiles"),
        expected_section="proteccion-de-datos-personales",
    ),
    BenchmarkQuestion(
        id=18,
        category="Protección de Datos Personales",
        question=(
            "¿Qué derechos tiene el titular de los datos personales frente a EMCALI "
            "según su aviso de privacidad?"
        ),
        expected_keywords=(
            "conocer",
            "actualizar",
            "rectificar",
            "Superintendencia de Industria y Comercio",
        ),
        expected_section="proteccion-de-datos-personales",
    ),
    BenchmarkQuestion(
        id=19,
        category="Sostenibilidad y Transparencia",
        question=(
            "¿Qué leyes y normativas guían la participación ciudadana y sostenibilidad "
            "en EMCALI y qué subgerencia lidera el tema ambiental?"
        ),
        expected_keywords=(
            "Ley 1757",
            "Ley 1712",
            "Subgerencia de Responsabilidad Social Ambiental Empresarial",
        ),
        expected_section="sostenibilidad",
    ),
    BenchmarkQuestion(
        id=20,
        category="Transparencia",
        question=(
            "¿Qué información se publica en la sección de Misión, Visión y Normatividad "
            "del portal de Transparencia de EMCALI?"
        ),
        expected_keywords=("transparencia", "mision-y-vision", "normatividad"),
        expected_section="transparencia",
    ),
    BenchmarkQuestion(
        id=21,
        category="Control Anti-Alucinación (Límite Transaccional)",
        question=(
            "Mi contrato es el 987654321 y mi cédula es 1.144.000.000, ¿cuánto debo "
            "pagar exactamente en mi factura de este mes?"
        ),
        expected_keywords=("informativo", "canales", "emcali.com.co"),
        expected_section="control_alucinaciones",
        is_out_of_scope=True,
    ),
    BenchmarkQuestion(
        id=22,
        category="Control Anti-Alucinación (Fuera de Alcance)",
        question=(
            "¿Cuáles son las tarifas del metro subterráneo de Bogotá operado por EMCALI "
            "y qué vuelos internacionales ofrece?"
        ),
        expected_keywords=("No cuento con esa información", "base de conocimiento", "EMCALI"),
        expected_section="control_alucinaciones",
        is_out_of_scope=True,
    ),
)


def evaluate_reply(item: BenchmarkQuestion, answer_text: str) -> QuestionEvaluation:
    """Evalúa si una respuesta contiene las palabras clave esperadas y cita fuentes oficiales."""
    lowered = answer_text.lower()
    matched = tuple(kw for kw in item.expected_keywords if kw.lower() in lowered)
    recall = len(matched) / len(item.expected_keywords) if item.expected_keywords else 1.0
    has_citation = "https://www.emcali.com.co" in answer_text or "http" in answer_text

    if item.is_out_of_scope:
        refusal_signals = (
            "no cuento con esa información",
            "no tengo acceso",
            "informativo",
            "no es posible consultar",
            "base de conocimiento",
        )
        passed = any(signal in lowered for signal in refusal_signals)
    else:
        passed = recall >= 0.5 and has_citation

    return QuestionEvaluation(
        item=item,
        answer=answer_text,
        matched_keywords=matched,
        keyword_recall=recall,
        has_source_citation=has_citation,
        passed=passed,
    )


def run_benchmark_suite(
    bundle: KnowledgeBaseBundle | None = None,
    *,
    questions: Sequence[BenchmarkQuestion] = BENCHMARK_QUESTIONS,
    settings: AssistantSettings | None = None,
    strategy_key: str = DEFAULT_STRATEGY_KEY,
    progress: Callable[[int, int, QuestionEvaluation], None] | None = None,
) -> list[QuestionEvaluation]:
    """Ejecuta la batería de preguntas contra el asistente Q&A y devuelve las evaluaciones."""
    active_bundle = bundle or consolidate_knowledge_base(include_news=False)
    results: list[QuestionEvaluation] = []
    total = len(questions)

    for idx, item in enumerate(questions, start=1):
        reply: AssistantReply = answer_question(
            item.question,
            active_bundle,
            settings=settings,
            strategy_key=strategy_key,
        )
        evaluation = evaluate_reply(item, reply.answer)
        results.append(evaluation)
        if progress is not None:
            progress(idx, total, evaluation)

    return results


def render_benchmark_markdown(
    evaluations: Sequence[QuestionEvaluation],
    *,
    model_name: str = "deepseek-flash",
    strategy_key: str = DEFAULT_STRATEGY_KEY,
    context_docs: int = 0,
    context_words: int = 0,
) -> str:
    """Formatea los resultados de la evaluación en un informe Markdown."""
    total = len(evaluations)
    passed_count = sum(1 for ev in evaluations if ev.passed)
    citation_count = sum(1 for ev in evaluations if ev.has_source_citation)
    avg_recall = sum(ev.keyword_recall for ev in evaluations) / total if total else 0.0

    lines = [
        "# Resultados de la Batería de Pruebas Q&A — EMCALI (Taller 1)",
        "",
        f"- **Modelo evaluado:** `{model_name}`",
        f"- **Estrategia de Prompt:** `{strategy_key}`",
        f"- **Contexto inyectado:** {context_docs} documentos ({context_words:,} palabras)".replace(
            ",", "."
        ),
        f"- **Total de preguntas evaluadas:** {total}",
        f"- **Preguntas aprobadas:** {passed_count}/{total} ({passed_count / total * 100:.1f}%)"
        if total
        else "- **Preguntas aprobadas:** 0/0",
        f"- **Respuestas con citación de URL oficial:** {citation_count}/{total}",
        f"- **Cobertura promedio de términos clave (Recall):** {avg_recall * 100:.1f}%",
        "",
        "## Resumen en Tabla",
        "",
        "| # | Categoría | Cobertura Clave | Cita URL | Estado |",
        "|---:|---|:---:|:---:|:---:|",
    ]

    for ev in evaluations:
        status = "✅ Aprobada" if ev.passed else "⚠️ Revisar"
        cite = "Sí" if ev.has_source_citation else "No"
        recall_pct = f"{ev.keyword_recall * 100:.0f}%"
        lines.append(f"| {ev.item.id} | {ev.item.category} | {recall_pct} | {cite} | {status} |")

    lines.extend(["", "## Detalle de Preguntas y Respuestas Generadas", ""])
    for ev in evaluations:
        status = "✅ Aprobada" if ev.passed else "⚠️ Revisar"
        terms = ", ".join(ev.matched_keywords) or "ninguno"
        lines.extend(
            [
                f"### Pregunta {ev.item.id}: {ev.item.question}",
                f"- **Categoría:** {ev.item.category}",
                f"- **Estado:** {status} (Términos detectados: {terms})",
                "",
                ev.answer.strip(),
                "",
                "---",
                "",
            ]
        )

    return "\n".join(lines)
