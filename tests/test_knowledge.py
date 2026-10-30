"""Pruebas de consolidación de la base de conocimiento y segmentación (chunking)."""

from __future__ import annotations

from pathlib import Path

from emcali_corpus.gold import write_document, write_index
from emcali_corpus.knowledge import (
    chunk_documents,
    compute_funnel_metrics,
    consolidate_knowledge_base,
    export_knowledge_artifacts,
    load_gold_documents,
    load_medallion_document_view,
)
from emcali_corpus.models import CorpusDocument


def _sample_gold_dir(tmp_path: Path) -> tuple[Path, Path]:
    gold_dir = tmp_path / "gold"
    index_path = gold_dir / "corpus.jsonl"

    doc_energy = CorpusDocument(
        slug="tarifas-de-energia",
        section="energia",
        title="Tarifas de Energía",
        body=(
            "# Tarifas de Energía\n\n"
            "## Residencial\n\n"
            "En EMCALI publicamos las tarifas vigentes para el sector residencial.\n\n"
            "## Comercial\n\n"
            "Consulta los valores por kilovatio hora (kWh) para comercios.\n"
        ),
        source_url="https://www.emcali.com.co/energia/tarifas-de-energia",
        description="Tarifas oficiales de energía.",
    )
    doc_news = CorpusDocument(
        slug="nota-prensa",
        section="noticias",
        title="Nota de prensa",
        body="# Nota de prensa\n\nContenido informativo de prensa.\n",
        source_url="https://www.emcali.com.co/w/nota-prensa",
        description="Noticia reciente.",
    )

    write_document(doc_energy, gold_dir)
    write_document(doc_news, gold_dir)
    write_index([doc_energy.index_record(), doc_news.index_record()], index_path)
    return gold_dir, index_path


def test_load_gold_documents_excludes_news_by_default(tmp_path: Path) -> None:
    # Arrange
    gold_dir, index_path = _sample_gold_dir(tmp_path)

    # Act
    docs_no_news = load_gold_documents(gold_dir=gold_dir, index_path=index_path, include_news=False)
    docs_with_news = load_gold_documents(
        gold_dir=gold_dir, index_path=index_path, include_news=True
    )

    # Assert
    assert len(docs_no_news) == 1
    assert docs_no_news[0].section == "energia"
    assert len(docs_with_news) == 2


def test_consolidate_knowledge_base_includes_metadata_and_url(tmp_path: Path) -> None:
    # Arrange
    gold_dir, index_path = _sample_gold_dir(tmp_path)

    # Act
    bundle = consolidate_knowledge_base(gold_dir=gold_dir, index_path=index_path)

    # Assert
    assert bundle.document_count == 1
    assert bundle.total_words > 10
    assert "https://www.emcali.com.co/energia/tarifas-de-energia" in bundle.consolidated_text
    assert "## [ENERGIA] Tarifas de Energía" in bundle.consolidated_text


def test_chunk_documents_preserves_headings_and_source_url(tmp_path: Path) -> None:
    # Arrange
    gold_dir, index_path = _sample_gold_dir(tmp_path)
    docs = load_gold_documents(gold_dir=gold_dir, index_path=index_path)

    # Act
    chunks = chunk_documents(docs, chunk_size=120, chunk_overlap=20)

    # Assert
    assert len(chunks) >= 2
    assert all(ch.source_url.endswith("/tarifas-de-energia") for ch in chunks)
    assert any("Residencial" in ch.heading_path for ch in chunks)


def test_export_knowledge_artifacts_writes_md_and_jsonl(tmp_path: Path) -> None:
    # Arrange
    out_md = tmp_path / "knowledge_base.md"
    out_chunks = tmp_path / "chunks.jsonl"

    # Act
    bundle, chunks = export_knowledge_artifacts(
        output_md=out_md,
        output_chunks=out_chunks,
        curated_only=True,
    )

    # Assert
    assert out_md.is_file()
    assert out_chunks.is_file()
    assert bundle.document_count > 0
    assert len(chunks) >= bundle.document_count


def test_compute_funnel_metrics_counts_stages(tmp_path: Path) -> None:
    # Arrange
    gold_dir, index_path = _sample_gold_dir(tmp_path)

    # Act
    metrics = compute_funnel_metrics(gold_dir=gold_dir, index_path=index_path)

    # Assert
    assert metrics.gold_total_docs == 2
    assert metrics.news_docs == 1
    assert metrics.institutional_unique_docs == 1
    assert metrics.institutional_tokens >= metrics.institutional_words


def test_load_medallion_document_view_returns_all_layers(tmp_path: Path) -> None:
    # Arrange
    gold_dir, index_path = _sample_gold_dir(tmp_path)

    # Act
    view = load_medallion_document_view(
        "energia",
        "tarifas-de-energia",
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        gold_dir=gold_dir,
        index_path=index_path,
    )

    # Assert
    assert view.title == "Tarifas de Energía"
    assert "<!DOCTYPE html>" in view.bronze_html
    assert "## Residencial" in view.silver_markdown
    assert 'slug: "tarifas-de-energia"' in view.gold_markdown_with_frontmatter
    assert view.gold_index_record["section"] == "energia"
