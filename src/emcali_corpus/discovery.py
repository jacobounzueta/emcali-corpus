"""Descubrimiento de semillas a partir del sitemap del sitio."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from urllib.parse import unquote, urlparse

from emcali_corpus import config
from emcali_corpus.config import Seed
from emcali_corpus.fetching import Fetcher, FetchError, normalize_url
from emcali_corpus.models import sha256_text, slugify


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml(xml_text: str) -> ET.Element | None:
    """Parsea XML y devuelve ``None`` si el cuerpo está vacío o mal formado."""
    if not xml_text.strip():
        return None
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError:
        return None


def parse_sitemap_index(xml_text: str) -> list[str]:
    """Extrae las URLs de sitemaps hijos de un ``sitemapindex``."""
    root = _parse_xml(xml_text)
    if root is None or _local_name(root.tag) != "sitemapindex":
        return []
    locations: list[str] = []
    for element in root.iter():
        if _local_name(element.tag) == "loc" and element.text:
            locations.append(element.text.strip())
    return locations


def parse_urlset(xml_text: str) -> list[tuple[str, str]]:
    """Extrae pares ``(url, lastmod)`` de un ``urlset``."""
    root = _parse_xml(xml_text)
    if root is None or _local_name(root.tag) != "urlset":
        return []
    entries: list[tuple[str, str]] = []
    for url_node in root:
        if _local_name(url_node.tag) != "url":
            continue
        location = ""
        lastmod = ""
        for child in url_node:
            name = _local_name(child.tag)
            if name == "loc" and child.text:
                location = child.text.strip()
            elif name == "lastmod" and child.text:
                lastmod = child.text.strip()
        if location:
            entries.append((location, lastmod))
    return entries


def seed_from_url(url: str, lastmod: str = "") -> Seed:
    """Construye una semilla estable a partir de una URL de EMCALI."""
    path = unquote(urlparse(url).path)
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return Seed("/", "inicio", "", "portada", lastmod)

    first = segments[0]
    if first == "w":
        section = "noticias"
        slug = slugify("-".join(segments[1:]) or "noticias")
    else:
        section = slugify(first)
        slug = slugify("-".join(segments[1:]) or first)
    return Seed(url=path, slug=slug, title="", section=section, lastmod=lastmod)


def discover_seeds(
    client: Fetcher,
    *,
    include_news: bool = True,
    sections: Iterable[str] | None = None,
) -> list[Seed]:
    """Recorre el sitemap y devuelve las semillas dentro del alcance."""
    try:
        index = client.fetch(config.SITEMAP_URL)
    except FetchError as exc:
        raise RuntimeError(f"No se pudo leer el sitemap: {exc}") from exc
    if not index.ok:
        raise RuntimeError(f"El sitemap respondió HTTP {index.status}")

    children = parse_sitemap_index(index.text)
    if not children:
        children = [config.SITEMAP_URL]

    entries: dict[str, str] = {}
    for child in children:
        try:
            result = client.fetch(child)
        except FetchError:
            continue
        if not result.ok:
            continue
        for location, lastmod in parse_urlset(result.text):
            entries.setdefault(normalize_url(location), lastmod)

    if not entries:
        raise RuntimeError("El sitemap no devolvió URLs; intenta de nuevo más tarde.")

    allowed_sections = {slugify(section) for section in sections} if sections else None
    seeds: list[Seed] = []
    used_slugs: set[tuple[str, str]] = set()
    for url, lastmod in sorted(entries.items()):
        path = urlparse(url).path
        if config.is_excluded(url):
            continue
        if not include_news and (path == "/w" or path.startswith("/w/")):
            continue
        seed = seed_from_url(url, lastmod)
        if allowed_sections and seed.section not in allowed_sections:
            continue
        key = (seed.section, seed.slug)
        if key in used_slugs:
            suffix = sha256_text(seed.url)[:8]
            seed = Seed(
                url=seed.url,
                slug=slugify(f"{seed.slug}-{suffix}"),
                title=seed.title,
                section=seed.section,
                lastmod=seed.lastmod,
            )
            key = (seed.section, seed.slug)
        used_slugs.add(key)
        seeds.append(seed)
    return seeds
