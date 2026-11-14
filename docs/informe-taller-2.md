# Informe Técnico — Taller 2 (Módulo 2): Agente Conversacional con Memoria, Qdrant ANN, Tools Pydantic, Router Jev, Blindaje RAG y Frontend Propio

**Asignatura:** Técnicas Avanzadas de IA Aplicadas en Modelos de Lenguaje (2026-2S) — Universidad Autónoma de Occidente (UAO)  
**Docente:** Prof. Jan Polanco Velasco  
**Grupo 5 — Empresa:** EMCALI E.I.C.E. E.S.P.  
**Integrantes:** Jacobo Unzueta Barreto (`jacobo.unzueta@uao.edu.co`) · Rommel Prieto (`rommel.prieto@uao.edu.co` — *Code Reviewer*)

---

## 1. Resumen Ejecutivo de la Evolución (Módulo 1 → Módulo 2)

En el Módulo 2 evolucionamos el pipeline de datos Medallion de **EMCALI E.I.C.E. E.S.P.** hacia una arquitectura de **Agente Conversacional en Producción Local** con separación estricta entre:
- **Frontend Propio (`frontend/`):** SPA construida en **React 19 + TypeScript + Vite + Tailwind CSS**, comunicada por HTTP JSON y **Server-Sent Events (SSE)** para *streaming* en tiempo real, con soporte de **comandos de voz por Hotword (`"Eder"`, `"Oye Eder"`, `"Hola Eder"`)** y lectura TTS.
- **Backend / API (`api/main.py` + `src/emcali_corpus/api.py`):** Servidor **FastAPI** tipado con Pydantic v2 que ejecuta el grafo de estado en **LangGraph (`StateGraph`)**.

---

## 2. Arquitectura de Memoria Conversacional (Criterios 1.1, 1.2 y 1.3 — 25%)

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                     CAPA DE MEMORIA CONVERSACIONAL (SQLite)                  │
├──────────────────────────────────────┬───────────────────────────────────────┤
│ 1. CORTO PLAZO (Dentro de un Hilo)   │ 2. LARGO PLAZO (Entre Hilos / Cross)  │
│ • Checkpointer: SqliteSaver          │ • Store: PersistentSqliteStore        │
│ • Clave: configurable.thread_id      │ • Namespace: ("users", user_id, ...)  │
│ • Archivo: data/memory/checkpoints   │ • Archivo: data/memory/store.sqlite   │
│ • Contexto: trim_messages (1800 tok) │ • Operaciones: put(), get(), search() │
│   + SummarizationMiddleware          │ • Persiste perfil, empresa y estrato  │
└──────────────────────────────────────┴───────────────────────────────────────┘
```

1. **Corto plazo (`SqliteSaver` + `thread_id`):** Cada turno se guarda transaccionalmente en `data/memory/checkpoints.sqlite`. Si el proceso de FastAPI se detiene (`Ctrl+C`) y se reinicia, el endpoint `/api/threads/{thread_id}` y el grafo recuperan intacto el estado de la conversación. Además, expone el historial de *checkpoints* para inspección de **Time Travel**.
2. **Gestión multi-turno (`trim_messages` + `SummarizationMiddleware`):** Cuando un hilo supera el umbral de turnos, `SummarizationMiddleware` condensa los mensajes antiguos en un bloque de resumen ejecutivo y `trim_messages` garantiza que los tokens enviados al modelo nunca excedan el presupuesto (`max_tokens=1800`).
3. **Largo plazo (`Store` + `namespace`):** `PersistentSqliteStore` implementa la interfaz `BaseStore` de LangGraph sobre SQLite. Cuando el usuario menciona hechos de su perfil (ej. *"Me llamo Ana, trabajo en Carvajal y vivo en estrato 3"*), se almacenan bajo `("users", user_id, "memories")` y se recuperan mediante `store.search()` al abrir cualquier **hilo nuevo**.

---

## 3. Herramientas Deterministas, RAG Híbrido en Qdrant y Router System One (`Jev`) (Criterios 2.1, 2.2, 2.3 y 2.4 — 30%)

### 3.1 Herramientas Deterministas CSV/JSON con `@tool` y Pydantic (`tools.py`)
- **`consultar_tarifas_emcali_csv`** (`TarifasFilterInput` $\rightarrow$ `TarifaRecord`): Consulta `data/structured/tarifas_servicios_emcali.csv` (40 registros por servicio, estrato y trimestre) y calcula de manera exacta la tarifa aplicada tras subsidio/contribución, la desviación frente a la meta corporativa y la factura mensual estimada.
- **`consultar_indicadores_operativos_json`** (`IndicadoresFilterInput` $\rightarrow$ `IndicadorOperativoRecord`): Consulta `data/structured/indicadores_operativos_emcali.json` con cifras oficiales verificadas (790.000 clientes de energía, 92% cobertura fibra óptica, 47.390 solicitudes PQR en 2026-Q3, plazos de 10 y 15 días hábiles de la Ley 1581).

### 3.2 RAG Documental sobre Qdrant con Índice ANN HNSW y Búsqueda Híbrida (`vector_store.py`)
- Colección `emcali_chunks_m2` en **Qdrant** con `VectorParams(size=384, distance=Distance.COSINE)` e índice ANN **`HnswConfigDiff(m=16, ef_construct=128, full_scan_threshold=256)`**.
- Combina la búsqueda vectorial densa ANN en Qdrant (con filtros de payload por `section` e `is_canary`) y el puntaje léxico `BM25` mediante **Reciprocal Rank Fusion (RRF)**.

### 3.3 Router Agent y Gatekeeper System One (`Jev`: `Choice`, `Noul`, `Score`, `Box`) (`router.py`)
Inspirado en el paradigma System One **Jev** (*Deusser 2026*), el nodo `router_jev` calcula en $<2\text{ ms}$:
- **`Choice`:** Selecciona entre `direct_reply`, `structured_tool`, `rag_search` y `hybrid_multi_tool`.
- **`Noul`:** Compuerta de abstención que detecta saludos triviales, turnos puros de memoria del usuario o consultas fuera de alcance, evitando quemar búsquedas vectoriales en Qdrant.
- **`Score`:** Nivel de confianza calibrado $[0.0, 1.0]$.
- **`Box`:** Extracción tipada de entidades (`section_filter`, `servicio_csv`, `estrato`, `trimestre`).

### 3.4 Blindaje del RAG contra Inyección Indirecta (`security.py`)
- Escanea cada fragmento recuperado con expresiones regulares de detección de *prompt injection* (`override_previous_instructions`, `system_prompt_exfiltration`, `fake_system_directive`, `forced_false_claim`).
- Neutraliza los segmentos maliciosos y encapsula cada chunk dentro de `<datos_pasivos_corpus solo_lectura="true">...</datos_pasivos_corpus>`.

---

## 4. Evaluación Cuantitativa del Retrieval (`Recall@10` y `nDCG@10`) (Criterio 4.2 — 7%)

Se evaluó la recuperación sobre un conjunto etiquetado de **25 consultas representativas** (`src/emcali_corpus/retrieval_eval.py` y `docs/evaluacion_retrieval_m2.md`):

| Estrategia de Recuperación | Recall@5 | Recall@10 | MRR@10 | nDCG@10 |
| :--- | :---: | :---: | :---: | :---: |
| **Híbrida (Qdrant ANN Densa + BM25 RRF)** | **100.0%** | **100.0%** | **0.943** | **0.884** |
| Densa pura (Qdrant HNSW Cosine) | 96.0% | 100.0% | 0.900 | 0.852 |
| Léxica pura (BM25 k1=1.5, b=0.75) | 100.0% | 100.0% | 0.940 | 0.881 |

---

## 5. Comparativa Conceptual: RAG Chains vs. RAG Agents y Orquestadores

| Dimensión | RAG Chain (Módulo 1) | RAG Agent con LangGraph (Módulo 2) |
| :--- | :--- | :--- |
| **Flujo de control** | Lineal e invariable (siempre busca o inyecta contexto). | Grafo condicional (`StateGraph`) guiado por el Router `Jev`. |
| **Eficiencia en saludos** | Quema tokens/búsquedas incluso ante un `"Hola"`. | Activa compuerta `Noul` y responde en 0 búsquedas. |
| **Fuentes heterogéneas** | Solo texto no estructurado. | Arbitra y combina `@tool` CSV/JSON (Pydantic) + Qdrant ANN. |
| **Memoria** | Historial efímero en RAM de sesión. | `SqliteSaver` (`thread_id`) + `Store` cross-thread en disco. |
