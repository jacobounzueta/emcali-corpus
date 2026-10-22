"""Pruebas de la orquestación y del reprocesamiento sin red."""

from __future__ import annotations

from pathlib import Path

from emcali_corpus import gold
from emcali_corpus.config import Seed
from emcali_corpus.models import CorpusDocument
from emcali_corpus.pipeline import Pipeline

GOLD_BODY = "# Tarifas de Energía\n\nContenido antiguo que ya no debe aparecer.\n"

RAW_HTML = """
<!doctype html>
<html lang="es">
  <head><title>Tarifas de Energía - EMCALI</title></head>
  <body>
    <main>
      <h1>Tarifas de Energía</h1>
      <p>Contenido nuevo extraído desde el archivo bronze sin volver a la red.</p>
      <p>Este segundo párrafo garantiza que el documento supere el umbral mínimo
      de palabras exigido por el pipeline antes de escribir la capa gold.</p>
    </main>
  </body>
</html>
"""


def _seed() -> Seed:
    return Seed(
        url="/energia/tarifas-de-energia",
        slug="tarifas-de-energia",
        title="Tarifas de Energía",
        section="energia",
    )


def test_reprocess_rewrites_gold_from_bronze(tmp_path: Path) -> None:
    # Arrange
    seed = _seed()
    with Pipeline(data_dir=tmp_path) as pipeline:
        document = CorpusDocument(
            slug=seed.slug,
            section=seed.section,
            title=seed.title,
            body=GOLD_BODY,
            source_url="https://www.emcali.com.co/energia/tarifas-de-energia",
        )
        gold.write_document(document, pipeline.gold_dir)
        raw_path = pipeline.raw_dir / seed.section / f"{seed.slug}.html"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(RAW_HTML, encoding="utf-8")

        # Act
        outcome = pipeline.reprocess_seed(seed)
        pipeline.index.flush()
        stats = pipeline.stats()

    # Assert
    assert outcome.status == "ok"
    assert outcome.words > 0
    assert stats["documents"] == 1
    assert stats["indexed"] == 1
    written = (tmp_path / "gold" / seed.section / f"{seed.slug}.md").read_text(encoding="utf-8")
    assert "Contenido nuevo extraído" in written
    assert "Contenido antiguo" not in written


def test_reprocess_without_bronze_reports_error(tmp_path: Path) -> None:
    # Arrange
    with Pipeline(data_dir=tmp_path) as pipeline:
        # Act
        outcome = pipeline.reprocess_seed(_seed())

    # Assert
    assert outcome.status == "error"
    assert "bronze" in outcome.message
