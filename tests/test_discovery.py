"""Pruebas del descubrimiento de semillas y del alcance."""

from __future__ import annotations

from emcali_corpus.config import CURATED_SEEDS, absolute_url, is_excluded
from emcali_corpus.discovery import (
    discover_seeds,
    parse_sitemap_index,
    parse_urlset,
    seed_from_url,
)
from emcali_corpus.models import FetchResult

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://www.emcali.com.co/sitemap.xml?p_l_id=1</loc></sitemap>
  <sitemap><loc>https://www.emcali.com.co/sitemap.xml?p_l_id=2</loc></sitemap>
</sitemapindex>
"""

URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.emcali.com.co/energia/tarifas-de-energia</loc>
    <lastmod>2026-10-20T10:00:00-05:00</lastmod>
  </url>
  <url><loc>https://www.emcali.com.co/w/una-noticia</loc></url>
</urlset>
"""


def test_parse_sitemap_index() -> None:
    # Act
    children = parse_sitemap_index(SITEMAP_INDEX)

    # Assert
    assert children == [
        "https://www.emcali.com.co/sitemap.xml?p_l_id=1",
        "https://www.emcali.com.co/sitemap.xml?p_l_id=2",
    ]


def test_parse_urlset_reads_url_and_lastmod() -> None:
    # Act
    entries = parse_urlset(URLSET)

    # Assert
    assert entries[0] == (
        "https://www.emcali.com.co/energia/tarifas-de-energia",
        "2026-10-20T10:00:00-05:00",
    )
    assert entries[1][0].endswith("/w/una-noticia")


def test_parse_ignores_empty_or_malformed_xml() -> None:
    # Act / Assert
    assert parse_urlset("") == []
    assert parse_sitemap_index("") == []
    assert parse_urlset("<urlset><url>") == []


def test_seed_from_url_uses_section_and_slug() -> None:
    # Act
    seed = seed_from_url("https://www.emcali.com.co/transparencia/informacion-de-la-entidad")

    # Assert
    assert seed.section == "transparencia"
    assert seed.slug == "informacion-de-la-entidad"


def test_seed_from_news_url_uses_noticias_section() -> None:
    # Act
    seed = seed_from_url("https://www.emcali.com.co/w/portal-de-proveedores")

    # Assert
    assert seed.section == "noticias"
    assert seed.slug == "portal-de-proveedores"


def test_curated_seeds_match_the_sitemap_derived_paths() -> None:
    # Act / Assert
    for seed in CURATED_SEEDS:
        derived = seed_from_url(absolute_url(seed.url))
        assert (seed.section, seed.slug) == (derived.section, derived.slug), seed.url


def test_scope_excludes_private_and_transactional_paths() -> None:
    # Act / Assert
    assert is_excluded("https://www.emcali.com.co/login")
    assert is_excluded("https://www.emcali.com.co/dashboard/facturas")
    assert is_excluded("https://www.emcali.com.co/registrarse")
    assert is_excluded("https://www.emcali.com.co/valida-carta-laboral")
    assert is_excluded("https://www.emcali.com.co/contratacion3")
    assert is_excluded("https://www.emcali.com.co/atencion-y-servicio-a-la-ciudadania/pqrs")
    assert is_excluded("https://www.emcali.com.co/energia/formulario-de-servicio")
    assert is_excluded("https://otro-dominio.com/energia")
    assert not is_excluded("https://www.emcali.com.co/energia")
    assert not is_excluded("https://www.emcali.com.co/w/una-noticia")


class _FakeClient:
    """Cliente mínimo que sirve un sitemap en memoria."""

    def __init__(self, urlset: str) -> None:
        self.urlset = urlset

    def fetch(self, url: str) -> FetchResult:
        body = SITEMAP_INDEX if "sitemap.xml" in url and "?" not in url else self.urlset
        return FetchResult(url, url, 200, body, "application/xml")


def test_colliding_slugs_get_a_stable_suffix() -> None:
    # Arrange
    urlset = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://www.emcali.com.co/energia/tarifas%20x</loc></url>
      <url><loc>https://www.emcali.com.co/energia/tarifas-x</loc></url>
    </urlset>
    """
    client = _FakeClient(urlset)

    # Act
    first = discover_seeds(client)
    second = discover_seeds(client)

    # Assert
    assert len({seed.slug for seed in first}) == 2
    assert [seed.slug for seed in first] == [seed.slug for seed in second]
