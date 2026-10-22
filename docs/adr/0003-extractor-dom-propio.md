# ADR 0003 — Extractor DOM propio en lugar de `trafilatura`

- **Fecha:** 2026-10-22
- **Estado:** Aceptada

## Contexto

Las páginas de EMCALI combinan artículos de noticias, tarjetas de servicios,
acordeones, tablas de tarifas y *call to action*. Un extractor orientado a artículos
de prensa tiende a descartar las tarjetas y los bloques laterales, que aquí sí son
contenido.

## Decisión

Implementar un conversor propio sobre BeautifulSoup que:

- selecciona el contenido editorial (`<main>`, `#main-content`, `[role=main]`);
- descarta navegación, pies, formularios, scripts, SVG y contadores;
- conserva encabezados, párrafos, listas anidadas, tablas, enlaces, citas y bloques
  de código;
- desenvuelve botones y anclas con contenido en bloque para no perder tarjetas;
- deduplica titulares repetidos y elimina *call to action* de bajo valor.

## Consecuencias

- El resultado conserva la estructura útil para RAG y para citar.
- Hay que mantener el conversor y sus pruebas.
- Se evita una dependencia pesada y un comportamiento difícil de ajustar.
