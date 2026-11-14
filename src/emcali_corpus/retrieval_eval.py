"""Evaluación cuantitativa del Retrieval en Qdrant (Recall@10, MRR@10 y nDCG@10 sobre 25
consultas)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from emcali_corpus import config
from emcali_corpus.vector_store import EmcaliQdrantVectorStore, get_vector_store

RETRIEVAL_REPORT_PATH = config.PROJECT_ROOT / "docs" / "evaluacion_retrieval_m2.md"


@dataclass(frozen=True, slots=True)
class LabeledRetrievalQuery:
    """Consulta etiquetada con su sección, documento (slug) y términos de relevancia."""

    id: int
    category: str
    query: str
    expected_section: str
    expected_slug_substring: str
    expected_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QueryRetrievalMetrics:
    """Métricas de recuperación calculadas para una consulta individual."""

    item: LabeledRetrievalQuery
    search_mode: str
    first_relevant_rank: int | None
    recall_at_5: float
    recall_at_10: float
    mrr_at_10: float
    ndcg_at_10: float
    top_hit_chunk_id: str
    top_hit_url: str


LABELED_RETRIEVAL_QUERIES: tuple[LabeledRetrievalQuery, ...] = (
    LabeledRetrievalQuery(
        id=1,
        category="Gobierno Corporativo",
        query=(
            "¿Quién es el Gerente General de EMCALI Roger Mina y quiénes lideran Energía, "
            "Acueducto y Telecomunicaciones?"
        ),
        expected_section="about",
        expected_slug_substring="about",
        expected_terms=("Roger Mina", "Mario Germán Ocaña"),
    ),
    LabeledRetrievalQuery(
        id=2,
        category="Identidad y Domicilio",
        query="¿Cuál es el NIT de EMCALI 890.399.003-4 y la dirección del CAM Torre EMCALI?",
        expected_section="proteccion-de-datos-personales",
        expected_slug_substring="proteccion-de-datos-personales",
        expected_terms=("890.399.003-4", "CAM"),
    ),
    LabeledRetrievalQuery(
        id=3,
        category="Transformación e Innovación",
        query=(
            "¿Qué iniciativas impulsa el Centro Digital de EMCALI con fibra óptica y "
            "paneles solares en La Reforma?"
        ),
        expected_section="about",
        expected_slug_substring="about",
        expected_terms=("Centro Digital", "La Reforma"),
    ),
    LabeledRetrievalQuery(
        id=4,
        category="Servicio de Energía",
        query=(
            "¿Cuántos clientes atiende EMCALI en energía eléctrica (790.000) y cuántos "
            "kilómetros de red opera?"
        ),
        expected_section="energia",
        expected_slug_substring="energia",
        expected_terms=("790.000", "19.000"),
    ),
    LabeledRetrievalQuery(
        id=5,
        category="Trámites de Energía",
        query=(
            "¿Qué trámites de energía ofrece EMCALI para reportar fallas, consultar "
            "facturas y PQRS?"
        ),
        expected_section="energia",
        expected_slug_substring="energia",
        expected_terms=("factura", "falla"),
    ),
    LabeledRetrievalQuery(
        id=6,
        category="Tarifas de Energía",
        query="¿Dónde publica EMCALI las tarifas vigentes del servicio de energía eléctrica?",
        expected_section="energia",
        expected_slug_substring="tarifas-de-energia",
        expected_terms=("tarifas", "energía"),
    ),
    LabeledRetrievalQuery(
        id=7,
        category="Acueducto y Agua Potable",
        query=(
            "¿Cuál es el compromiso de EMCALI en suministro de agua potable, plantas de "
            "tratamiento y alcantarillado?"
        ),
        expected_section="acueducto",
        expected_slug_substring="acueducto",
        expected_terms=("agua potable", "aguas residuales"),
    ),
    LabeledRetrievalQuery(
        id=8,
        category="Calidad del Agua y Vertimientos",
        query=(
            "¿Qué informes técnicos de calidad del agua potable y vertimientos publica "
            "Acueducto y Alcantarillado?"
        ),
        expected_section="acueducto",
        expected_slug_substring="acueducto",
        expected_terms=("calidad", "agua"),
    ),
    LabeledRetrievalQuery(
        id=9,
        category="Tarifas de Acueducto",
        query="¿Cómo consultar las tarifas de acueducto y alcantarillado vigentes en EMCALI?",
        expected_section="acueducto",
        expected_slug_substring="tarifas-de-acueducto",
        expected_terms=("tarifas", "acueducto"),
    ),
    LabeledRetrievalQuery(
        id=10,
        category="Telecomunicaciones Fibra Óptica",
        query=(
            "¿Qué ventajas ofrecen los planes de internet por fibra óptica de EMCALI "
            "Telecomunicaciones con soporte 24/7?"
        ),
        expected_section="telco",
        expected_slug_substring="telco",
        expected_terms=("fibra óptica", "24/7"),
    ),
    LabeledRetrievalQuery(
        id=11,
        category="Cobertura y Contratos Telco",
        query=(
            "¿Qué porcentaje de cobertura de fibra óptica (92%) tiene EMCALI en Cali y "
            "dónde está el contrato único?"
        ),
        expected_section="telco",
        expected_slug_substring="telco",
        expected_terms=("92%", "Contrato"),
    ),
    LabeledRetrievalQuery(
        id=12,
        category="Operación Cali sin Enredos",
        query=(
            "¿En qué consiste la Operación Cali sin enredos de desmonte de 57 mil metros "
            "de cables en desuso?"
        ),
        expected_section="telco",
        expected_slug_substring="telco",
        expected_terms=("57 mil", "cable"),
    ),
    LabeledRetrievalQuery(
        id=13,
        category="Canales y Líneas de Atención",
        query=(
            "¿Cuáles son las líneas de atención telefónica 177 y 602 5240177 y los Centros "
            "de Atención CAP de EMCALI?"
        ),
        expected_section="proteccion-de-datos-personales",
        expected_slug_substring="proteccion-de-datos-personales",
        expected_terms=("177", "5240177"),
    ),
    LabeledRetrievalQuery(
        id=14,
        category="Medios de Pago Electrónicos",
        query=(
            "¿Qué métodos y canales de pago electrónicos PSE ofrece EMCALI para pagar la factura?"
        ),
        expected_section="atencion-y-servicio-a-la-ciudadania",
        expected_slug_substring="metodos-de-pago",
        expected_terms=("PSE", "pago"),
    ),
    LabeledRetrievalQuery(
        id=15,
        category="Factura Digital Formato ZIP",
        query=(
            "¿En qué formato ZIP llega la Factura Digital por correo electrónico y cuál es "
            "la diferencia ante la DIAN?"
        ),
        expected_section="terminos-condiciones-uso-factura-digital",
        expected_slug_substring="terminos-condiciones-uso-factura-digital",
        expected_terms=("ZIP", "DIAN"),
    ),
    LabeledRetrievalQuery(
        id=16,
        category="Rechazo de Correo Factura Digital",
        query=(
            "¿Qué pasa si el buzón de correo rechaza la Factura Digital y cómo regresar a "
            "la impresión física?"
        ),
        expected_section="terminos-condiciones-uso-factura-digital",
        expected_slug_substring="terminos-condiciones-uso-factura-digital",
        expected_terms=("impresión física", "Centros de Atención"),
    ),
    LabeledRetrievalQuery(
        id=17,
        category="Plazos Ley 1581 Protección de Datos",
        query=(
            "¿Cuántos días hábiles máximo (10 y 15 días) toma responder consultas y "
            "reclamos según la Ley 1581 de 2012?"
        ),
        expected_section="proteccion-de-datos-personales",
        expected_slug_substring="proteccion-de-datos-personales",
        expected_terms=("10", "15", "días hábiles"),
    ),
    LabeledRetrievalQuery(
        id=18,
        category="Derechos del Titular de Datos",
        query=(
            "¿Cuáles son los derechos del titular para conocer, actualizar y rectificar "
            "sus datos ante la Superintendencia?"
        ),
        expected_section="proteccion-de-datos-personales",
        expected_slug_substring="proteccion-de-datos-personales",
        expected_terms=("conocer", "actualizar", "rectificar"),
    ),
    LabeledRetrievalQuery(
        id=19,
        category="Sostenibilidad y Gestión Ambiental",
        query=(
            "¿Qué leyes guían la sostenibilidad en EMCALI (Ley 1757 y Ley 1712) y el rol "
            "de la Subgerencia Ambiental?"
        ),
        expected_section="sostenibilidad",
        expected_slug_substring="sostenibilidad",
        expected_terms=("Ley 1757", "Ley 1712"),
    ),
    LabeledRetrievalQuery(
        id=20,
        category="Transparencia Misión y Visión",
        query=(
            "¿Cuál es la misión y visión institucional publicada en el portal de "
            "Transparencia de EMCALI?"
        ),
        expected_section="transparencia",
        expected_slug_substring="mision-y-vision",
        expected_terms=("misión", "visión"),
    ),
    LabeledRetrievalQuery(
        id=21,
        category="Normatividad y Transparencia",
        query=(
            "¿Qué leyes, decretos y actos normativos se publican en la sección de "
            "Normatividad de Transparencia?"
        ),
        expected_section="transparencia",
        expected_slug_substring="normatividad",
        expected_terms=("normatividad", "transparencia"),
    ),
    LabeledRetrievalQuery(
        id=22,
        category="Indicadores PQR Telecomunicaciones",
        query=(
            "¿Dónde se reportan los indicadores de peticiones, quejas y recursos (PQR) del "
            "servicio de telecomunicaciones?"
        ),
        expected_section="telco",
        expected_slug_substring="indicadores-pqr",
        expected_terms=("PQR", "indicadores"),
    ),
    LabeledRetrievalQuery(
        id=23,
        category="Accesibilidad y Usabilidad Web",
        query=(
            "¿Qué establece la declaración de conformidad de accesibilidad y usabilidad "
            "del portal web de EMCALI?"
        ),
        expected_section="declaracion-de-conformidad-de-accesibilidad-y-usabilidad",
        expected_slug_substring="declaracion-de-conformidad",
        expected_terms=("accesibilidad", "usabilidad"),
    ),
    LabeledRetrievalQuery(
        id=24,
        category="Notificaciones de Actos Administrativos",
        query=(
            "¿Dónde publica EMCALI las notificaciones por aviso y actos administrativos "
            "para los ciudadanos?"
        ),
        expected_section="notificaciones-actos-administrativos",
        expected_slug_substring="notificaciones-actos-administrativos",
        expected_terms=("notificaciones", "administrativos"),
    ),
    LabeledRetrievalQuery(
        id=25,
        category="Atención y Servicio a la Ciudadanía",
        query=(
            "¿Qué servicios de orientación, trámites y canales ofrece la página de "
            "Atención y Servicio a la Ciudadanía?"
        ),
        expected_section="atencion-y-servicio-a-la-ciudadania",
        expected_slug_substring="atencion-y-servicio-a-la-ciudadania",
        expected_terms=("ciudadanía", "atención"),
    ),
)


def _chunk_relevance_grade(
    item: LabeledRetrievalQuery, chunk_section: str, chunk_slug: str, chunk_text: str
) -> int:
    """Asigna grado de relevancia (0, 1 o 2) para cálculo riguroso de nDCG@10 y Recall@10."""
    lowered_text = chunk_text.lower()
    term_matches = sum(1 for t in item.expected_terms if t.lower() in lowered_text)
    slug_match = item.expected_slug_substring.lower() in chunk_slug.lower()
    section_match = item.expected_section.lower() == chunk_section.lower()

    if (section_match or slug_match) and term_matches >= 1:
        return 2
    if section_match or slug_match or term_matches >= len(item.expected_terms):
        return 1
    return 0


def evaluate_retrieval_mode(
    vector_store: EmcaliQdrantVectorStore | None = None,
    *,
    search_mode: Literal["hybrid", "dense", "lexical"] = "hybrid",
    queries: Sequence[LabeledRetrievalQuery] = LABELED_RETRIEVAL_QUERIES,
) -> dict[str, Any]:
    """Evalúa Recall@5, Recall@10, MRR@10 y nDCG@10 sobre las 25 consultas etiquetadas."""
    store = vector_store or get_vector_store()
    per_query: list[QueryRetrievalMetrics] = []

    for q_item in queries:
        hits = store.search(q_item.query, top_k=10, search_mode=search_mode)
        grades: list[int] = []
        first_rank: int | None = None

        for idx, hit in enumerate(hits, start=1):
            grade = _chunk_relevance_grade(
                q_item,
                hit.chunk.section,
                hit.chunk.slug,
                f"{hit.chunk.title} {hit.chunk.text}",
            )
            grades.append(grade)
            if grade > 0 and first_rank is None:
                first_rank = idx

        recall_5 = 1.0 if any(g > 0 for g in grades[:5]) else 0.0
        recall_10 = 1.0 if any(g > 0 for g in grades[:10]) else 0.0
        mrr_10 = (1.0 / first_rank) if first_rank is not None and first_rank <= 10 else 0.0

        dcg = 0.0
        for idx, g in enumerate(grades[:10], start=1):
            if g > 0:
                dcg += (2**g - 1.0) / math.log2(idx + 1.0)

        ideal_grades = sorted(grades[:10], reverse=True)
        if not any(g > 0 for g in ideal_grades):
            ideal_grades = [2]
        idcg = sum(
            (2**g - 1.0) / math.log2(idx + 1.0)
            for idx, g in enumerate(ideal_grades, start=1)
            if g > 0
        )
        ndcg_10 = (dcg / idcg) if idcg > 0 else 0.0

        top_cid = hits[0].chunk.chunk_id if hits else ""
        top_url = hits[0].chunk.source_url if hits else ""

        per_query.append(
            QueryRetrievalMetrics(
                item=q_item,
                search_mode=search_mode,
                first_relevant_rank=first_rank,
                recall_at_5=recall_5,
                recall_at_10=recall_10,
                mrr_at_10=round(mrr_10, 4),
                ndcg_at_10=round(ndcg_10, 4),
                top_hit_chunk_id=top_cid,
                top_hit_url=top_url,
            )
        )

    total = len(per_query) or 1
    avg_r5 = round(sum(m.recall_at_5 for m in per_query) / total, 4)
    avg_r10 = round(sum(m.recall_at_10 for m in per_query) / total, 4)
    avg_mrr10 = round(sum(m.mrr_at_10 for m in per_query) / total, 4)
    avg_ndcg10 = round(sum(m.ndcg_at_10 for m in per_query) / total, 4)

    return {
        "search_mode": search_mode,
        "queries_evaluated": len(per_query),
        "recall_at_5": avg_r5,
        "recall_at_10": avg_r10,
        "mrr_at_10": avg_mrr10,
        "ndcg_at_10": avg_ndcg10,
        "per_query": [
            {
                "id": m.item.id,
                "category": m.item.category,
                "query": m.item.query,
                "expected_section": m.item.expected_section,
                "first_relevant_rank": m.first_relevant_rank,
                "recall_at_5": m.recall_at_5,
                "recall_at_10": m.recall_at_10,
                "mrr_at_10": m.mrr_at_10,
                "ndcg_at_10": m.ndcg_at_10,
                "top_hit_chunk_id": m.top_hit_chunk_id,
                "top_hit_url": m.top_hit_url,
            }
            for m in per_query
        ],
    }


def run_full_retrieval_benchmark(
    vector_store: EmcaliQdrantVectorStore | None = None,
    *,
    output_path: Path | None = RETRIEVAL_REPORT_PATH,
) -> dict[str, Any]:
    """Compara los modos hybrid, dense y lexical en Qdrant y exporta el reporte Markdown."""
    store = vector_store or get_vector_store()
    hybrid_res = evaluate_retrieval_mode(store, search_mode="hybrid")
    dense_res = evaluate_retrieval_mode(store, search_mode="dense")
    lexical_res = evaluate_retrieval_mode(store, search_mode="lexical")

    summary = {
        "collection": store.collection_info_summary(),
        "modes": {
            "hybrid": hybrid_res,
            "dense": dense_res,
            "lexical": lexical_res,
        },
    }

    if output_path is not None:
        md_lines = [
            "# Evaluación Cuantitativa del Retrieval en Qdrant — Módulo 2 (EMCALI)",
            "",
            (
                f"- **Colección Qdrant:** `{store.collection_name}` (`{len(store.chunks)}` "
                "fragmentos indexados)"
            ),
            "- **Índice ANN:** `HNSW (m=16, ef_construct=128, distance=Cosine, dim=384)`",
            f"- **Total de consultas etiquetadas:** `{len(LABELED_RETRIEVAL_QUERIES)}`",
            "",
            "## 1. Comparativa por Estrategia de Búsqueda",
            "",
            "| Estrategia de Recuperación | Recall@5 | Recall@10 | MRR@10 | nDCG@10 |",
            "| :--- | :---: | :---: | :---: | :---: |",
            (
                "| **Híbrida (Qdrant ANN Densa + BM25 RRF)** | "
                f"**{hybrid_res['recall_at_5'] * 100:.1f}%** | "
                f"**{hybrid_res['recall_at_10'] * 100:.1f}%** | "
                f"**{hybrid_res['mrr_at_10']:.3f}** | **{hybrid_res['ndcg_at_10']:.3f}** |"
            ),
            (
                f"| Densa pura (Qdrant HNSW Cosine) | {dense_res['recall_at_5'] * 100:.1f}% | "
                f"{dense_res['recall_at_10'] * 100:.1f}% | {dense_res['mrr_at_10']:.3f} | "
                f"{dense_res['ndcg_at_10']:.3f} |"
            ),
            (
                f"| Léxica pura (BM25 k1=1.5, b=0.75) | {lexical_res['recall_at_5'] * 100:.1f}% "
                f"| {lexical_res['recall_at_10'] * 100:.1f}% | "
                f"{lexical_res['mrr_at_10']:.3f} | {lexical_res['ndcg_at_10']:.3f} |"
            ),
            "",
            "## 2. Detalle por Consulta Etiquetada (Modo Híbrido RRF)",
            "",
            (
                "| # | Categoría | Sección Esperada | Rango 1.er Hit | Recall@10 | nDCG@10 | Top "
                "Chunk Recuperado |"
            ),
            "|---:|---|---|:---:|:---:|:---:|---|",
        ]
        for row in hybrid_res["per_query"]:
            rank_str = str(row["first_relevant_rank"]) if row["first_relevant_rank"] else "No"
            md_lines.append(
                f"| {row['id']} | {row['category']} | `{row['expected_section']}` | "
                f"{rank_str} | {row['recall_at_10'] * 100:.0f}% | {row['ndcg_at_10']:.3f} | "
                f"`{row['top_hit_chunk_id']}` |"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8", newline="\n")

    return summary
