# ADR 0007 — Consolidación semántica, chunking y sistema Q&A con LangChain + DeepSeek (Taller 1)

- **Fecha:** 2026-10-29
- **Estado:** Aceptada

## Contexto

El Taller 1 del curso *Técnicas Avanzadas de IA Aplicadas en Modelos de Lenguaje* exige
entregar en un mismo repositorio:

1. El pipeline de extracción y limpieza (*web scraping*) de la empresa asignada del Valle del
   Cauca (**EMCALI E.I.C.E. E.S.P.**).
2. La consolidación de la base de conocimiento en texto limpio y su segmentación en fragmentos
   semánticamente coherentes (*chunks*).
3. La implementación funcional en **LangChain** de tres tareas sobre el corpus:
   **Resumen Ejecutivo**, **Generación de FAQ** y **Sistema Q&A** controlado por *Prompt
   Engineering* para evitar alucinaciones.
4. Una interfaz interactiva en **Streamlit** y una batería de al menos 20 preguntas de prueba.

## Decisión

Integrar directamente en el paquete `emcali_corpus` (sin alterar el contrato de
`data/gold/<sección>/<slug>.md` ni `data/gold/corpus.jsonl`) cinco nuevos módulos:

- `knowledge.py`: consolida los 164 documentos institucionales únicos (~54.625 palabras,
  deduplicados por `content_sha256` y excluyendo por defecto las 310 noticias `/w/`) y los
  segmenta mediante `MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter`.
- `prompts.py`: centraliza las plantillas de *Prompt Engineering* (tres estrategias para Q&A:
  `estricto_citado`, `razonamiento_guiado` y `minimal_zero_shot`, además de las plantillas de
  Resumen y FAQ).
- `assistant.py`: orquesta `ChatDeepSeek` (`deepseek-flash`, ventana de 1M tokens) con
  LangChain (`create_agent` y cadenas LCEL `ChatPromptTemplate | ChatDeepSeek`).
- `evaluation.py`: define una batería de 22 preguntas de prueba (incluyendo casos de control
  anti-alucinación y límites transaccionales) con evaluación automatizada de cobertura de
  términos clave y citación de URLs oficiales.
- `app.py`: expone el dashboard en Streamlit con cinco pestañas para la sustentación en vivo.

## Consecuencias

- Un único repositorio (`emcali-corpus`) satisface de extremo a extremo la entrega del Taller 1.
- El corpus institucional completo (~54k palabras, ~75k tokens) cabe holgadamente en la
  ventana de contexto de 1M tokens de `deepseek-flash` sin pérdida por truncamiento.
- Los chunks semánticos (`data/chunks.jsonl`, 1.385 fragmentos) quedan listos para la
  indexación vectorial del Módulo 2 sin modificar `data/gold/`.
