"""Proyección UMAP 2D del corpus EMCALI, consultas de benchmark y tickets PQRS/Fallas."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import silhouette_score
from umap import UMAP

from emcali_corpus import config
from emcali_corpus.ops_db import EmcaliOpsDatabase, get_ops_db
from emcali_corpus.retrieval_eval import LABELED_RETRIEVAL_QUERIES
from emcali_corpus.vector_store import compute_dense_embedding, load_chunks_from_disk

UMAP_CACHE_PATH = config.DATA_DIR / "ops" / "umap_projection_cache.json"

CORE_SECTIONS = (
    "energia",
    "acueducto",
    "telco",
    "atencion-y-servicio-a-la-ciudadania",
    "sostenibilidad",
    "transparencia",
    "proteccion-de-datos-personales",
    "noticias",
    "about",
)


def _select_stratified_chunks(max_chunks: int = 220) -> list[dict[str, Any]]:
    """Selecciona una muestra estratificada de chunks del corpus y noticias para UMAP."""
    chunks = load_chunks_from_disk(include_canary=False)
    by_section: dict[str, list[Any]] = {}
    for ch in chunks:
        sec = ch.section if ch.section in CORE_SECTIONS else "otros"
        by_section.setdefault(sec, []).append(ch)

    per_sec = max(12, max_chunks // max(1, len(by_section)))
    selected: list[dict[str, Any]] = []
    for sec, items in sorted(by_section.items()):
        step = max(1, len(items) // per_sec)
        for ch in items[::step][:per_sec]:
            selected.append(
                {
                    "id": ch.chunk_id,
                    "kind": "corpus_chunk",
                    "section": sec,
                    "label": ch.title[:90],
                    "snippet": ch.text[:180].replace("\n", " "),
                    "text": f"{ch.title} {ch.heading_path} {ch.text[:600]}",
                }
            )
    return selected[:max_chunks]


def compute_umap_diagnostics(
    *,
    ops_db: EmcaliOpsDatabase | None = None,
    max_chunks: int = 220,
    cache_path: Path | None = UMAP_CACHE_PATH,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Ajusta UMAP 2D sobre embeddings del corpus y proyecta consultas + tickets PQRS/fallas."""
    if not force_refresh and cache_path is not None and cache_path.is_file():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    db = ops_db or get_ops_db()
    corpus_items = _select_stratified_chunks(max_chunks=max_chunks)

    # Añadir noticias scrapeadas si no están ya en chunks
    news_rows = db.list_news(limit=30)
    for n in news_rows:
        corpus_items.append(
            {
                "id": str(n["noticia_id"]),
                "kind": "news_article",
                "section": "noticias",
                "label": str(n["titulo"])[:90],
                "snippet": str(n["resumen"])[:180],
                "text": f"{n['titulo']} {n['resumen']}",
            }
        )

    if len(corpus_items) < 10:
        return {
            "method": "UMAP",
            "points": [],
            "metrics": {"total_points": 0, "silhouette_score": 0.0},
            "section_counts": {},
        }

    corpus_vecs = np.array(
        [compute_dense_embedding(item["text"]) for item in corpus_items],
        dtype=np.float32,
    )

    n_neighbors = min(12, max(4, len(corpus_items) - 2))
    reducer = UMAP(
        n_components=2,
        n_neighbors=n_neighbors,
        min_dist=0.15,
        metric="cosine",
        random_state=42,
    )
    corpus_coords = np.asarray(reducer.fit_transform(corpus_vecs), dtype=np.float64)

    # Silhouette score sobre secciones con al menos 2 muestras
    sec_labels = [item["section"] for item in corpus_items]
    sec_counter = Counter(sec_labels)
    valid_mask = [sec_counter[s] >= 2 for s in sec_labels]
    unique_valid = {s for s, ok in zip(sec_labels, valid_mask, strict=True) if ok}
    sil_score = 0.0
    if len(unique_valid) >= 2 and sum(valid_mask) > len(unique_valid):
        sil_score = float(
            silhouette_score(
                corpus_coords[valid_mask],
                [s for s, ok in zip(sec_labels, valid_mask, strict=True) if ok],
            )
        )

    points: list[dict[str, Any]] = []
    for item, (x, y) in zip(corpus_items, corpus_coords, strict=True):
        points.append(
            {
                "id": item["id"],
                "kind": item["kind"],
                "section": item["section"],
                "label": item["label"],
                "snippet": item["snippet"],
                "x": round(float(x), 4),
                "y": round(float(y), 4),
            }
        )

    # Proyectar consultas de benchmark + PQRS + fallas sobre la misma variedad UMAP (.transform)
    overlay_items: list[dict[str, Any]] = []
    for idx, bq in enumerate(LABELED_RETRIEVAL_QUERIES, start=1):
        overlay_items.append(
            {
                "id": f"BENCH-Q{idx:02d}",
                "kind": "benchmark_query",
                "section": bq.expected_section or "consulta",
                "label": bq.query[:90],
                "snippet": f"Sección esperada: {bq.expected_section}",
                "text": bq.query,
            }
        )
    for pq in db.list_pqrs(limit=20):
        overlay_items.append(
            {
                "id": str(pq["radicado_id"]),
                "kind": "pqrs_ticket",
                "section": str(pq["servicio"]),
                "label": f"[{pq['tipo']}] {pq['barrio']}: {pq['descripcion'][:60]}",
                "snippet": str(pq["descripcion"])[:160],
                "text": f"{pq['servicio']} {pq['barrio']} {pq['descripcion']}",
            }
        )
    for fr in db.list_failure_reports(limit=20):
        overlay_items.append(
            {
                "id": str(fr["reporte_id"]),
                "kind": "failure_report",
                "section": str(fr["servicio"]),
                "label": f"[Falla] {fr['barrio']} ({fr['servicio']})",
                "snippet": str(fr["descripcion"])[:160],
                "text": f"falla {fr['servicio']} {fr['barrio']} {fr['descripcion']}",
            }
        )

    if overlay_items:
        ov_vecs = np.array(
            [compute_dense_embedding(it["text"]) for it in overlay_items],
            dtype=np.float32,
        )
        ov_coords = np.asarray(reducer.transform(ov_vecs), dtype=np.float64)
        for item, (x, y) in zip(overlay_items, ov_coords, strict=True):
            points.append(
                {
                    "id": item["id"],
                    "kind": item["kind"],
                    "section": item["section"],
                    "label": item["label"],
                    "snippet": item["snippet"],
                    "x": round(float(x), 4),
                    "y": round(float(y), 4),
                }
            )

    payload = {
        "method": "UMAP (cosine, n_neighbors=12, min_dist=0.15)",
        "metrics": {
            "total_points": len(points),
            "corpus_and_news_points": len(corpus_items),
            "overlay_queries_and_tickets": len(overlay_items),
            "silhouette_score": round(sil_score, 4),
            "clusters_detected": len(sec_counter),
        },
        "section_counts": dict(sec_counter.most_common()),
        "points": points,
    }

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return payload
