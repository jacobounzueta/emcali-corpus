"""Pruebas de extracción HTML → Markdown."""

from __future__ import annotations

from emcali_corpus.extracting import (
    compose_body,
    extract_document,
    find_content_frame,
)

ARTICLE_HTML = """
<!doctype html>
<html lang="es">
  <head>
    <title>Tarifas de Energía - EMCALI</title>
    <meta name="description" content="Tarifas vigentes del servicio de energía.">
    <link rel="canonical" href="https://www.emcali.com.co/energia/tarifas-de-energia">
  </head>
  <body>
    <div id="content">
      <nav><a href="/">Inicio</a> | <a href="/energia">Energía</a></nav>
      <div id="main-content" role="main">
        <article>
          <h1>Tarifas de Energía</h1>
          <p>Consulta las <strong>tarifas</strong> y elige el
            <a href="/energia/tarifas-del-mercado-regulado">mercado regulado</a>.</p>
          <h2>Opciones</h2>
          <ul>
            <li>Mercado regulado</li>
            <li>Laboratorio
              <ul><li>Ensayos</li></ul>
            </li>
          </ul>
          <table>
            <thead><tr><th>Concepto</th><th>Valor</th></tr></thead>
            <tbody><tr><td>Consumo</td><td>1.000</td></tr></tbody>
          </table>
          <img src="/img/tarifas.png" alt="Gráfica de tarifas">
          <p>Número de visitas a esta página: 42</p>
          <p>Fecha de publicación: 30/12/2022</p>
        </article>
      </div>
      <footer>Pie institucional</footer>
    </div>
  </body>
</html>
"""

REACT_HTML = """
<!doctype html>
<html lang="es">
  <head><title>EMCALI</title></head>
  <body>
    <header><nav>Transparencia | Atención</nav></header>
    <main>
      <section>
        <header><h2>Nuestros servicios</h2></header>
        <p>En EMCALI trabajamos por la región.</p>
      </section>
      <a href="/noticias"><span>General</span><h3>Noticia de prueba</h3><span>Octubre 22</span></a>
    </main>
    <footer>Pie</footer>
  </body>
</html>
"""


def test_extract_removes_chrome_and_keeps_structure() -> None:
    # Arrange
    url = "https://www.emcali.com.co/energia/tarifas-de-energia"

    # Act
    document = extract_document(ARTICLE_HTML, source_url=url)

    # Assert
    assert document.title == "Tarifas de Energía"
    assert document.description == "Tarifas vigentes del servicio de energía."
    assert document.language == "es"
    assert "Inicio" not in document.body
    assert "Pie institucional" not in document.body
    assert "Tarifas de Energía" in compose_body(document.title, document.body)
    assert "**tarifas**" in document.body
    assert "[mercado regulado](https://www.emcali.com.co/energia/tarifas-del-mercado-regulado)" in (
        document.body
    )
    assert "- Mercado regulado" in document.body
    assert "  - Ensayos" in document.body
    assert "| Concepto | Valor |" in document.body
    assert "| Consumo | 1.000 |" in document.body
    assert "Número de visitas" not in document.body
    assert "Fecha de publicación" not in document.body
    assert document.images == ["https://www.emcali.com.co/img/tarifas.png"]


def test_wrapper_iframe_is_detected() -> None:
    # Arrange
    html = """
    <html><body><div id="content">
      <p>Saltar al contenido principal</p>
      <iframe src="https://portalemcali.onrender.com/homePage"></iframe>
    </div></body></html>
    """

    # Act
    frame = find_content_frame(html, "https://www.emcali.com.co/")

    # Assert
    assert frame == "https://portalemcali.onrender.com/homePage"


def test_wrapper_with_editorial_content_has_no_frame() -> None:
    # Arrange
    html = """
    <html><body><main>
      <p>Contenido editorial suficiente para no tratarse de un envoltorio.</p>
      <p>Esta página tiene párrafos propios y no depende del iframe para mostrar su
      información principal al lector. El contenido se repite para superar el umbral
      de texto que distingue un envoltorio vacío de una página editorial completa.
      Añadimos una frase adicional para que el cuerpo supere con holgura el límite
      configurado y la detección de iframes no se active en este caso de prueba.</p>
      <iframe src="https://portalemcali.onrender.com/homePage"></iframe>
    </main></body></html>
    """

    # Act
    frame = find_content_frame(html, "https://www.emcali.com.co/")

    # Assert
    assert frame == ""


def test_repeated_blocks_are_removed() -> None:
    # Arrange
    html = """
    <html lang="es"><body><main>
      <h1>Noticias</h1>
      <p>Una noticia relevante para la comunidad.</p>
      <p>Una noticia relevante para la comunidad.</p>
      <p>Otra noticia distinta.</p>
    </main></body></html>
    """

    # Act
    document = extract_document(html, source_url="https://www.emcali.com.co/noticias")

    # Assert
    assert document.body.count("Una noticia relevante") == 1
    assert "Otra noticia distinta." in document.body


def test_repeated_lines_and_cta_headings_are_removed() -> None:
    # Arrange
    html = """
    <html lang="es"><body><main>
      <h1>Noticias</h1>
      <h2>Conoce más</h2>
      <div>
        Titular repetido<br>Titular repetido<br>Titular repetido<br>Otro titular
      </div>
    </main></body></html>
    """

    # Act
    document = extract_document(html, source_url="https://www.emcali.com.co/noticias")

    # Assert
    assert "Conoce más" not in document.body
    assert document.body.count("Titular repetido") == 1
    assert "Otro titular" in document.body


def test_publication_timestamp_lines_are_removed() -> None:
    # Arrange
    html = """
    <html lang="es"><body><main>
      <h1>Noticia</h1>
      <p>Contenido de la noticia con suficiente texto para conservarse.</p>
      <p>6/12/24, 16:25</p>
      <p>10:45 a. m.</p>
    </main></body></html>
    """

    # Act
    document = extract_document(html, source_url="https://www.emcali.com.co/w/noticia")

    # Assert
    assert "6/12/24" not in document.body
    assert "10:45" not in document.body
    assert "Contenido de la noticia" in document.body


def test_block_anchor_is_rendered_as_blocks() -> None:
    # Act
    document = extract_document(REACT_HTML, source_url="https://www.emcali.com.co/")

    # Assert
    assert "Transparencia | Atención" not in document.body
    assert "### Noticia de prueba" in document.body
    assert "Pie" not in document.body


def test_compose_body_deduplicates_and_demotes_headings() -> None:
    # Arrange
    body = "# Tarifas de Energía\n\n## Sección\n\n# Otra página"

    # Act
    composed = compose_body("Tarifas de Energía", body)

    # Assert
    assert composed.count("# Tarifas de Energía") == 1
    assert "## Otra página" in composed
    assert composed.endswith("\n")
