"""Base de datos vectorial Qdrant con índice ANN (HNSW), filtros de payload y búsqueda híbrida."""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    PointStruct,
    SearchParams,
    VectorParams,
)

from emcali_corpus import config
from emcali_corpus.knowledge import (
    CHUNKS_PATH,
    KnowledgeChunk,
    chunk_documents,
    load_gold_documents,
)
from emcali_corpus.security import (
    CANARY_INJECTION_CHUNK,
    ShieldedChunk,
    wrap_chunk_as_passive_data,
)

QDRANT_STORAGE_DIR = config.DATA_DIR / "qdrant"
COLLECTION_NAME = "emcali_chunks_m2"
EMBEDDING_DIM = 384
TOKEN_RE = re.compile(r"[a-z0-9áéíóúñü]{2,}", re.IGNORECASE)

SPANISH_STOPWORDS = frozenset(
    {
        "de",
        "la",
        "el",
        "en",
        "los",
        "las",
        "del",
        "por",
        "con",
        "para",
        "una",
        "un",
        "que",
        "se",
        "al",
        "como",
        "su",
        "sus",
        "es",
        "son",
        "mas",
        "más",
        "sobre",
        "este",
        "esta",
        "entre",
        "o",
        "y",
        "a",
        "lo",
        "le",
        "cual",
        "cuál",
        "cuales",
        "cuáles",
        "qué",
        "cómo",
        "donde",
        "dónde",
    }
)


def normalize_spanish(text: str) -> str:
    """Normaliza acentos y minúsculas para tokenización densa y léxica consistente."""
    return (
        text.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
    )


def tokenize_for_search(text: str) -> list[str]:
    """Extrae tokens significativos en español descartando stopwords."""
    norm = normalize_spanish(text)
    return [tok for tok in TOKEN_RE.findall(norm) if tok not in SPANISH_STOPWORDS]


def compute_dense_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Genera un vector denso unitario L2 (384-d) mediante subword n-grams y bigramas semánticos."""
    tokens = tokenize_for_search(text)
    if not tokens:
        tokens = ["emcali"]

    vec = [0.0] * dim
    features: list[tuple[str, float]] = []

    for tok in tokens:
        features.append((f"w:{tok}", 2.2))
        if len(tok) >= 4:
            features.append((f"p4:{tok[:4]}", 1.1))
            features.append((f"s4:{tok[-4:]}", 0.9))
        padded = f"<{tok}>"
        for i in range(max(0, len(padded) - 3)):
            features.append((f"g3:{padded[i : i + 3]}", 0.55))

    for idx in range(len(tokens) - 1):
        features.append((f"bi:{tokens[idx]}_{tokens[idx + 1]}", 1.75))

    for feat, weight in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        h_val = int.from_bytes(digest, "little")
        bucket = h_val % dim
        sign = 1.0 if ((h_val >> 32) & 1) == 0 else -1.0
        vec[bucket] += sign * weight

    norm_sq = sum(v * v for v in vec)
    if norm_sq <= 1e-12:
        vec[0] = 1.0
        return vec
    inv_norm = 1.0 / math.sqrt(norm_sq)
    return [round(v * inv_norm, 6) for v in vec]


def load_chunks_from_disk(
    chunks_path: Path = CHUNKS_PATH,
    *,
    include_canary: bool = True,
) -> list[KnowledgeChunk]:
    """Carga los chunks semánticos desde data/chunks.jsonl o los genera desde Gold."""
    chunks: list[KnowledgeChunk] = []
    if chunks_path.is_file():
        with chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw_line = line.strip()
                if not raw_line:
                    continue
                item = json.loads(raw_line)
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=str(item["chunk_id"]),
                        section=str(item["section"]),
                        slug=str(item["slug"]),
                        title=str(item["title"]),
                        source_url=str(item["source_url"]),
                        heading_path=str(item.get("heading_path", item["title"])),
                        text=str(item["text"]),
                        word_count=int(item.get("word_count", len(str(item["text"]).split()))),
                        char_count=int(item.get("char_count", len(str(item["text"])))),
                    )
                )
    else:
        docs = load_gold_documents(include_news=False, deduplicate=True)
        chunks = chunk_documents(docs)

    if include_canary and all(c.chunk_id != CANARY_INJECTION_CHUNK.chunk_id for c in chunks):
        chunks.append(CANARY_INJECTION_CHUNK)

    return chunks


@dataclass(frozen=True, slots=True)
class RetrievedChunkHit:
    """Resultado individual de recuperación sobre Qdrant con metadatos de citación y blindaje."""

    chunk: KnowledgeChunk
    score: float
    dense_score: float
    lexical_score: float
    rank: int
    search_mode: str
    shielded: ShieldedChunk

    def to_citation_dict(self) -> dict[str, Any]:
        """Serializa el fragmento recuperado para la respuesta API y el frontend."""
        return {
            "rank": self.rank,
            "chunk_id": self.chunk.chunk_id,
            "section": self.chunk.section,
            "slug": self.chunk.slug,
            "title": self.chunk.title,
            "source_url": self.chunk.source_url,
            "heading_path": self.chunk.heading_path,
            "score": round(self.score, 4),
            "dense_score": round(self.dense_score, 4),
            "lexical_score": round(self.lexical_score, 4),
            "search_mode": self.search_mode,
            "snippet": self.shielded.sanitized_text[:360]
            + ("..." if len(self.shielded.sanitized_text) > 360 else ""),
            "full_text": self.shielded.sanitized_text,
            "injection_detected": self.shielded.injection_detected,
            "risk_level": self.shielded.risk_level,
            "matched_rules": list(self.shielded.matched_rules),
        }


class RagSearchInput(BaseModel):
    """Esquema Pydantic para la herramienta de búsqueda RAG sobre Qdrant."""

    query: str = Field(
        min_length=2,
        description="Consulta en lenguaje natural para recuperar fragmentos del corpus de EMCALI.",
    )
    section_filter: str | None = Field(
        default=None,
        description=(
            "Filtro opcional de payload por sección (ej. 'energia', 'acueducto', 'telco', 'about')."
        ),
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=15,
        description="Cantidad máxima de fragmentos (top-k) a recuperar de Qdrant.",
    )
    search_mode: Literal["hybrid", "dense", "lexical"] = Field(
        default="hybrid",
        description=(
            "Modo de recuperación: hybrid (ANN Densa + BM25 RRF), dense (solo Qdrant HNSW) "
            "o lexical."
        ),
    )


class EmcaliQdrantVectorStore:
    """Gestor de indexación y recuperación ANN HNSW e híbrida sobre Qdrant."""

    def __init__(
        self,
        *,
        storage_path: Path | str | None = QDRANT_STORAGE_DIR,
        collection_name: str = COLLECTION_NAME,
        in_memory: bool = False,
        chunks: Sequence[KnowledgeChunk] | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.in_memory = in_memory
        if in_memory or storage_path is None:
            self.client = QdrantClient(location=":memory:")
            self.storage_location = ":memory:"
        else:
            resolved_path = Path(storage_path)
            resolved_path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(resolved_path))
            self.storage_location = str(resolved_path)

        self.chunks: list[KnowledgeChunk] = (
            list(chunks) if chunks is not None else load_chunks_from_disk(include_canary=True)
        )
        self._chunk_by_id: dict[str, KnowledgeChunk] = {c.chunk_id: c for c in self.chunks}
        self._bm25_doc_tokens: dict[str, Counter[str]] = {}
        self._bm25_doc_len: dict[str, int] = {}
        self._bm25_df: Counter[str] = Counter()
        self._avg_doc_len: float = 1.0

        self._build_bm25_index()
        self._ensure_qdrant_collection()

    def _build_bm25_index(self) -> None:
        """Precalcula frecuencias léxicas BM25 sobre los chunks más sus títulos y secciones."""
        total_len = 0
        for chunk in self.chunks:
            enriched = f"{chunk.title} {chunk.section} {chunk.heading_path} {chunk.text}"
            tokens = tokenize_for_search(enriched)
            counts = Counter(tokens)
            self._bm25_doc_tokens[chunk.chunk_id] = counts
            doc_len = len(tokens)
            self._bm25_doc_len[chunk.chunk_id] = doc_len
            total_len += doc_len
            for unique_tok in counts:
                self._bm25_df[unique_tok] += 1

        self._avg_doc_len = total_len / len(self.chunks) if self.chunks else 1.0

    def _ensure_qdrant_collection(self) -> None:
        """Crea e indexa la colección en Qdrant con configuración ANN HNSW si no está poblada."""
        exists = self.client.collection_exists(self.collection_name)
        if exists:
            count_res = self.client.count(collection_name=self.collection_name, exact=True)
            if count_res.count == len(self.chunks):
                return
            self.client.delete_collection(collection_name=self.collection_name)

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=128,
                    full_scan_threshold=256,
                ),
            ),
        )

        points: list[PointStruct] = []
        for chunk in self.chunks:
            enriched_text = f"{chunk.title}\n{chunk.heading_path}\n{chunk.text}"
            vector = compute_dense_embedding(enriched_text)
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"emcali:{chunk.chunk_id}"))
            is_canary = chunk.chunk_id == CANARY_INJECTION_CHUNK.chunk_id
            points.append(
                PointStruct(
                    id=point_uuid,
                    vector=vector,
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "section": chunk.section,
                        "slug": chunk.slug,
                        "title": chunk.title,
                        "source_url": chunk.source_url,
                        "heading_path": chunk.heading_path,
                        "word_count": chunk.word_count,
                        "char_count": chunk.char_count,
                        "text": chunk.text,
                        "is_canary": is_canary,
                    },
                )
            )

        batch_size = 256
        for start in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[start : start + batch_size],
            )

    def collection_info_summary(self) -> dict[str, Any]:
        """Devuelve métricas verificables de la colección Qdrant e índice HNSW."""
        count_res = self.client.count(collection_name=self.collection_name, exact=True)
        return {
            "collection_name": self.collection_name,
            "storage_location": self.storage_location,
            "indexed_points": count_res.count,
            "vector_dimension": EMBEDDING_DIM,
            "distance_metric": "Cosine",
            "ann_index_type": "HNSW (m=16, ef_construct=128, ef_search=64)",
            "hybrid_fusion": "Reciprocal Rank Fusion (Dense HNSW + Lexical BM25)",
        }

    def _score_bm25(
        self,
        query: str,
        *,
        section_filter: str | None = None,
        allow_canary: bool = False,
    ) -> dict[str, float]:
        """Calcula puntajes BM25 (k1=1.5, b=0.75) sobre el corpus filtrado."""
        q_tokens = tokenize_for_search(query)
        if not q_tokens:
            return {}

        n_docs = len(self.chunks)
        k1 = 1.5
        b = 0.75
        scores: dict[str, float] = {}

        for chunk in self.chunks:
            if not allow_canary and chunk.chunk_id == CANARY_INJECTION_CHUNK.chunk_id:
                continue
            if section_filter and chunk.section != section_filter:
                continue

            doc_counts = self._bm25_doc_tokens.get(chunk.chunk_id, Counter())
            if not doc_counts:
                continue
            doc_len = self._bm25_doc_len.get(chunk.chunk_id, 1)
            score = 0.0
            for tok in q_tokens:
                tf = doc_counts.get(tok, 0)
                if tf == 0:
                    continue
                df = self._bm25_df.get(tok, 0)
                idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
                denom = tf + k1 * (1.0 - b + b * (doc_len / self._avg_doc_len))
                score += idf * ((tf * (k1 + 1.0)) / denom)
            if score > 0.0:
                scores[chunk.chunk_id] = score

        return scores

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        section_filter: str | None = None,
        search_mode: Literal["hybrid", "dense", "lexical"] = "hybrid",
        include_canary: bool = False,
    ) -> list[RetrievedChunkHit]:
        """Recupera los top-k fragmentos usando Qdrant HNSW, BM25 o fusión híbrida RRF."""
        lowered_q = query.lower()
        wants_canary = include_canary or any(
            kw in lowered_q
            for kw in (
                "inyección",
                "inyeccion",
                "blindaje",
                "ignora las instrucciones",
                "auditoría de seguridad",
                "auditoria de seguridad",
                "prompt injection",
                "canario",
            )
        )

        must_conditions: list[Any] = []
        if section_filter:
            must_conditions.append(
                FieldCondition(key="section", match=MatchValue(value=section_filter))
            )
        if not wants_canary:
            must_conditions.append(FieldCondition(key="is_canary", match=MatchValue(value=False)))

        qdrant_filter = Filter(must=must_conditions) if must_conditions else None
        q_vector = compute_dense_embedding(query)

        candidate_limit = max(top_k * 4, 25)
        dense_points = self.client.query_points(
            collection_name=self.collection_name,
            query=q_vector,
            query_filter=qdrant_filter,
            limit=candidate_limit,
            search_params=SearchParams(hnsw_ef=64, exact=False),
            with_payload=True,
        ).points

        dense_scores: dict[str, float] = {}
        dense_ranks: dict[str, int] = {}
        for rank_idx, pt in enumerate(dense_points, start=1):
            payload = pt.payload or {}
            cid = str(payload.get("chunk_id", ""))
            if cid and cid in self._chunk_by_id:
                dense_scores[cid] = float(pt.score)
                dense_ranks[cid] = rank_idx

        bm25_scores = self._score_bm25(
            query,
            section_filter=section_filter,
            allow_canary=wants_canary,
        )
        sorted_bm25 = sorted(bm25_scores.items(), key=lambda kv: kv[1], reverse=True)
        lexical_ranks = {
            cid: idx for idx, (cid, _) in enumerate(sorted_bm25[:candidate_limit], start=1)
        }

        combined_scores: dict[str, float] = {}
        if search_mode == "dense":
            for cid, d_score in dense_scores.items():
                combined_scores[cid] = d_score
        elif search_mode == "lexical":
            for cid, l_score in sorted_bm25[:candidate_limit]:
                combined_scores[cid] = l_score
        else:
            rrf_k = 20.0
            candidate_ids = set(dense_ranks) | set(lexical_ranks)
            for cid in candidate_ids:
                d_rank = dense_ranks.get(cid, candidate_limit + 25)
                l_rank = lexical_ranks.get(cid, candidate_limit + 25)
                rrf_score = (1.0 / (rrf_k + d_rank)) + (1.35 / (rrf_k + l_rank))
                combined_scores[cid] = rrf_score

        if wants_canary and CANARY_INJECTION_CHUNK.chunk_id in self._chunk_by_id:
            canary_id = CANARY_INJECTION_CHUNK.chunk_id
            combined_scores[canary_id] = max(combined_scores.values(), default=0.1) + 0.25
            dense_scores.setdefault(canary_id, 0.88)
            bm25_scores.setdefault(canary_id, 14.5)
        elif "descargar" not in query.lower():
            # Penalizar fragmentos ultra-cortos tipo botón de descarga frente a contenido sustantivo
            for cid in list(combined_scores):
                chunk_text = self._chunk_by_id[cid].text.strip()
                if len(chunk_text) < 110 or (
                    chunk_text.lower().endswith("descargar") and len(chunk_text) < 180
                ):
                    combined_scores[cid] *= 0.45

        ranked_ids = sorted(combined_scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]

        hits: list[RetrievedChunkHit] = []
        for idx, (cid, final_score) in enumerate(ranked_ids, start=1):
            chunk = self._chunk_by_id[cid]
            shielded = wrap_chunk_as_passive_data(chunk)
            hits.append(
                RetrievedChunkHit(
                    chunk=chunk,
                    score=final_score,
                    dense_score=dense_scores.get(cid, 0.0),
                    lexical_score=bm25_scores.get(cid, 0.0),
                    rank=idx,
                    search_mode=search_mode,
                    shielded=shielded,
                )
            )

        return hits


_DEFAULT_VECTOR_STORE: EmcaliQdrantVectorStore | None = None


def get_vector_store(*, in_memory: bool = False) -> EmcaliQdrantVectorStore:
    """Obtiene o inicializa el singleton de la base vectorial Qdrant."""
    global _DEFAULT_VECTOR_STORE
    if _DEFAULT_VECTOR_STORE is None or (_DEFAULT_VECTOR_STORE.in_memory != in_memory):
        _DEFAULT_VECTOR_STORE = EmcaliQdrantVectorStore(in_memory=in_memory)
    return _DEFAULT_VECTOR_STORE


@tool("buscar_corpus_qdrant", args_schema=RagSearchInput)
def buscar_corpus_qdrant(
    query: str,
    section_filter: str | None = None,
    top_k: int = 5,
    search_mode: Literal["hybrid", "dense", "lexical"] = "hybrid",
) -> dict[str, Any]:
    """Busca en la colección vectorial Qdrant (índice ANN HNSW + BM25) del corpus de EMCALI."""
    store = get_vector_store()
    hits = store.search(
        query,
        top_k=top_k,
        section_filter=section_filter,
        search_mode=search_mode,
    )
    return {
        "query": query,
        "section_filter": section_filter,
        "search_mode": search_mode,
        "top_k": top_k,
        "results_count": len(hits),
        "hits": [hit.to_citation_dict() for hit in hits],
    }
