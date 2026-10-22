# ADR 0001 — Capas Medallion y contrato `data/gold/`

- **Fecha:** 2026-10-22
- **Estado:** Aceptada

## Contexto

La captura depende de un sitio cambiante y de un renderizado con navegador. Volver
a descargar todo para reprocesar la extracción es lento y frágil. El proyecto
consumidor necesita un entregable estable.

## Decisión

Usar tres capas:

- **bronze (`data/raw/`)**: HTML crudo del envoltorio y, si aplica, del iframe ya
  renderizado.
- **silver (`data/processed/`)**: Markdown limpio, sin metadatos.
- **gold (`data/gold/`)**: Markdown + *front matter*, más `corpus.jsonl`.

Solo `data/gold/` se versiona. Bronze y silver son reproducibles y quedan ignorados
por Git.

## Consecuencias

- Se puede reprocesar la extracción sin volver a la web.
- El contrato con el consumidor es explícito y auditable.
- Cambiar el esquema de `data/gold/` exige actualizar `CONSTITUTION.md`.
- El repositorio no crece con HTML intermedio.
