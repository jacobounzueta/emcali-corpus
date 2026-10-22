# ADR 0004 — Descubrimiento de semillas desde el sitemap

- **Fecha:** 2026-10-22
- **Estado:** Aceptada

## Contexto

El sitio publica un `sitemap.xml` con un índice de sitemaps. Rastrear enlaces de
navegación llevaría a rutas transaccionales y duplicaría URLs con parámetros.

## Decisión

- Las capturas por defecto usan una lista curada de 18 semillas en `config.py`.
- `capture --all` recorre el índice de sitemaps, agrega los `urlset` y genera
  semillas estables a partir de la ruta.
- Se excluyen login, registro, dashboard, PQRS, pagos, pruebas, `embed` y rutas con
  parámetros transaccionales.
- Las noticias bajo `/w/` se agrupan en la sección `noticias` y se pueden omitir con
  `--no-news`.

## Consecuencias

- Cobertura amplia y reproducible sin un *crawler* general.
- El orden y los slugs son deterministas.
- Cambios en el sitemap se reflejan en la siguiente ejecución.
- Las URLs nuevas pueden requerir ajustar exclusiones o títulos curados.
