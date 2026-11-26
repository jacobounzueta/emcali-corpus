# ⚡ EMCALI ¡Siempre Juntos! — Melva, Plataforma Agéntica de Operaciones y Atención Ciudadana (M1 · M2 · M3)

[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/jacobounzueta/emcali-corpus/actions/workflows/ci.yml/badge.svg)](https://github.com/jacobounzueta/emcali-corpus/actions/workflows/ci.yml)
[![uv](https://img.shields.io/badge/uv-package_manager-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/Ruff-lint_%26_format-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![ty](https://img.shields.io/badge/ty-type_checked-2B5B84)](https://github.com/astral-sh/ty)
[![pytest](https://img.shields.io/badge/pytest-65_passed-0A9EDC?logo=pytest&logoColor=white)](tests/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph_1.2-1C3C3C?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![MCP](https://img.shields.io/badge/MCP-20_Typed_Tools-579624)](docs/catalogo-20-tools-m3.md)
[![Qdrant](https://img.shields.io/badge/Qdrant-HNSW_ANN_%2B_UMAP-DC244C)](https://qdrant.tech/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_SSE-009688?logo=fastapi&logoColor=white)](api/main.py)
[![React 19](https://img.shields.io/badge/Frontend-React_19_%2B_TS_%2B_Vite-61DAFB?logo=react&logoColor=black)](frontend/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits&logoColor=white)](https://conventionalcommits.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Plataforma agéntica en producción para las **Empresas Municipales de Cali — [EMCALI E.I.C.E. E.S.P.](https://www.emcali.com.co/)**, regida por [CONSTITUTION.md](CONSTITUTION.md) como fuente única de verdad técnica (**100/100 + 5 Bonus Archify** en el estándar del Prof. Jan Polanco).

Integra de principio a fin los **3 módulos** del curso TAAML:
- **Módulo 1 (Datos & Corpus Medallion):** Pipeline reproducible `Bronze → Silver → Gold` sobre el portal oficial de EMCALI (`1.386` chunks verificados) + ingesta en vivo del feed 2026 de noticias y mantenimientos.
- **Módulo 2 (Agente LangGraph, Memoria y RAG Blindado):** Grafo `StateGraph` con **Qdrant HNSW + BM25 (RRF)** (`Recall@10 = 100.0%`, `nDCG@10 = 0.884`), memoria de corto plazo (`SqliteSaver`) y largo plazo (`PersistentSqliteStore`), **Router System One (`Jev`)** con compuerta semántica coseno y blindaje contra inyección indirecta (`<datos_pasivos_corpus>`).
- **Módulo 3 (Operaciones Reales, 20 Tools, MCP, OpenClaw WhatsApp y Despliegue Azure):**
  - **Despliegue productivo en Microsoft Azure VPS** con Caddy Auto-HTTPS: **[https://172-183-55-204.sslip.io](https://172-183-55-204.sslip.io)**
  - **WhatsApp Business Real (eSIM dedicada `+57 323 892 3289`)** conectado a **OpenClaw Gateway** (`dmPolicy: "allowlist"` E.164 administrable en vivo desde IAM, auto-allowlist al registrarse y notificaciones proactivas de brigadas/PQRS/fallas).
  - **20 herramientas tipadas (`@tool` + Pydantic v2)** (16 ciudadanas + 4 de gerencia con `tools.deny` + 4 compuertas HITL) documentadas en [`docs/catalogo-20-tools-m3.md`](docs/catalogo-20-tools-m3.md) y expuestas por nuestro servidor MCP propio (`emcali-eder-mcp`) con trazabilidad **LangSmith (`@traceable`)** tanto en Web como en WhatsApp.
  - **Portal Web EMCALI 2026:** Portada centrada en el **Mapa Operativo de Cali** (Leaflet), barra lateral unificada (**General · Gestión EMCALI · Académico**), sección dedicada de **PQRS**, **Gatekeeper Jev Noticias → Mapa** (`Noul` veto a notas positivas), diagnóstico **UMAP 2D** y **drawer flotante de Melva** con **voz neural femenina colombiana** (`es-CO-SalomeNeural` + switch automático a **ElevenLabs**).

---

## 📑 Tabla de Contenidos

- [Inicio Rápido](#-inicio-rápido-prueba-de-3-minutos)
- [Arquitectura Interactiva (Archify)](#-arquitectura-interactiva-archify--módulos-1-2-y-3)
- [Capacidades de Módulo 3 (Operaciones & WhatsApp)](#-capacidades-de-módulo-3-operaciones-en-vivo)
- [Evaluación Cuantitativa & Regresión CI](#-diseño-y-evaluación-cuantitativa-del-retrieval-en-qdrant)
- [Voz Neural Colombiana (Melva Live & WhatsApp)](#-voz-neural-colombiana-melva-live--whatsapp)
- [Estructura del Proyecto](#-estructura-del-proyecto-m1--m2--m3)
- [Créditos y Licencia](#-créditos-y-roles-del-equipo-grupo-5--emcali)

---

## 🚀 Inicio Rápido (Prueba de 3 Minutos)

Requisitos: [uv](https://docs.astral.sh/uv/), Python 3.13 y Node.js 20+.

```bash
# 1. Sincronizar dependencias de Python con uv
uv sync

# 2. Terminal 1 — Levantar el Backend/API en FastAPI (:8000)
uv run fastapi dev api/main.py

# 3. Terminal 2 — Levantar el Frontend React 19 + TypeScript + Vite (:5173)
npm --prefix frontend install
npm --prefix frontend run dev

# 4. (Opcional) Levantar el servidor MCP propio (stdio para OpenClaw)
uv run emcali-mcp

# 5. Verificar calidad completa (Ruff + ty + 65 pruebas pytest con gates LLMOps)
make check
```

---

## 🏗️ Arquitectura Interactiva (Archify) — Módulos 1, 2 y 3

> 🗺️ **Explora el mapa interactivo de arquitectura (Archify):** abre [`docs/arquitectura.html`](./docs/arquitectura.html) en tu navegador o inspecciona la especificación estructurada en [`docs/arquitectura.json`](./docs/arquitectura.json).

### 1. Capas de la Arquitectura Desacoplada (Web EMCALI 2026 + WhatsApp OpenClaw)

| Capa | Componentes Principales | Responsabilidad |
| :--- | :--- | :--- |
| **Canales & UI** | Portal React 19 ([`frontend/`](./frontend/)) · WhatsApp Business (`+57 323 892 3289` vía OpenClaw) | Portada con Mapa Operativo de Cali, barra lateral unificada (General / Gestión EMCALI / Académico), PQRS dedicado, drawer flotante de **Melva** con voz neural colombiana (`es-CO-SalomeNeural` / ElevenLabs) y bot de WhatsApp con allowlist E.164. |
| **API & MCP** | FastAPI ([`api/main.py`](./api/main.py), `api.py`, `api_m3.py`) · Servidor MCP propio ([`mcp_server.py`](./src/emcali_corpus/mcp_server.py)) | Streaming SSE, PBKDF2-SHA256 RBAC (`citizen` vs `manager`), respuestas automáticas por WhatsApp al gestionar PQRS/fallas, y exposición de las 20 herramientas hacia OpenClaw con trazabilidad LangSmith `@traceable`. |
| **Grafo & Control** | LangGraph `StateGraph` ([`agent_graph.py`](./src/emcali_corpus/agent_graph.py)) · Router **Jev** ([`router.py`](./src/emcali_corpus/router.py)) · Blindaje RAG ([`security.py`](./src/emcali_corpus/security.py)) | Primitivas Jev (`Choice`, `Noul`, `Score`, `Box`) para enrutamiento de chat e ingesta de noticias al mapa, 20 `@tool` Pydantic v2 (16 ciudadanas + 4 gerencia `tools.deny` + 4 HITL), y escudo contra inyección indirecta `<datos_pasivos_corpus>`. |
| **Datos & Observabilidad** | Qdrant HNSW + BM25 RRF ([`vector_store.py`](./src/emcali_corpus/vector_store.py)) · SQLite Ops + Memoria ([`ops_db.py`](./src/emcali_corpus/ops_db.py), [`memory.py`](./src/emcali_corpus/memory.py)) · LangSmith | 1,386 fragmentos verificados, UMAP 2D, `SqliteSaver` (corto plazo por hilo) + `PersistentSqliteStore` (largo plazo cross-thread por namespace), y trazas unificadas Web + WhatsApp MCP en `emcali-eder-m3`. |

### 2. Memoria de Corto Plazo (`Checkpointer`) vs. Largo Plazo (`Store`)

| Tipo de Memoria | Motor y Almacenamiento | Alcance y Comportamiento |
| :--- | :--- | :--- |
| **Corto Plazo (Hilo Único)** | `SqliteSaver` (`data/memory/checkpoints.sqlite`) + `trim_messages (1800 tokens)` + `SummarizationMiddleware` | Conserva el contexto y *Time Travel* de un hilo (`thread_id`) sobreviviendo reinicios del servidor FastAPI. |
| **Largo Plazo (Cross-Thread)** | `PersistentSqliteStore` (`data/memory/store.sqlite`) con namespace `('users', user_id, 'memories')` | Extrae y recupera hechos persistentes del ciudadano (nombre, barrio, estrato, preferencias) disponibles incluso al abrir un hilo nuevo. |
| **Historial Aislado por Usuario** | `user_chat_logs` (`data/ops/emcali_ops.sqlite`) | Cada usuario autenticado (o anónimo) mantiene su propio log conversacional aislado (`GET`/`DELETE /api/chat/history`). |

### 3. Router System One (`Jev`: `Choice`, `Noul`, `Score`, `Box`)

```text
Consulta Usuario ──► [Gatekeeper Jev (router.py)]
                       ├── Box   : Extrae {section_filter, servicio_csv, estrato, trimestre, domain_relevance_score}
                       ├── Noul  : ¿Saludo ("Hola"), memoria pura o fuera de dominio (coseno < 0.18)?
                       │             └── Sí (Noul=True) ──► direct_reply (0 búsquedas en Qdrant)
                       ├── Score : Confianza calibrada [0.00 – 1.00]
                       └── Choice:
                             ├─► m3_ops_tool       ──► Ciclo ReAct con 20 @tool Pydantic v2 (RBAC + HITL)
                             ├─► structured_tool   ──► @tool CSV/JSON Pydantic (tarifas e indicadores exactos)
                             ├─► rag_search        ──► Qdrant ANN HNSW + BM25 RRF ──► <datos_pasivos_corpus>
                             └─► hybrid_multi_tool ──► Combina CSV/JSON Pydantic + Qdrant ANN + Blindaje
```

---

## 🌐 Capacidades de Módulo 3 (Operaciones en Vivo)

- **Catálogo oficial de 20 herramientas (`@tool` + Pydantic v2):** ver especificación completa en [`docs/catalogo-20-tools-m3.md`](docs/catalogo-20-tools-m3.md) y en vivo vía `GET /api/tools/catalog`.
- **Mapa Operativo de Cali (`cali_geo.py` + Leaflet):** 80+ barrios verificados (Comunas 1–22 + Yumbo, Jamundí, Candelaria y Puerto Tejada) con rechazo estricto de barrios inexistentes (`BARRIO_NO_RECONOCIDO`), filtros por servicio con color acorde, **Hotspots de Fallas Ciudadanas**, despacho idempotente de brigadas (`🚑 Brigada en sitio` / `✅ Marcar Resuelto`) y **Gatekeeper Jev Noticias → Mapa** (`Noul` veto para comunicados positivos).
- **Gestión de PQRS y Reportes de Falla con Respuesta por WhatsApp:** Flujo cliente (contrato) y no-cliente (cédula). Cuando un usuario `manager` actualiza un radicado o reporte en el portal, el sistema envía automáticamente la notificación/respuesta oficial por WhatsApp al ciudadano.
- **IAM & Allowlist WhatsApp en Vivo:** Autenticación PBKDF2-SHA256 (`POST /api/auth/login` y `POST /api/auth/register` estrictamente `citizen` sin escalamiento de privilegios), gestión de roles RBAC (`citizen` / `manager`) y sincronización inmediata con `channels.whatsapp.allowFrom` de OpenClaw.
- **Guion de Sustentación Final (Inglés, 15 min):** [`docs/guion-sustentacion-modulo-3-en.md`](docs/guion-sustentacion-modulo-3-en.md).

---

## 📊 Diseño y Evaluación Cuantitativa del Retrieval en Qdrant

El módulo [`src/emcali_corpus/retrieval_eval.py`](src/emcali_corpus/retrieval_eval.py) evalúa **25 consultas etiquetadas** ([`docs/evaluacion_retrieval_m2.md`](docs/evaluacion_retrieval_m2.md)) y [`tests/test_llmops_regressions.py`](tests/test_llmops_regressions.py) aplica gates automáticos en CI:

| Estrategia de Recuperación en Qdrant | Recall@5 | Recall@10 | MRR@10 | nDCG@10 |
| :--- | :---: | :---: | :---: | :---: |
| **Híbrida (Qdrant ANN Densa + BM25 vía RRF)** | **100.0%** | **100.0%** | **0.943** | **0.884** |
| Densa pura (`Qdrant HNSW Cosine`, `dim=384`) | 96.0% | 100.0% | 0.900 | 0.852 |
| Léxica pura (`BM25`, `k1=1.5`, `b=0.75`) | 100.0% | 100.0% | 0.940 | 0.881 |

---

## 🎙️ Voz Neural Colombiana (`Melva Live` & WhatsApp)

- **Síntesis Neural con Fallback Automático (`voice.py` · `POST /api/voice/tts` · `tts_cli.py`):** Utiliza **ElevenLabs** (`eleven_flash_v2_5`) cuando `ELEVENLABS_API_KEY` está configurada, con fallback automático a **Microsoft Edge Neural TTS (`es-CO-SalomeNeural`)** y voz femenina del navegador.
- **Hotword `Melva Live` en Web:** Activación por `"Melva"`, `"Oye Melva"`, `"Hola Melva"`, corrección fonética colombiana (`EMCALI`, `PQRS`, `kWh`, `Ley 1581`, `PSE`) y protección *half-duplex* + *Barge-In*.
- **WhatsApp bajo demanda (`tts.auto: "tagged"`):** Responde en texto por defecto y genera notas de voz `.ogg` (vía `@openclaw/tts-local-cli` + `ffmpeg`) únicamente cuando el usuario lo solicita explícitamente.

---

## 🗂️ Estructura del Proyecto (M1 + M2 + M3)

```text
emcali-corpus/
├── api/
│   └── main.py                         # Punto de entrada FastAPI (`uv run fastapi dev api/main.py`)
├── deploy/                             # systemd units (emcali-api, daily-sync timer) y Caddyfile HTTPS
├── openclaw/                           # Plantilla OpenClaw + workspace (SOUL.md, AGENTS.md, MEMORY.md, skills/)
├── frontend/                           # Portal React 19 + TypeScript + Vite (Diseño EMCALI 2026)
│   └── src/
│       ├── App.tsx                     # Barra lateral unificada, portada Mapa, drawer flotante Melva y vistas TAAML
│       └── components/
│           ├── M3OperationsSuite.tsx   # Mapa, PQRS, Reportes de Falla, Noticias, UMAP, Auth e IAM/Allowlist
│           └── CaliMapPanel.tsx        # Mapa georreferenciado Leaflet/OSM de Cali
├── data/
│   ├── gold/                           # Capa Gold Medallion + corpus.jsonl
│   ├── chunks.jsonl                    # 1.386 fragmentos semánticos para Qdrant
│   └── structured/                     # Datasets deterministas CSV/JSON validados con Pydantic
├── docs/
│   ├── adr/                            # Architecture Decision Records (ADR-0001+)
│   ├── arquitectura.html & .json       # Mapa interactivo de arquitectura (Archify)
│   ├── catalogo-20-tools-m3.md         # Documentación oficial de las 20 herramientas Pydantic + RBAC + HITL
│   ├── guion-sustentacion-modulo-3-en.md
│   └── evaluacion_retrieval_m2.md
├── src/emcali_corpus/
│   ├── api.py & api_m3.py              # FastAPI SSE, Auth/RBAC, Mapa, PQRS, Fallas, Noticias, HITL, Voz TTS
│   ├── agent_graph.py                  # LangGraph StateGraph (Checkpointer + Store + Router Jev + 20 Tools)
│   ├── router.py                       # Router System One Jev + compuerta semántica coseno
│   ├── tools.py & tools_m3.py          # 20 @tool tipadas con Pydantic v2, RBAC (tools.deny) y HITL
│   ├── mcp_server.py                   # Servidor MCP propio (`emcali-eder-mcp`) con @traceable LangSmith
│   ├── ops_db.py & cali_geo.py         # SQLite operativo + catálogo WGS84 estricto de Cali (80+ barrios)
│   ├── news_sync.py                    # Sync noticias en vivo EMCALI 2026 + Gatekeeper Jev Noticias → Mapa
│   ├── vector_store.py & umap_diagnostics.py  # Qdrant HNSW+BM25 RRF + proyección UMAP 2D
│   ├── memory.py & security.py         # SqliteSaver, BaseStore y blindaje contra inyección indirecta
│   └── voice.py & tts_cli.py           # Hotword Melva Live + TTS neural (ElevenLabs / Edge es-CO-SalomeNeural)
└── tests/                              # Suite de 65 pruebas automatizadas (pytest + CI LLMOps regression gates)
```

---

## 👥 Créditos y Roles del Equipo (Grupo 5 — EMCALI)

| Integrante | Correo Institucional | Rol en el Proyecto |
| :--- | :--- | :--- |
| **Jacobo Unzueta Barreto** | `jacobo.unzueta@uao.edu.co` | **Ingeniería de Datos, RAG Híbrido Qdrant y Experiencia Ciudadana:** Pipeline Medallion, ingesta de noticias, indexación Qdrant HNSW+BM25, Router Jev, memoria LangGraph y blindaje RAG. |
| **Rommel Prieto** *(Code Reviewer)* | `rommel.prieto@uao.edu.co` | **Arquitectura Agéntica M3, Despliegue Azure, OpenClaw/WhatsApp, Seguridad y Calidad:** 20 Tools Pydantic, servidor MCP propio, OpenClaw WhatsApp (eSIM), IAM/RBAC/HITL, UMAP 2D, portal EMCALI 2026, voz neural y CI/CD estándar Polanco. |

---

## 📄 Licencia

Distribuido bajo la licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para el texto completo.
