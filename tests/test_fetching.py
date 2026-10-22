"""Pruebas del cliente HTTP y de la política de robots."""

from __future__ import annotations

from emcali_corpus.fetching import RobotsPolicy, decode_html, normalize_url


def test_decode_html_prefers_header_charset() -> None:
    # Arrange
    content = "Energía".encode("latin-1")

    # Act
    decoded = decode_html(content, "text/html; charset=ISO-8859-1")

    # Assert
    assert decoded == "Energía"


def test_decode_html_uses_meta_charset() -> None:
    # Arrange
    content = '<meta charset="utf-8"><p>Energía</p>'.encode()

    # Act
    decoded = decode_html(content, "text/html")

    # Assert
    assert "Energía" in decoded


def test_normalize_url_removes_fragment_and_lowercases_host() -> None:
    # Act
    normalized = normalize_url("HTTPS://WWW.EMCALI.COM.CO/energia#tarifas")

    # Assert
    assert normalized == "https://www.emcali.com.co/energia"


def test_robots_allows_everything_when_disallow_is_empty() -> None:
    # Arrange
    policy = RobotsPolicy.from_text("User-Agent: *\nDisallow:\n")

    # Act / Assert
    assert policy.allowed("https://www.emcali.com.co/cualquier/ruta")


def test_robots_longest_match_wins() -> None:
    # Arrange
    policy = RobotsPolicy.from_text("User-Agent: *\nDisallow: /private\nAllow: /private/publico\n")

    # Act / Assert
    assert not policy.allowed("https://www.emcali.com.co/private/dato")
    assert policy.allowed("https://www.emcali.com.co/private/publico/pagina")
    assert policy.allowed("https://www.emcali.com.co/energia")
