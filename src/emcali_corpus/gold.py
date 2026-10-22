"""Capa gold: front matter, índice JSONL y reconstrucción del catálogo."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from emcali_corpus import config
from emcali_corpus.models import CorpusDocument

FRONT_MATTER_DELIMITER = "---"


def render_front_matter(data: dict[str, Any]) -> str:
    """Serializa un diccionario plano como front matter YAML."""
    lines = [FRONT_MATTER_DELIMITER]
    for key, value in data.items():
        if isinstance(value, str):
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif value is not None:
            lines.append(f"{key}: {value}")
    lines.append(FRONT_MATTER_DELIMITER)
    return "\n".join(lines)


def write_document(document: CorpusDocument, gold_dir: Path = config.GOLD_DIR) -> Path:
    """Escribe un documento gold con su front matter."""
    path = gold_dir / document.gold_filename
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"{render_front_matter(document.front_matter())}\n\n{document.body.rstrip()}\n"
    path.write_text(content, encoding="utf-8", newline="\n")
    return path


def write_silver(
    body: str,
    slug: str,
    section: str,
    processed_dir: Path = config.PROCESSED_DIR,
) -> Path:
    """Escribe la versión silver (Markdown limpio, sin front matter)."""
    path = processed_dir / section / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.rstrip() + "\n", encoding="utf-8", newline="\n")
    return path


def write_index(records: Iterable[dict[str, Any]], index_path: Path = config.INDEX_PATH) -> Path:
    """Escribe el índice JSONL ordenado por sección y slug."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=lambda item: (item.get("section", ""), item.get("slug", "")))
    with index_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in ordered:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return index_path


def read_index(index_path: Path = config.INDEX_PATH) -> list[dict[str, Any]]:
    """Lee el índice JSONL existente."""
    if not index_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with index_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Separa el front matter YAML simple del cuerpo Markdown."""
    if not text.startswith(f"{FRONT_MATTER_DELIMITER}\n"):
        return {}, text
    parts = text.split(f"\n{FRONT_MATTER_DELIMITER}\n", 1)
    if len(parts) != 2:
        return {}, text
    header, body = parts
    data: dict[str, Any] = {}
    for line in header.splitlines()[1:]:
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        raw = raw.strip()
        try:
            data[key.strip()] = json.loads(raw) if raw.startswith('"') else int(raw)
        except (json.JSONDecodeError, ValueError):
            data[key.strip()] = raw.strip('"')
    return data, body.lstrip("\n")


def rebuild_index_from_gold(gold_dir: Path = config.GOLD_DIR) -> list[dict[str, Any]]:
    """Reconstruye el índice a partir de los archivos gold existentes."""
    records: list[dict[str, Any]] = []
    for path in sorted(gold_dir.rglob("*.md")):
        data, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        if not data:
            continue
        relative = path.relative_to(gold_dir).as_posix()
        records.append(
            {
                **data,
                "gold_path": f"data/gold/{relative}",
                "silver_path": f"data/processed/{relative}",
            }
        )
    return records


class GoldIndex:
    """Índice incremental con escritura atómica al finalizar la captura."""

    def __init__(self, index_path: Path = config.INDEX_PATH) -> None:
        self.index_path = index_path
        self._records: dict[tuple[str, str], dict[str, Any]] = {
            (str(record.get("section", "")), str(record["slug"])): record
            for record in read_index(index_path)
            if "slug" in record
        }

    def upsert(self, document: CorpusDocument) -> None:
        self._records[(document.section, document.slug)] = document.index_record()

    def upsert_many(self, documents: Iterable[CorpusDocument]) -> None:
        for document in documents:
            self.upsert(document)

    def records(self) -> list[dict[str, Any]]:
        return sorted(
            self._records.values(),
            key=lambda item: (item.get("section", ""), item.get("slug", "")),
        )

    def flush(self) -> Path:
        return write_index(self.records(), self.index_path)


def iter_gold(gold_dir: Path = config.GOLD_DIR) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Itera los documentos gold con su front matter."""
    for path in sorted(gold_dir.rglob("*.md")):
        data, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        yield path, data
