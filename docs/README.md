# Documentación — `emcali-corpus`

Carpeta de documentación técnica, registros de decisiones de arquitectura y reportes de evaluación del proyecto.

| Ruta / Archivo | Contenido |
|----------------|-----------|
| [`adr/`](./adr/) | *Architecture Decision Records* (ADR 0001 a ADR 0007): decisiones técnicas con contexto, alternativas y consecuencias. |
| [`informe-taller-1.md`](./informe-taller-1.md) | Informe técnico integral del Taller 1 (pipeline Medallion, consolidación, chunking, LangChain + DeepSeek y evaluación). |
| [`evaluacion_preguntas.md`](./evaluacion_preguntas.md) | Reporte reproducible de las 22 preguntas de prueba sobre el corpus oficial de EMCALI (`make evaluate`). |

> El resumen ejecutivo de arquitectura, stack, convenciones y el historial de decisiones viven en
> [`../CONSTITUTION.md`](../CONSTITUTION.md).

## Reglas de documentación

- Un documento, un tema claro.
- Fechas en formato ISO (`AAAA-MM-DD`).
- Enlazar cada documento relevante desde `CONSTITUTION.md` o `README.md`.
- No subir datos sensibles ni personales reales (usar siempre información pública o *fixtures* sintéticos).
