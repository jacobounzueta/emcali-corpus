"""Modelos del dominio del corpus."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, max_length: int = 80) -> str:
    """Convierte texto libre en un slug estable en ASCII."""
    normalized = (
        value.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
        .replace("ü", "u")
    )
    slug = SLUG_RE.sub("-", normalized).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "documento"


def utc_now_iso() -> str:
    """Devuelve la fecha actual en UTC con formato ISO 8601."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    """Calcula el hash SHA-256 de un texto UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class FetchResult:
    """Respuesta HTTP normalizada."""

    url: str
    final_url: str
    status: int
    text: str
    content_type: str
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type.lower() or not self.content_type


@dataclass(slots=True)
class ExtractedDocument:
    """Resultado de convertir una página HTML a Markdown limpio."""

    title: str
    body: str
    description: str = ""
    canonical_url: str = ""
    language: str = "es"
    links: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    used_frame: bool = False
    frame_url: str = ""


@dataclass(slots=True)
class CorpusDocument:
    """Documento de la capa gold listo para el índice y el consumo RAG."""

    slug: str
    section: str
    title: str
    body: str
    source_url: str
    canonical_url: str = ""
    description: str = ""
    captured_at: str = field(default_factory=utc_now_iso)
    render_mode: str = "http"
    http_status: int = 200
    language: str = "es"
    iframe_url: str = ""
    lastmod: str = ""

    @property
    def content_sha256(self) -> str:
        return sha256_text(self.body)

    @property
    def word_count(self) -> int:
        return len(self.body.split())

    @property
    def gold_filename(self) -> str:
        return f"{self.section}/{self.slug}.md"

    @property
    def silver_filename(self) -> str:
        return f"{self.section}/{self.slug}.md"

    def front_matter(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "title": self.title,
            "slug": self.slug,
            "section": self.section,
            "source_url": self.source_url,
            "canonical_url": self.canonical_url or self.source_url,
            "description": self.description,
            "captured_at": self.captured_at,
            "render": self.render_mode,
            "http_status": self.http_status,
            "language": self.language,
            "content_sha256": self.content_sha256,
            "word_count": self.word_count,
        }
        if self.iframe_url:
            data["iframe_url"] = self.iframe_url
        if self.lastmod:
            data["lastmod"] = self.lastmod
        return data

    def index_record(self) -> dict[str, Any]:
        record = self.front_matter()
        record["gold_path"] = f"data/gold/{self.gold_filename}"
        record["silver_path"] = f"data/processed/{self.silver_filename}"
        return record
