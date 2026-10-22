# ADR 0006 — Organizar gold y silver por sección

- **Fecha:** 2026-10-22
- **Estado:** Aceptada

## Contexto

El *slug* de cada documento se deriva de su ruta. Al cubrir el sitemap completo
aparecieron rutas con el mismo último segmento en secciones distintas (por ejemplo
`/telco/indicadores-pqr` y `/indicadores-pqr`). Un directorio plano de gold/silver
provocaba colisiones: el segundo documento sobrescribía al primero.

Además, un directorio plano con cientos de archivos dificulta la navegación y la
revisión de cambios.

## Decisión

Guardar gold y silver en subcarpetas por sección:

```text
data/gold/<sección>/<slug>.md
data/processed/<sección>/<slug>.md
data/raw/<sección>/<slug>.html
```

El índice `corpus.jsonl` conserva las rutas completas en `gold_path` y
`silver_path`. La sección se toma de la primera carpeta de la ruta de origen y se
registra también en el *front matter*.

## Consecuencias

- Se eliminan las colisiones de *slug* sin cambiar el esquema de metadatos.
- El índice sigue siendo la fuente de verdad para localizar cada documento.
- La estructura de `data/gold/` cambia: los consumidores deben usar `gold_path` en
  lugar de componer rutas a mano.
- Los archivos existentes se migran moviéndolos a su carpeta de sección y
  reconstruyendo el índice con `emcali-corpus index`.
