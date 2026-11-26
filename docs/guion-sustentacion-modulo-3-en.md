# Module 3 Final Defense Script (English — 15 Minutes, Zero Slides)

**Group 5 — EMCALI E.I.C.E. E.S.P.** | **Rommel Prieto & Jacobo Unzueta**
**Slot:** Turn #10 · Saturday, Nov 28, 2026 · **10:15 – 10:30 a.m.**
**Production URL:** `https://172-183-55-204.sslip.io` | **Channel:** Live WhatsApp + Dual-Mode Web App

---

## Block 1: Elevator Pitch & Live WhatsApp Demo (`0:00 – 7:00`)

### `0:00 – 1:15` — The Problem & Value Proposition
- **Hook:** *"EMCALI serves over 790,000 households across Cali and four neighboring municipalities — yet today, citizens face a fragmented website with static PDFs, disconnected news, and no unified way to check neighborhood outages, estimate bills, or file PQRS directly from WhatsApp."*
- **Our Solution — Mile (Production Agentic Platform):** *"We built **Mile**, a production-grade, dual-role AI platform integrating **all three modules** of this course — a reproducible web corpus, hybrid Qdrant RAG with layered memory, **20 typed Pydantic tools**, a live **Cali Operations Map**, and **OpenClaw + WhatsApp** deployed on Microsoft Azure."*

### `1:15 – 4:30` — Live Fire Test on an EMCALI Guest's Phone (WhatsApp)
1. **Live Guest Onboarding (3 seconds):** Add an EMCALI guest's phone number via **IAM → Allowlist WhatsApp** (or have them register on the web portal, which auto-allowlists them and sends Mile's welcome WhatsApp message).
2. **Guest Query 1 (Tariffs + News/Outages + Voice):** Invite the guest to text Mile (`+57 323 892 3289`) on WhatsApp:
   - *"¿Cuánto cuesta el kWh de energía en estrato 3 y hay mantenimientos activos en San Fernando?"*
   - Show Mile responding live with exact deterministic CSV numbers + live scraped maintenance info (zero hallucinations — even refusing to guess if a quarter/barrio doesn't exist, e.g. *"Manhattan"* or missing Q1 water data). Optionally trigger an on-demand Colombian neural voice note (`es-CO-SalomeNeural` / ElevenLabs-ready).
3. **Guest Query 2 (PQRS / Failure Report without being a client):**
   - Guest reports a water failure in *Ciudad Jardín* using their **cédula** (non-client flow) or **contract #** (client flow).
   - Switch screen to `https://172-183-55-204.sslip.io`: the **EMCALI 2026 Map-first landing** immediately flags the citizen failure report on the **Cali Leaflet Map**, while **Mile** sits cleanly in the bottom-right green dock (just like EMCALI's real 2026 portal)!
4. **RBAC Security Proof (`tools.deny`):**
   - Guest tries to run a management action (e.g., *"Activa un mantenimiento en Granada"*) → Mile blocks it via **RBAC (`tools.deny`)** based on E.164 phone identity.

### `4:30 – 7:00` — Management Mode & Closed Operational Loop (Commercial Close)
- Log in to **EMCALI Management Mode** (`Mi cuenta ↗` → `rommel` / PBKDF2-SHA256 Bearer session; zero prefilled credentials).
- Show the **Failure Hotspots** panel (with `(i)` explainer) flagging accumulated citizen reports by `(barrio, service)` for repair team assignment.
- Click **Despachar Brigada** (idempotent — switches to **`🚑 Brigada en sitio`** + **`✅ Marcar Resuelto`**) or reply directly to a ticket in **PQRS / Failure Reports** → the pin turns into an official active maintenance on the Cali map and triggers a **proactive WhatsApp alert** directly to the citizen's phone!
- Guest asks Mile on WhatsApp *"¿Hay novedades en Ciudad Jardín?"* → Mile immediately reports the dispatched repair crew and offers subscription to the **OpenClaw Daily Newsletter**.
- **Commercial Close:** *"From citizen WhatsApp complaint → geospatial hotspot → crew dispatch → proactive WhatsApp reply, all auditable and running live on Azure."*

---

## Block 2: Technical Discussion (`7:00 – 12:00`)

### `7:00 – 8:30` — Agent Architecture, 20 Tools & Unified LangSmith Traces
- Open **LangSmith (`emcali-eder-m3`)** showing live traces from **both** Web LangGraph AND WhatsApp MCP (`@traceable`, tags `whatsapp`/`mcp`): System One **Jev Router** (`Choice`, `Noul`, `Score`, `Box`) + cosine domain-relevance gate skipping Qdrant on greetings/off-topic and invoking typed tools on domain queries.
- Show `GET /api/tools/catalog` & `docs/catalogo-20-tools-m3.md` (`20/20` Pydantic v2 `@tool`s: 16 Citizen + 4 Manager-only `tools.deny` + 4 HITL).
- Show **Layered Memory:** `SqliteSaver` (`thread_id`) short-term + `PersistentSqliteStore` (`users/{id}/memories`) long-term + isolated per-user `user_chat_logs` + OpenClaw `MEMORY.md`.

### `8:30 – 10:00` — Data Pipeline, Jev Ingestion Gatekeeper, Qdrant Hybrid RAG & UMAP 2D
- Highlight the **live 2026 EMCALI news feed** (120+ live articles including Nov 26–27 maintenances + daily sync timer) filtered by our **Jev News-to-Map Gatekeeper (`Noul` veto)** so positive press releases never pollute the operational map.
- Show **Qdrant Hybrid Search** (HNSW Dense + BM25 RRF): `Recall@10 = 100.0%`, `nDCG@10 = 0.884`, enforced by CI regression gates (`tests/test_llmops_regressions.py`).
- Open the **Académico → UMAP y 20 Tools** section: explain why we chose **UMAP over t-SNE** (preserves global inter-cluster topology + supports `.transform()` to project live queries and PQRS/failure tickets onto the corpus manifold) + Silhouette Score.

### `10:00 – 12:00` — OpenClaw Gateway, Custom MCP Server & Security Hardening
- Show `openclaw/openclaw.template.json`: **DeepSeek cloud API** (zero Ollama), dedicated eSIM WhatsApp Business (`+57 323 892 3289`), `gateway.bind: loopback`, E.164 allowlist, `fs.workspaceOnly: true`, `tools.deny`, custom **`emcali-eder-mcp`** (`mcp==2.3.0`) server + `emcali-daily-newsletter` skill + `tts-local-cli` Colombian neural voice.
- Show **Indirect Prompt Injection Defense** (`<datos_pasivos_corpus solo_lectura="true">`), **HITL** approval queue, `docs/arquitectura.html` (**Archify** interactive map), `openclaw security audit` (0 critical), and `uv run pytest` (**65/65 tests passing**, **100/100 + 5 Bonus Archify Polanco Standard**).

---

## Block 3: Expert Q&A (`12:00 – 15:00`)
- **Rommel** owns: Azure deployment, OpenClaw/WhatsApp gateway, RBAC/Security, UMAP diagnostics, Code Review & CI/CD quality gates.
- **Jacobo** owns: M1 corpus & news pipeline, Qdrant hybrid RAG, Jev router, LangGraph memory, and citizen UX.
