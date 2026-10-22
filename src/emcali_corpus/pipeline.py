"""Orquestación de las capas bronze, silver y gold."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from emcali_corpus import config, gold
from emcali_corpus.config import Seed
from emcali_corpus.discovery import discover_seeds
from emcali_corpus.extracting import (
    compose_body,
    extract_document,
    extract_metadata,
    find_content_frame,
)
from emcali_corpus.fetching import FetchError, HttpClient, RobotsPolicy, load_robots, normalize_url
from emcali_corpus.models import CorpusDocument, FetchResult, utc_now_iso
from emcali_corpus.rendering import BrowserRenderer, RenderError

CaptureStatus = Literal["ok", "skipped", "error"]


@dataclass(slots=True)
class CaptureOutcome:
    """Resultado de capturar una semilla."""

    seed: Seed
    status: CaptureStatus
    title: str = ""
    words: int = 0
    render_mode: str = ""
    message: str = ""

    @property
    def label(self) -> str:
        icons = {"ok": "OK", "skipped": "··", "error": "!!"}
        return icons[self.status]


@dataclass(slots=True)
class CaptureReport:
    """Resumen de una ejecución de captura."""

    outcomes: list[CaptureOutcome] = field(default_factory=list)

    @property
    def captured(self) -> int:
        return sum(1 for item in self.outcomes if item.status == "ok")

    @property
    def skipped(self) -> int:
        return sum(1 for item in self.outcomes if item.status == "skipped")

    @property
    def errors(self) -> int:
        return sum(1 for item in self.outcomes if item.status == "error")

    @property
    def words(self) -> int:
        return sum(item.words for item in self.outcomes if item.status == "ok")


class Pipeline:
    """Captura semillas y mantiene sincronizadas las tres capas del corpus."""

    def __init__(
        self,
        *,
        force: bool = False,
        render: bool = True,
        include_news: bool = True,
        data_dir: Path | None = None,
        progress: Callable[[CaptureOutcome], None] | None = None,
    ) -> None:
        self.force = force
        self.render_enabled = render
        self.include_news = include_news
        self.progress = progress
        self.data_dir = data_dir or config.DATA_DIR
        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        self.gold_dir = self.data_dir / "gold"
        self.index_path = self.gold_dir / "corpus.jsonl"
        self.errors_path = self.data_dir / "errors.jsonl"
        for directory in (self.raw_dir, self.processed_dir, self.gold_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self.client = HttpClient()
        self.index = gold.GoldIndex(self.index_path)
        self._robots: RobotsPolicy | None = None
        self._renderer: BrowserRenderer | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
        self.client.close()

    @property
    def robots(self) -> RobotsPolicy:
        if self._robots is None:
            self._robots = load_robots(self.client)
        return self._robots

    @property
    def renderer(self) -> BrowserRenderer:
        if self._renderer is None:
            self._renderer = BrowserRenderer()
            self._renderer.start()
        return self._renderer

    def _raw_paths(self, seed: Seed) -> tuple[Path, Path]:
        folder = self.raw_dir / seed.section
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{seed.slug}.html", folder / f"{seed.slug}.render.html"

    def _gold_path(self, seed: Seed) -> Path:
        return self.gold_dir / seed.section / f"{seed.slug}.md"

    def _log_error(self, seed: Seed, message: str) -> None:
        self.errors_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "captured_at": utc_now_iso(),
            "slug": seed.slug,
            "section": seed.section,
            "url": config.absolute_url(seed.url),
            "error": message,
        }
        with self.errors_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _notify(self, outcome: CaptureOutcome) -> None:
        if self.progress is not None:
            self.progress(outcome)

    def capture_seed(self, seed: Seed) -> CaptureOutcome:
        """Captura una semilla aplicando caché de bronze y renderizado si hace falta."""
        url = config.absolute_url(seed.url)
        if not self.robots.allowed(url):
            outcome = CaptureOutcome(seed, "skipped", message="bloqueado por robots.txt")
            self._notify(outcome)
            return outcome

        raw_path, render_path = self._raw_paths(seed)
        gold_path = self._gold_path(seed)
        if not self.force and gold_path.is_file() and raw_path.is_file():
            outcome = CaptureOutcome(seed, "skipped", message="ya capturado")
            self._notify(outcome)
            return outcome

        try:
            wrapper = self._fetch_wrapper(seed, url, raw_path)
            if wrapper.status == 404 or "error-404" in _page_title(wrapper.text).lower():
                outcome = CaptureOutcome(seed, "skipped", message="página no encontrada (404)")
                self._notify(outcome)
                return outcome
            if not wrapper.ok:
                raise FetchError(f"HTTP {wrapper.status} al descargar {url}")

            frame = find_content_frame(wrapper.text, wrapper.final_url or url)
            if frame and "pagina-404" in frame:
                outcome = CaptureOutcome(seed, "skipped", message="página no encontrada (404)")
                self._notify(outcome)
                return outcome

            render_mode = "http"
            content_html = wrapper.text
            if frame:
                if not self.render_enabled:
                    outcome = CaptureOutcome(
                        seed,
                        "error",
                        message="la página requiere navegador (usa --render)",
                    )
                    self._notify(outcome)
                    return outcome
                content_html = self._render_frame(frame, render_path)
                render_mode = "browser"

            return self._write_from_content(
                seed,
                wrapper.text,
                content_html,
                frame=frame,
                render_mode=render_mode,
                http_status=wrapper.status,
            )
        except (FetchError, RenderError, OSError, ValueError) as exc:
            message = str(exc)
            self._log_error(seed, message)
            outcome = CaptureOutcome(seed, "error", message=message)
            self._notify(outcome)
            return outcome

    def _write_from_content(
        self,
        seed: Seed,
        wrapper_text: str,
        content_html: str,
        *,
        frame: str,
        render_mode: str,
        http_status: int,
    ) -> CaptureOutcome:
        """Extrae y escribe gold/silver a partir de HTML ya descargado."""
        url = config.absolute_url(seed.url)
        wrapper_metadata = extract_metadata(BeautifulSoup(wrapper_text, "lxml"), url)
        title = seed.title or wrapper_metadata["title"] or _frame_title(content_html)
        extracted = extract_document(
            content_html,
            source_url=url,
            title_hint=title,
            used_frame=bool(frame),
            frame_url=frame,
        )
        body = compose_body(extracted.title, extracted.body)
        word_count = len(body.split())
        if word_count < 15:
            outcome = CaptureOutcome(
                seed,
                "skipped",
                title=extracted.title,
                message="contenido insuficiente",
            )
            self._notify(outcome)
            return outcome

        document = CorpusDocument(
            slug=seed.slug,
            section=seed.section,
            title=extracted.title,
            body=body,
            source_url=url,
            canonical_url=extracted.canonical_url or url,
            description=extracted.description or _summarize(body),
            render_mode=render_mode,
            http_status=http_status,
            language=extracted.language,
            iframe_url=frame,
            lastmod=seed.lastmod,
        )
        gold.write_silver(body, seed.slug, seed.section, self.processed_dir)
        gold.write_document(document, self.gold_dir)
        self.index.upsert(document)

        outcome = CaptureOutcome(
            seed,
            "ok",
            title=document.title,
            words=document.word_count,
            render_mode=render_mode,
        )
        self._notify(outcome)
        return outcome

    def reprocess(self) -> CaptureReport:
        """Reextrae gold y silver desde bronze, sin volver a la red."""
        report = CaptureReport()
        for path in sorted(self.gold_dir.rglob("*.md")):
            data, _body = gold.parse_front_matter(path.read_text(encoding="utf-8"))
            if not data.get("source_url") or not data.get("slug") or not data.get("section"):
                continue
            seed = Seed(
                url=urlparse(str(data["source_url"])).path or "/",
                slug=str(data["slug"]),
                title=str(data.get("title", "")),
                section=str(data["section"]),
                lastmod=str(data.get("lastmod", "")),
            )
            report.outcomes.append(self.reprocess_seed(seed))
        if report.captured:
            self.index.flush()
        return report

    def reprocess_seed(self, seed: Seed) -> CaptureOutcome:
        """Reextrae una semilla desde sus archivos bronze existentes."""
        raw_path, render_path = self._raw_paths(seed)
        if not raw_path.is_file():
            outcome = CaptureOutcome(seed, "error", message="no hay bronze para reprocesar")
            self._notify(outcome)
            return outcome

        wrapper_text = raw_path.read_text(encoding="utf-8")
        frame = find_content_frame(wrapper_text, config.absolute_url(seed.url))
        render_mode = "http"
        content_html = wrapper_text
        if frame:
            if not render_path.is_file():
                outcome = CaptureOutcome(seed, "error", message="no hay render para reprocesar")
                self._notify(outcome)
                return outcome
            content_html = render_path.read_text(encoding="utf-8")
            render_mode = "browser"

        try:
            return self._write_from_content(
                seed,
                wrapper_text,
                content_html,
                frame=frame,
                render_mode=render_mode,
                http_status=200,
            )
        except (OSError, ValueError) as exc:
            message = str(exc)
            self._log_error(seed, message)
            outcome = CaptureOutcome(seed, "error", message=message)
            self._notify(outcome)
            return outcome

    def _fetch_wrapper(self, seed: Seed, url: str, raw_path: Path) -> FetchResult:
        if raw_path.is_file() and not self.force:
            text = raw_path.read_text(encoding="utf-8")
            return FetchResult(url, url, 200, text, "text/html; charset=utf-8")
        result = self.client.fetch(url)
        if result.ok:
            raw_path.write_text(result.text, encoding="utf-8", newline="\n")
        return result

    def _render_frame(self, frame_url: str, render_path: Path) -> str:
        if render_path.is_file() and not self.force:
            return render_path.read_text(encoding="utf-8")
        html = self.renderer.render(frame_url)
        render_path.write_text(html, encoding="utf-8", newline="\n")
        return html

    def capture(self, seeds: Iterable[Seed]) -> CaptureReport:
        """Captura una colección de semillas y consolida el índice."""
        report = CaptureReport()
        for seed in seeds:
            report.outcomes.append(self.capture_seed(seed))
        if report.captured:
            self.index.flush()
        return report

    def capture_sitemap(
        self,
        *,
        sections: Iterable[str] | None = None,
        limit: int | None = None,
    ) -> CaptureReport:
        """Descubre el sitio desde el sitemap y captura todas sus páginas."""
        seeds = discover_seeds(
            self.client,
            include_news=self.include_news,
            sections=sections,
        )
        if limit is not None:
            seeds = seeds[:limit]
        return self.capture(seeds)

    def capture_urls(self, urls: Iterable[str]) -> CaptureReport:
        """Captura URLs sueltas usando un slug derivado de la ruta."""
        from emcali_corpus.discovery import seed_from_url

        return self.capture(seed_from_url(normalize_url(url)) for url in urls)

    def stats(self) -> dict[str, object]:
        """Resumen del estado del corpus en disco."""
        gold_files = sorted(self.gold_dir.rglob("*.md"))
        records = gold.read_index(self.index_path)
        total_words = sum(int(record.get("word_count", 0)) for record in records)
        sections: dict[str, int] = {}
        for record in records:
            section = str(record.get("section", "sin-seccion"))
            sections[section] = sections.get(section, 0) + 1
        rendered = sum(1 for record in records if record.get("render") == "browser")
        return {
            "documents": len(gold_files),
            "indexed": len(records),
            "words": total_words,
            "sections": dict(sorted(sections.items())),
            "rendered": rendered,
            "raw_files": len(list(self.raw_dir.rglob("*.html"))),
            "silver_files": len(list(self.processed_dir.rglob("*.md"))),
            "errors": _count_lines(self.errors_path),
            "data_dir": str(self.data_dir),
        }


def _page_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def _summarize(body: str, limit: int = 280) -> str:
    """Construye una descripción breve a partir del primer párrafo útil."""
    candidates: list[str] = []
    for block in body.split("\n\n"):
        text = " ".join(block.split())
        if not text or text.startswith(("#", "|", "-", "*", ">", "```")):
            continue
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"[*_`#]", "", text).strip()
        text = re.sub(r"\s*(?:Ver más|Ver todo|Leer más)$", "", text, flags=re.IGNORECASE)
        if len(text) < 40:
            continue
        candidates.append(text)
        if "." in text and len(text) >= 80:
            break
    if not candidates:
        return ""
    text = candidates[-1] if "." in candidates[-1] else candidates[0]
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return text


def _frame_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    heading = soup.find("h1")
    if heading is not None:
        return " ".join(heading.get_text(" ", strip=True).split())
    return ""


def _count_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def summarize(report: CaptureReport) -> str:
    """Devuelve una línea legible con el resultado de la captura."""
    return (
        f"{report.captured} capturados · {report.skipped} omitidos · "
        f"{report.errors} errores · {report.words:,} palabras".replace(",", ".")
    )


__all__ = [
    "CaptureOutcome",
    "CaptureReport",
    "Pipeline",
    "summarize",
]
