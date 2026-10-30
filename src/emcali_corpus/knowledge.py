"""Consolidación de la base de conocimiento semántico y segmentación (chunking)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from emcali_corpus import config, gold

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200
SITEMAP_TOTAL_URLS = 587
SITEMAP_IN_SCOPE_URLS = 570

KNOWLEDGE_BASE_PATH = config.DATA_DIR / "knowledge_base.md"
CHUNKS_PATH = config.DATA_DIR / "chunks.jsonl"

SECTION_LABELS: dict[str, str] = {
    "portada": "Portada e Inicio",
    "inicio": "Inicio Institucional",
    "about": "Quiénes Somos (Sobre Nosotros)",
    "energia": "Servicio de Energía",
    "acueducto": "Acueducto y Alcantarillado",
    "telco": "Telecomunicaciones (Telco)",
    "atencion-y-servicio-a-la-ciudadania": "Atención y Servicio a la Ciudadanía",
    "sostenibilidad": "Sostenibilidad y Gestión Ambiental",
    "transparencia": "Transparencia y Acceso a la Información Pública",
    "proteccion-de-datos-personales": "Protección de Datos Personales",
    "terminos-condiciones-uso-factura-digital": "Factura Digital (Términos y Condiciones)",
    "transformacion-emcali": "Transformación EMCALI",
    "superciudadano": "Superciudadano",
    "canal-digital": "Canal Digital",
    "indicadores-atencion-fisica": "Indicadores de Atención Física",
    "indicadores-pqr": "Indicadores PQR",
    "informacion-contractual": "Información Contractual",
    "informacion-sobre-decisiones-que-puede-afectar-al-publico": (
        "Decisiones que Afectan al Público"
    ),
    "notificaciones-actos-administrativos": "Notificaciones de Actos Administrativos",
    "declaracion-de-conformidad-de-accesibilidad-y-usabilidad": "Accesibilidad y Usabilidad",
    "tablas-de-retencion-documental": "Tablas de Retención Documental",
    "politicas-derechos-autor": "Políticas de Derechos de Autor",
    "mapa-sitio": "Mapa del Sitio",
    "noticias": "Noticias y Actualidad",
}


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Documento limpio de la capa gold cargado en memoria."""

    slug: str
    section: str
    title: str
    source_url: str
    description: str
    body: str
    word_count: int
    content_sha256: str
    gold_path: str

    def render_block(self) -> str:
        """Formatea el documento con metadatos explícitos para el prompt del LLM."""
        header = [
            f"## [{self.section.upper()}] {self.title}",
            f"- **Sección:** {SECTION_LABELS.get(self.section, self.section)} (`{self.section}`)",
            f"- **URL oficial:** {self.source_url}",
        ]
        if self.description:
            header.append(f"- **Resumen:** {self.description}")
        header.append("")
        header.append(self.body.strip())
        return "\n".join(header)


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """Fragmento semántico (chunk) extraído de un documento gold."""

    chunk_id: str
    section: str
    slug: str
    title: str
    source_url: str
    heading_path: str
    text: str
    word_count: int
    char_count: int

    def to_dict(self) -> dict[str, Any]:
        """Serializa el fragmento a un diccionario compatible con JSONL."""
        return {
            "chunk_id": self.chunk_id,
            "section": self.section,
            "slug": self.slug,
            "title": self.title,
            "source_url": self.source_url,
            "heading_path": self.heading_path,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeBaseBundle:
    """Conjunto consolidado de documentos listos para inyectar en el prompt."""

    documents: tuple[KnowledgeDocument, ...]
    consolidated_text: str
    sections: tuple[str, ...] = field(default_factory=tuple)

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def total_words(self) -> int:
        return sum(doc.word_count for doc in self.documents)

    @property
    def total_chars(self) -> int:
        return len(self.consolidated_text)

    @property
    def estimated_tokens(self) -> int:
        """Estimación de tokens en español (~1.33 tokens por palabra)."""
        return round(self.total_words * 1.33)


@dataclass(frozen=True, slots=True)
class PipelineFunnelMetrics:
    """Métricas por etapas del proceso de scraping y curaduría Medallion."""

    sitemap_urls: int
    urls_in_scope: int
    excluded_by_scope: int
    discarded_pages: int
    gold_total_docs: int
    browser_rendered_docs: int
    http_rendered_docs: int
    news_docs: int
    institutional_before_dedup: int
    duplicates_removed: int
    institutional_unique_docs: int
    total_words_all: int
    estimated_tokens_all: int
    institutional_words: int
    institutional_tokens: int
    sections_count: int


@dataclass(frozen=True, slots=True)
class MedallionDocumentView:
    """Vista comparativa Bronze -> Silver -> Gold de un documento del corpus."""

    section: str
    slug: str
    title: str
    source_url: str
    render_mode: str
    iframe_url: str
    bronze_source: str
    bronze_html: str
    silver_markdown: str
    gold_markdown_with_frontmatter: str
    gold_index_record: dict[str, Any]


def available_sections(
    *,
    include_news: bool = False,
    index_path: Path = config.INDEX_PATH,
) -> list[str]:
    """Devuelve la lista ordenada de secciones presentes en el índice gold."""
    records = gold.read_index(index_path)
    sections = {
        str(record.get("section", ""))
        for record in records
        if record.get("section") and (include_news or record.get("section") != "noticias")
    }
    return sorted(sections)


def load_gold_documents(
    *,
    gold_dir: Path = config.GOLD_DIR,
    index_path: Path = config.INDEX_PATH,
    include_news: bool = False,
    sections: Sequence[str] | None = None,
    curated_only: bool = False,
    deduplicate: bool = True,
) -> list[KnowledgeDocument]:
    """Carga y filtra los documentos limpios de la capa gold."""
    records = gold.read_index(index_path)
    if not records:
        records = gold.rebuild_index_from_gold(gold_dir)

    allowed_sections = set(sections) if sections else None
    curated_keys = {(seed.section, seed.slug) for seed in config.CURATED_SEEDS}
    seen_hashes: set[str] = set()
    documents: list[KnowledgeDocument] = []

    for record in records:
        section = str(record.get("section", ""))
        slug = str(record.get("slug", ""))
        if not include_news and section == "noticias":
            continue
        if allowed_sections is not None and section not in allowed_sections:
            continue
        if curated_only and (section, slug) not in curated_keys:
            continue

        md_path = gold_dir / section / f"{slug}.md"
        if not md_path.is_file():
            continue

        meta, body = gold.parse_front_matter(md_path.read_text(encoding="utf-8"))
        clean_body = body.strip()
        if not clean_body:
            continue

        sha256 = str(meta.get("content_sha256") or record.get("content_sha256") or "")
        if deduplicate and sha256:
            if sha256 in seen_hashes:
                continue
            seen_hashes.add(sha256)

        documents.append(
            KnowledgeDocument(
                slug=slug,
                section=section,
                title=str(meta.get("title") or record.get("title") or slug),
                source_url=str(meta.get("source_url") or record.get("source_url") or ""),
                description=str(meta.get("description") or record.get("description") or ""),
                body=clean_body,
                word_count=len(clean_body.split()),
                content_sha256=sha256,
                gold_path=f"data/gold/{section}/{slug}.md",
            )
        )

    return documents


def consolidate_knowledge_base(
    documents: Sequence[KnowledgeDocument] | None = None,
    *,
    gold_dir: Path = config.GOLD_DIR,
    index_path: Path = config.INDEX_PATH,
    include_news: bool = False,
    sections: Sequence[str] | None = None,
    curated_only: bool = False,
    deduplicate: bool = True,
) -> KnowledgeBaseBundle:
    """Consolida los documentos seleccionados en un único texto estructurado."""
    docs = (
        list(documents)
        if documents is not None
        else load_gold_documents(
            gold_dir=gold_dir,
            index_path=index_path,
            include_news=include_news,
            sections=sections,
            curated_only=curated_only,
            deduplicate=deduplicate,
        )
    )
    unique_sections = tuple(sorted({doc.section for doc in docs}))
    sections_label = ", ".join(unique_sections) if unique_sections else "ninguna"
    header = [
        "# BASE DE CONOCIMIENTO OFICIAL — EMCALI E.I.C.E. E.S.P.",
        "",
        f"- **Total de documentos consolidados:** {len(docs)}",
        f"- **Total de palabras:** {sum(doc.word_count for doc in docs)}",
        f"- **Secciones incluidas:** {sections_label}",
        "",
        "---",
        "",
    ]
    blocks = [doc.render_block() for doc in docs]
    consolidated_text = "\n".join(header) + "\n\n---\n\n".join(blocks) + "\n"
    return KnowledgeBaseBundle(
        documents=tuple(docs),
        consolidated_text=consolidated_text,
        sections=unique_sections,
    )


def chunk_documents(
    documents: Sequence[KnowledgeDocument],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[KnowledgeChunk]:
    """Segmenta los documentos Markdown en fragmentos semánticos coherentes."""
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "h1"),
            ("##", "h2"),
            ("###", "h3"),
        ],
        strip_headers=False,
    )
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[KnowledgeChunk] = []
    for doc in documents:
        md_splits = header_splitter.split_text(doc.body)
        sub_splits = char_splitter.split_documents(md_splits)
        for idx, split in enumerate(sub_splits, start=1):
            text = split.page_content.strip()
            if not text:
                continue
            headings = [
                str(split.metadata[key]) for key in ("h1", "h2", "h3") if split.metadata.get(key)
            ]
            heading_path = " > ".join(headings) if headings else doc.title
            chunk_id = f"{doc.section}/{doc.slug}#c{idx:02d}"
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    section=doc.section,
                    slug=doc.slug,
                    title=doc.title,
                    source_url=doc.source_url,
                    heading_path=heading_path,
                    text=text,
                    word_count=len(text.split()),
                    char_count=len(text),
                )
            )
    return chunks


def export_knowledge_artifacts(
    *,
    output_md: Path = KNOWLEDGE_BASE_PATH,
    output_chunks: Path = CHUNKS_PATH,
    include_news: bool = False,
    sections: Sequence[str] | None = None,
    curated_only: bool = False,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> tuple[KnowledgeBaseBundle, list[KnowledgeChunk]]:
    """Escribe el archivo de texto limpio consolidado y el archivo JSONL de chunks."""
    bundle = consolidate_knowledge_base(
        include_news=include_news,
        sections=sections,
        curated_only=curated_only,
    )
    chunks = chunk_documents(
        bundle.documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(bundle.consolidated_text, encoding="utf-8", newline="\n")

    output_chunks.parent.mkdir(parents=True, exist_ok=True)
    with output_chunks.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")

    return bundle, chunks


def compute_funnel_metrics(
    *,
    gold_dir: Path = config.GOLD_DIR,
    index_path: Path = config.INDEX_PATH,
) -> PipelineFunnelMetrics:
    """Calcula las métricas de embudo de las 5 etapas del pipeline Medallion."""
    records = gold.read_index(index_path)
    if not records:
        records = gold.rebuild_index_from_gold(gold_dir)

    gold_total = len(records)
    browser_docs = sum(1 for r in records if r.get("render") == "browser")
    http_docs = gold_total - browser_docs
    news_docs = sum(1 for r in records if r.get("section") == "noticias")
    inst_before_dedup = gold_total - news_docs

    inst_unique_docs = load_gold_documents(
        gold_dir=gold_dir,
        index_path=index_path,
        include_news=False,
        deduplicate=True,
    )
    inst_unique_count = len(inst_unique_docs)
    duplicates_removed = max(0, inst_before_dedup - inst_unique_count)

    total_words_all = sum(int(r.get("word_count", 0)) for r in records)
    inst_words = sum(doc.word_count for doc in inst_unique_docs)
    sections_count = len({str(r.get("section", "")) for r in records if r.get("section")})

    sitemap_urls = max(SITEMAP_TOTAL_URLS, gold_total)
    in_scope = max(SITEMAP_IN_SCOPE_URLS, gold_total)
    excluded = max(0, sitemap_urls - in_scope)
    discarded = max(0, in_scope - gold_total)

    return PipelineFunnelMetrics(
        sitemap_urls=sitemap_urls,
        urls_in_scope=in_scope,
        excluded_by_scope=excluded,
        discarded_pages=discarded,
        gold_total_docs=gold_total,
        browser_rendered_docs=browser_docs,
        http_rendered_docs=http_docs,
        news_docs=news_docs,
        institutional_before_dedup=inst_before_dedup,
        duplicates_removed=duplicates_removed,
        institutional_unique_docs=inst_unique_count,
        total_words_all=total_words_all,
        estimated_tokens_all=round(total_words_all * 1.33),
        institutional_words=inst_words,
        institutional_tokens=round(inst_words * 1.33),
        sections_count=sections_count,
    )


def load_medallion_document_view(
    section: str,
    slug: str,
    *,
    raw_dir: Path = config.RAW_DIR,
    processed_dir: Path = config.PROCESSED_DIR,
    gold_dir: Path = config.GOLD_DIR,
    index_path: Path = config.INDEX_PATH,
) -> MedallionDocumentView:
    """Construye la vista Bronze -> Silver -> Gold de un documento específico."""
    gold_path = gold_dir / section / f"{slug}.md"
    gold_raw_text = gold_path.read_text(encoding="utf-8") if gold_path.is_file() else ""
    meta, body = gold.parse_front_matter(gold_raw_text)

    silver_path = processed_dir / section / f"{slug}.md"
    silver_text = silver_path.read_text(encoding="utf-8") if silver_path.is_file() else body.strip()

    records = gold.read_index(index_path)
    record_match: dict[str, Any] = next(
        (r for r in records if str(r.get("section")) == section and str(r.get("slug")) == slug),
        meta,
    )

    source_url = str(meta.get("source_url") or record_match.get("source_url") or "")
    title = str(meta.get("title") or record_match.get("title") or slug)
    render_mode = str(meta.get("render") or record_match.get("render") or "http")
    iframe_url = str(meta.get("iframe_url") or record_match.get("iframe_url") or "")

    raw_wrapper = raw_dir / section / f"{slug}.html"
    raw_render = raw_dir / section / f"{slug}.render.html"
    if raw_render.is_file():
        bronze_source = f"data/raw/{section}/{slug}.render.html (DOM React renderizado)"
        bronze_html = raw_render.read_text(encoding="utf-8")
    elif raw_wrapper.is_file():
        bronze_source = f"data/raw/{section}/{slug}.html (Envoltorio HTTP Liferay)"
        bronze_html = raw_wrapper.read_text(encoding="utf-8")
    else:
        bronze_source = "Reconstrucción estructural Bronze (caché local no descargada)"
        iframe_tag = (
            f'    <iframe src="{iframe_url}" title="{title}" width="100%"></iframe>\n'
            if iframe_url
            else ""
        )
        bronze_html = (
            "<!DOCTYPE html>\n"
            '<html lang="es">\n'
            "<head>\n"
            '  <meta charset="utf-8" />\n'
            f"  <title>{title} - EMCALI</title>\n"
            f'  <link rel="canonical" href="{source_url}" />\n'
            "</head>\n"
            '<body class="controls-visible yui3-skin-sam guest-site signed-out">\n'
            '  <header id="banner" role="banner"><!-- Menú global Liferay descartado --></header>\n'
            '  <main id="main-content" role="main">\n'
            f"{iframe_tag}"
            '    <div class="journal-content-article">\n'
            f"      <!-- Cuerpo extraído mediante modo: {render_mode} "
            f"(SHA-256: {str(meta.get('content_sha256', ''))[:16]}...) -->\n"
            "    </div>\n"
            "  </main>\n"
            '  <footer id="footer" role="contentinfo"><!-- Pie de página descartado --></footer>\n'
            "</body>\n"
            "</html>"
        )

    return MedallionDocumentView(
        section=section,
        slug=slug,
        title=title,
        source_url=source_url,
        render_mode=render_mode,
        iframe_url=iframe_url,
        bronze_source=bronze_source,
        bronze_html=bronze_html,
        silver_markdown=silver_text,
        gold_markdown_with_frontmatter=gold_raw_text,
        gold_index_record=record_match,
    )
