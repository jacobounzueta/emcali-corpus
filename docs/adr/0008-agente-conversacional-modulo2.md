# ADR 0008: Evolución a Agente Conversacional en LangGraph con Qdrant ANN, Memorias SQLite, Router Jev y Frontend React Desacoplado (Módulo 2)

- **Estado:** Aceptado
- **Fecha:** 2026-11-13
- **Autores:** Jacobo Unzueta (`jacobo.unzueta@uao.edu.co`) · Rommel Prieto (`rommel.prieto@uao.edu.co`)

## Contexto

En el Módulo 1 se construyó el corpus Medallion (`Bronze → Silver → Gold`) de **EMCALI E.I.C.E. E.S.P.** (`164` documentos institucionales únicos, `1.385` chunks semánticos) con una interfaz de prototipo en Streamlit que inyectaba el corpus consolidado en el *system prompt*.

Para el **Módulo 2**, los requerimientos arquitectónicos cambian de forma estructural:
1. **Prohibición de Streamlit y Gradio:** Se exige un **frontend propio** (React + TypeScript + Vite) desacoplado de un **backend/API** (FastAPI) con *streaming* SSE, manejo de sesiones y errores controlados.
2. **Memoria de corto y largo plazo real:** El estado conversacional por hilo (`thread_id`) debe persistir en disco con `SqliteSaver` sobreviviendo al reinicio del proceso backend, gestionar la ventana con `trim_messages` + `SummarizationMiddleware`, y persistir el perfil/preferencias del usuario en un `Store` con *namespaces* (`users/<user_id>/memories`) recuperable desde hilos nuevos mediante `search()`.
3. **Herramientas deterministas (`@tool` CSV/JSON + Pydantic) y RAG sobre Qdrant con ANN:** Las consultas numéricas/tarifarias deben resolverse sin que el LLM invente ni calcule a ojo, y las consultas documentales deben ejecutarse sobre **Qdrant** con índice ANN **HNSW**, filtros de payload y atribución verificable.
4. **Router Agent y Gatekeeper System One (`Jev`):** Un enrutador explícito (`Choice`, `Noul`, `Score`, `Box`) debe decidir si responder directo (sin gastar búsquedas en saludos), invocar la herramienta CSV/JSON, consultar Qdrant o combinar ambas fuentes.
5. **Blindaje del RAG contra inyección indirecta:** Los fragmentos recuperados deben aislarse como datos pasivos (`<datos_pasivos_corpus>`) e inspeccionarse para bloquear instrucciones imperativas ocultas en los documentos.

## Decisiones

1. **Orquestación en LangGraph (`StateGraph`) frente a cadenas lineales (RAG Chains vs. RAG Agents):**
   - Mientras una *RAG Chain* ejecuta siempre el mismo pipeline fijo (`consulta → retrieval → prompt → LLM`), un **RAG Agent en LangGraph** evalúa primero la intención (`router_jev`), omite búsquedas innecesarias cuando la compuerta `Noul` se activa, decide dinámicamente qué herramientas invocar (`structured_tool`, `rag_search` o `hybrid_multi_tool`) y mantiene estado cíclico persistente por `thread_id`.
2. **Comparación de Orquestadores (`LangChain/LangGraph` vs. `LlamaIndex`, `Agno` y `DSPy`):**
   - Se seleccionó **LangChain 1.4 + LangGraph 1.2** por su soporte nativo de primer nivel para `SqliteSaver` (`thread_id`), `BaseStore` por *namespaces*, `trim_messages` y trazabilidad directa en **LangSmith**, superando a LlamaIndex en control explícito de grafos de estado multi-herramienta y a DSPy/Agno en madurez del protocolo de *checkpointing* e inspección de *time travel*.
3. **Búsqueda Híbrida sobre Qdrant (`HNSW Cosine` + `BM25` vía Reciprocal Rank Fusion — RRF):**
   - Se indexan los `1.385` fragmentos (+ 1 fragmento canario de auditoría de seguridad) en **Qdrant** con `HnswConfigDiff(m=16, ef_construct=128)` y se fusiona el ranking denso con un índice léxico `BM25` (`k1=1.5, b=0.75`) mediante RRF, alcanzando **`Recall@10 = 100.0%`**, **`MRR@10 = 0.943`** y **`nDCG@10 = 0.884`** sobre las 25 consultas etiquetadas.
4. **Interfaz Multimodal con Voz y Hotword (`"Eder"`, `"Oye Eder"`, `"Hola Eder"`):**
   - Se incorpora el módulo `voice.py` y el endpoint `/api/voice/command` junto con Web Speech API (`es-CO`) en el frontend React para permitir activación por palabra clave (*hotword* `"Eder"`, `"Oye Eder"` o `"Hola Eder"`), normalización fonética de siglas (`PQR`, `PQRS`, `kWh`, `Ley 1581`, `PSE`) y lectura en voz alta (TTS).

## Consecuencias

- **Positivas:** Arquitectura 100% desacoplada, determinista en local, auditable turno a turno desde el panel de Rayos-X del frontend React y con cobertura de pruebas automatizadas en `pytest`.
- **Compromisos:** Se mantiene `app.py` únicamente como artefacto histórico del Taller 1, siendo `uv run fastapi dev api/main.py` + `npm --prefix frontend run dev` el flujo oficial del Módulo 2.
