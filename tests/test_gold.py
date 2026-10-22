"""Pruebas de la capa gold y del índice."""

from __future__ import annotations

from pathlib import Path

from emcali_corpus.gold import (
    GoldIndex,
    parse_front_matter,
    rebuild_index_from_gold,
    render_front_matter,
    write_document,
    write_index,
)
from emcali_corpus.models import CorpusDocument


def _document() -> CorpusDocument:
    return CorpusDocument(
        slug="tarifas-de-energia",
        section="energia",
        title="Tarifas de Energía",
        body="# Tarifas de Energía\n\nContenido de prueba.\n",
        source_url="https://www.emcali.com.co/energia/tarifas-de-energia",
        description="Tarifas vigentes.",
        render_mode="browser",
        iframe_url="https://portalemcali.onrender.com/energia/ratesEnergy",
    )


def test_front_matter_roundtrip() -> None:
    # Arrange
    document = _document()

    # Act
    text = f"{render_front_matter(document.front_matter())}\n\n{document.body}"
    data, body = parse_front_matter(text)

    # Assert
    assert data["title"] == "Tarifas de Energía"
    assert data["slug"] == "tarifas-de-energia"
    assert data["iframe_url"].endswith("/energia/ratesEnergy")
    assert body.startswith("# Tarifas de Energía")


def test_write_document_and_rebuild_index(tmp_path: Path) -> None:
    # Arrange
    gold_dir = tmp_path / "gold"
    document = _document()

    # Act
    path = write_document(document, gold_dir)
    records = rebuild_index_from_gold(gold_dir)

    # Assert
    assert path.is_file()
    assert path.name == "tarifas-de-energia.md"
    assert len(records) == 1
    assert records[0]["gold_path"] == "data/gold/energia/tarifas-de-energia.md"
    assert records[0]["word_count"] == document.word_count


def test_gold_index_upserts_by_slug(tmp_path: Path) -> None:
    # Arrange
    index_path = tmp_path / "corpus.jsonl"
    document = _document()
    index = GoldIndex(index_path)

    # Act
    index.upsert(document)
    index.flush()
    reloaded = GoldIndex(index_path)

    # Assert
    assert len(reloaded.records()) == 1
    assert reloaded.records()[0]["slug"] == "tarifas-de-energia"


def test_gold_index_keeps_same_slug_in_different_sections(tmp_path: Path) -> None:
    # Arrange
    index_path = tmp_path / "corpus.jsonl"
    index = GoldIndex(index_path)
    document = _document()
    duplicate = CorpusDocument(
        slug=document.slug,
        section="otra-seccion",
        title="Otra tarifa",
        body=document.body,
        source_url="https://www.emcali.com.co/otra-seccion/tarifas-de-energia",
    )

    # Act
    index.upsert(document)
    index.upsert(duplicate)

    # Assert
    assert len(index.records()) == 2
    assert {record["section"] for record in index.records()} == {"energia", "otra-seccion"}


def test_write_index_is_sorted(tmp_path: Path) -> None:
    # Arrange
    records = [
        {"slug": "zeta", "section": "b"},
        {"slug": "alfa", "section": "a"},
    ]
    path = tmp_path / "corpus.jsonl"

    # Act
    write_index(records, path)

    # Assert
    lines = path.read_text(encoding="utf-8").splitlines()
    assert '"slug": "alfa"' in lines[0]
    assert '"slug": "zeta"' in lines[1]
