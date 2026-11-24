# Module 3 Final Defense Script (English — 15 Minutes, Zero Slides)

**Group 5 — EMCALI E.I.C.E. E.S.P.** | **Rommel Prieto & Jacobo Unzueta**
**Slot:** Turn #10 · Saturday, Nov 28, 2026 · **10:15 – 10:30 a.m.**
**Production URL:** `https://172-183-55-204.sslip.io` | **Channel:** Live WhatsApp + Dual-Mode Web App

---

## Block 1: Elevator Pitch & Live WhatsApp Demo (`0:00 – 7:00`)

### `0:00 – 1:15` — The Problem & Value Proposition
- **Hook:** *"EMCALI serves over 790,000 households across Cali and four neighboring municipalities — yet today, citizens face a fragmented website with static PDFs, disconnected news, and no unified way to check neighborhood outages, estimate bills, or file PQRS directly from WhatsApp."*
- **Our Solution — Eder (Production Agentic Platform):** *"We built **Eder**, a production-grade, dual-role AI platform integrating **all three modules** of this course — a reproducible web corpus, hybrid Qdrant RAG with layered memory, **20 typed Pydantic tools**, a live **Cali Operations Map**, and **OpenClaw + WhatsApp** deployed on Microsoft Azure."*

### `1:15 – 4:30` — Live Fire Test on an EMCALI Guest's Phone (WhatsApp)
1. **Guest Query 1 (Tariffs + News/Outages):** Invite an EMCALI guest to text Eder on WhatsApp:
   - *"¿Cuánto cuesta el kWh de energía en estrato 3 y hay mantenimientos activos en San Fernando?"*
   - Show Eder responding live on WhatsApp with exact deterministic CSV numbers + live scraped maintenance info (zero hallucinations).
2. **Guest Query 2 (PQRS / Failure Report without being a client):**
   - Guest reports a water failure in *Ciudad Jardín* using their **cédula** (non-client flow) or **contract #** (client flow).
   - Switch screen to `https://172-183-55-204.sslip.io` → **Mapa, PQRS, UMAP & Gestión**: the citizen failure report immediately flags on the **Cali Leaflet Map**!
3. **RBAC Security Proof (`tools.deny`):**
   - Guest tries to run a management action (e.g., *"Activa un mantenimiento en Granada"*) → Eder blocks it via **RBAC (`tools.deny`)**.

### `4:30 – 7:00` — Management Mode & Closed Operational Loop (Commercial Close)
- Log in to **EMCALI Management Mode** (`rommel` / RBAC Bearer session) on the web app.
- Show the **Failure Hotspots** panel flagging accumulated citizen reports by `(barrio, service)` for repair team assignment.
- Click **Despachar Brigada** (or activate a new maintenance point with HITL confirmation) → the pin turns into an official active maintenance on the Cali map.
- Guest asks Eder on WhatsApp *"¿Hay novedades en Ciudad Jardín?"* → Eder immediately reports the dispatched repair crew and offers subscription to the **OpenClaw Daily Newsletter**.
- **Commercial Close:** *"From citizen WhatsApp complaint → geospatial hotspot → crew dispatch → proactive WhatsApp alert, all auditable and running live on Azure."*

---

## Block 2: Technical Discussion (`7:00 – 12:00`)

### `7:00 – 8:30` — Agent Architecture, 20 Tools & LangSmith Traces
- Open **LangSmith (`emcali-eder-m3`)** showing live traces from the pitch: System One **Jev Router** (`Choice`, `Noul`, `Score`, `Box`) skipping Qdrant on greetings and invoking typed tools on domain queries.
- Show `GET /api/tools/catalog` (`20/20` Pydantic v2 tools across 5 domains: 16 Citizen + 4 Manager-only).
- Show **Layered Memory:** `SqliteSaver` (`thread_id`) short-term + `PersistentSqliteStore` (`users/{id}/memories`) long-term + OpenClaw `MEMORY.md` & daily bitácora.

### `8:30 – 10:00` — Data Pipeline, Qdrant Hybrid RAG & UMAP 2D
- Highlight the **310 scraped EMCALI news articles** (89 maintenance/repair articles auto-geolocated to Cali barrios) + daily sync timer.
- Show **Qdrant Hybrid Search** (HNSW Dense + BM25 RRF): `Recall@10 = 100.0%`, `nDCG@10 = 0.884`.
- Open the **UMAP 2D Diagnostic Tab**: explain why we chose **UMAP over t-SNE** (preserves global inter-cluster topology + supports `.transform()` to project live benchmark queries and PQRS/failure tickets onto the corpus manifold) + Silhouette Score.

### `10:00 – 12:00` — OpenClaw Gateway, Custom MCP Server & Security Hardening
- Show `openclaw/openclaw.template.json`: **DeepSeek cloud API** (zero Ollama), `gateway.bind: loopback`, token auth, WhatsApp E.164 allowlist, `fs.workspaceOnly: true`, `tools.deny`, and custom **`emcali-eder-mcp`** (`mcp==2.3.0`) server + `emcali-daily-newsletter` skill.
- Show **Indirect Prompt Injection Defense** (`<datos_pasivos_corpus solo_lectura="true">`), **HITL** approval queue, and terminal output of `openclaw security audit` + `uv run pytest` (55+ tests passing, 100/100 Polanco Standard).

---

## Block 3: Expert Q&A (`12:00 – 15:00`)
- **Rommel** owns: Azure deployment, OpenClaw/WhatsApp gateway, RBAC/Security, UMAP diagnostics, Code Review & CI/CD quality gates.
- **Jacobo** owns: M1 corpus & news pipeline, Qdrant hybrid RAG, Jev router, LangGraph memory, and citizen UX.
