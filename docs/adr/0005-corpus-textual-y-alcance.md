# ADR 0005 — Corpus textual sin imágenes ni rutas transaccionales

- **Fecha:** 2026-10-22
- **Estado:** Aceptada

## Contexto

Las páginas incluyen logotipos, íconos, aves decorativas, banners y fotografías de
noticias. Para recuperación semántica aportan poco y añaden ruido. Además, el sitio
ofrece trámites y formularios que no deben capturarse.

## Decisión

- Registrar las URLs de imágenes en el modelo, pero no insertarlas en el Markdown.
- Conservar solo el pie de foto (`figcaption`) cuando aporte texto.
- Excluir login, registro, dashboard, PQRS, pagos, consultas y formularios externos.
- Tratar como fuera de alcance cualquier iframe que no pertenezca a los hosts de
  confianza.

## Consecuencias

- El corpus es más liviano y adecuado para *chunking*.
- Se pierde información visual que no es recuperable por texto.
- No se capturan datos personales ni se atraviesan trámites.
