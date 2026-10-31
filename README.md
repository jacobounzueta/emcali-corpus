# ⚡ EMCALI Corpus — Núcleo de Conocimiento Semántico y Sistema Q&A

[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/jacobounzueta/emcali-corpus/actions/workflows/ci.yml/badge.svg)](https://github.com/jacobounzueta/emcali-corpus/actions/workflows/ci.yml)
[![uv](https://img.shields.io/badge/uv-package_manager-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/Ruff-lint_%26_format-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![ty](https://img.shields.io/badge/ty-type_checked-2B5B84)](https://github.com/astral-sh/ty)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=precommit&logoColor=white)](./.pre-commit-config.yaml)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-fe5196.svg)](https://conventionalcommits.org)
[![pytest](https://img.shields.io/badge/pytest-38_passed-0A9EDC?logo=pytest&logoColor=white)](tests/)
[![LangChain](https://img.shields.io/badge/LangChain-1.4-1C3C3C?logo=langchain&logoColor=white)](https://python.langchain.com/)
[![DeepSeek V4.1 Flash](https://img.shields.io/badge/LLM-DeepSeek_V4.1_Flash-4D6BFE)](https://platform.deepseek.com/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](app.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Pipeline reproducible de *web scraping* con arquitectura **Medallion (Bronze → Silver → Gold)**, consolidación de base de conocimiento semántico y asistente **Q&A con atribución de fuentes** para las **Empresas Municipales de Cali — [EMCALI E.I.C.E. E.S.P.](https://www.emcali.com.co/)**.

---

## 🎯 Problema y Solución

La información pública de **EMCALI E.I.C.E. E.S.P.** (servicios de energía, acueducto, alcantarillado, telecomunicaciones, trámites, sedes, tarifas y transparencia) se encuentra dispersa en cientos de páginas sobre un portal **Liferay DXP** que incrusta aplicaciones **React** externas (`portalemcali.onrender.com`), dificultando su consulta directa por ciudadanos o modelos de lenguaje debido al ruido estructural HTML y al renderizado dinámico en cliente.

**Nuestra solución** construye un pipeline determinista e idempotente que descubre el sitio desde `sitemap.xml` respetando `robots.txt`, extrae tanto el HTML estático como los iframes React mediante **Playwright**, limpia y deduplica el contenido por hash `SHA-256` en formato Markdown con *frontmatter* YAML e índices JSONL, y lo conecta a un sistema **Q&A, Resumen Ejecutivo y Generador de FAQ** orquestado con **LangChain** y **DeepSeek V4.1 Flash (`deepseek-flash`)** en **Streamlit** que responde citando siempre la sección y URL oficial.

> **Alcance ético y legal:** únicamente información pública del sitio institucional (`www.emcali.com.co`). No se atraviesan formularios, sesiones autenticadas, pasarelas de pago ni datos personales.

---

## 🏗️ Arquitectura del Pipeline (5 Etapas: Bronze → Silver → Gold → LLM)

1. **Descubrir (`discovery.py`):** Lee `sitemap.xml` (`587` URLs), verifica `robots.txt` y filtra rutas fuera de alcance (`570` semillas válidas; `17` excluidas como logins o pagos).
2. **Extraer (`fetching.py` + `rendering.py` → Capa Bronze):** Descarga el envoltorio Liferay en `data/raw/` con *rate limit* (`0.75 s`), *timeout* (`25 s`) y 3 reintentos. Si detecta un iframe React autorizado (`portalemcali.onrender.com`), lo renderiza con Chromium en Playwright (`166` páginas por navegador + `312` por HTTP directo).
3. **Limpiar (`extracting.py` → Capa Silver):** Aísla `#main-content`, elimina menús globales, cabeceras, pies de página, scripts y plantillas vacías (`92` descartes por contenido `< 15` palabras o `404`), y convierte el DOM editorial a Markdown limpio en `data/processed/` (`478` documentos válidos).
4. **Deduplicar (`knowledge.py`):** Separa notas de prensa (`310` noticias bajo `/w/`) del núcleo institucional (`168` páginas) y elimina duplicados exactos mediante huella `content_sha256`, consolidando **`164` documentos institucionales únicos** (`54.625` palabras · `~72.651` tokens estimados).
5. **Enriquecer y Orquestar (`gold.py` + `knowledge.py` + `assistant.py` → Capa Gold + RAG):** Añade *frontmatter* YAML en `data/gold/<sección>/<slug>.md`, actualiza `data/gold/corpus.jsonl`, consolida `data/knowledge_base.md`, segmenta **`1.385` fragmentos semánticos** en `data/chunks.jsonl` (`MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter`) y alimenta el sistema Q&A en **Streamlit** (`app.py`).

```text
www.emcali.com.co ──► 1. Descubrir (sitemap.xml: 587 → 570 URLs en alcance)
                         │
                         ▼
                  2. Extraer ──► data/raw/ (Bronze: HTML Liferay + Iframe React con Playwright)
                         │
                         ▼
                  3. Limpiar ──► data/processed/ (Silver: 478 docs Markdown · 92 descartes)
                         │
                         ▼
               4. Deduplicar ──► SHA-256: 164 docs institucionales únicos (54.625 palabras)
                         │
                         ▼
               5. Enriquecer ──► data/gold/ (MD + YAML + corpus.jsonl)
                                 ├── data/knowledge_base.md (~72.651 tokens)
                                 ├── data/chunks.jsonl (1.385 chunks semánticos)
                                 └── LangChain + DeepSeek V4.1 Flash ──► Streamlit UI (app.py)
```

---

## 🚀 Instalación y Ejecución Rápida (`uv`)

Requisitos: [uv](https://docs.astral.sh/uv/) y Python 3.13 (`uv` lo instala automáticamente).

```bash
# 1. Clonar el repositorio e instalar dependencias desde uv.lock
git clone https://github.com/jacobounzueta/emcali-corpus.git
cd emcali-corpus
uv sync

# 2. Configurar la clave de API de DeepSeek para el sistema Q&A
cp .env.example .env   # o crea .env con: DEEPSEEK_API_KEY=sk-...

# 3. (Opcional) Instalar Chromium si deseas re-ejecutar el scraping desde la red
uv run playwright install chromium

# 4. Verificar el estado del corpus Gold y generar la base consolidada + chunks
uv run emcali-corpus status
uv run emcali-corpus chunk

# 5. Lanzar la interfaz interactiva en Streamlit
uv run streamlit run app.py
```

También puedes usar los atajos del [`Makefile`](Makefile):

```bash
make sync      # uv sync
make status    # Estado del corpus Medallion
make chunk     # Consolida data/knowledge_base.md y data/chunks.jsonl
make app       # Lanza Streamlit (uv run streamlit run app.py)
make check     # Ejecuta Ruff lint + Ruff format + ty + pytest
```

---

## 📊 Métricas del Corpus (Embudo de Captura y Curaduría)

| Etapa / Métrica | Valor | Detalle verificable |
| :--- | :---: | :--- |
| **1. URLs en `sitemap.xml`** | `587` | Total publicado por el portal de EMCALI |
| **URLs en alcance** | `570` | `-17` excluidas por reglas éticas/alcance (logins, pagos, formularios) |
| **2. Capturas válidas (Gold total)** | `478` | `166` renderizadas con Playwright (iframes React) + `312` por HTTP |
| **3. Descartes en limpieza** | `92` | Plantillas Liferay sin cuerpo editorial (`< 15` palabras) o páginas `404` |
| **4. Documentos institucionales únicos** | `164` | Deduplicados por `content_sha256` (`-4` duplicados exactos; `310` noticias `/w/` separadas) |
| **Palabras (Total / Institucional)** | `167.072` / `54.625` | Texto limpio en español sin ruido HTML |
| **Tokens estimados (Total / Institucional)** | `~222.206` / `~72.651` | Estimación conservadora (`~1,33` tokens/palabra) |
| **5. Chunks semánticos (`data/chunks.jsonl`)** | `1.385` | `chunk_size=1200`, `chunk_overlap=200` respetando jerarquía `# / ## / ###` |
| **Secciones cubiertas / Errores fatales** | `24` / `0` | Cobertura completa de servicios, trámites, sedes y transparencia |

---

## 💻 Comandos de la CLI (`emcali-corpus`)

| Comando | Descripción |
| :--- | :--- |
| `uv run emcali-corpus capture` | Captura las 18 semillas curadas (portada, energía, acueducto, telco, sostenibilidad, ciudadanía, noticias y transparencia). |
| `uv run emcali-corpus capture --all` | Recorre el `sitemap.xml` completo y captura todas las URLs públicas. |
| `uv run emcali-corpus capture --all --no-news` | Captura todas las páginas institucionales omitiendo noticias bajo `/w/`. |
| `uv run emcali-corpus discover` | Lista las semillas descubiertas en el `sitemap.xml`. |
| `uv run emcali-corpus index` | Reconstruye `data/gold/corpus.jsonl` desde los documentos Gold. |
| `uv run emcali-corpus reprocess` | Reextrae Gold y Silver desde Bronze sin volver a la red. |
| `uv run emcali-corpus status` | Muestra documentos, palabras, secciones, renderizados y errores. |
| `uv run emcali-corpus chunk` | Consolida `data/knowledge_base.md` y genera los fragmentos en `data/chunks.jsonl`. |
| `uv run emcali-corpus ask "<pregunta>"` | Responde una pregunta con LangChain + DeepSeek (`deepseek-flash`) citando fuentes. |
| `uv run emcali-corpus summarize` | Genera un Resumen Ejecutivo estructurado del corpus institucional. |
| `uv run emcali-corpus faq` | Genera un catálogo de Preguntas Frecuentes (FAQ) con enlaces oficiales. |
| `uv run emcali-corpus evaluate` | Ejecuta la batería de 22 preguntas de prueba y genera `docs/evaluacion_preguntas.md`. |

---

## 🗂️ Estructura del Proyecto

```text
emcali-corpus/
├── app.py                          # Punto de entrada raíz para Streamlit (`uv run streamlit run app.py`)
├── pyproject.toml                  # Configuración del paquete, dependencias y herramientas (Ruff, ty, pytest)
├── uv.lock                         # Lockfile determinista de uv
├── Makefile                        # Automatización de captura, chunking, UI y verificaciones de calidad
├── AGENTS.md                       # Guía operativa para agentes de IA y desarrolladores
├── CONSTITUTION.md                 # Principios innegociables del proyecto y gobernanza técnica
├── data/
│   ├── raw/                        # Capa Bronze: HTML crudo Liferay + DOM renderizado (no versionado)
│   ├── processed/                  # Capa Silver: Markdown limpio sin metadatos (no versionado)
│   ├── gold/                       # Capa Gold: 478 documentos Markdown + frontmatter YAML + corpus.jsonl
│   ├── knowledge_base.md           # Base de conocimiento institucional consolidada (164 docs · 54.625 palabras)
│   └── chunks.jsonl                # 1.385 fragmentos semánticos con metadatos de trazabilidad
├── docs/
│   ├── adr/                        # 7 Architecture Decision Records (ADR-0001 a ADR-0007)
│   └── informe-taller-1.md         # Informe técnico completo del Taller 1 (Módulo 1)
├── src/emcali_corpus/
│   ├── config.py                   # Semillas, límites de tasa, User-Agent y rutas Medallion
│   ├── discovery.py                # Descubrimiento de URLs vía sitemap.xml
│   ├── fetching.py                 # Cliente HTTP con verificación de robots.txt, reintentos y throttle
│   ├── rendering.py                # Renderizador Playwright Chromium para iframes React
│   ├── extracting.py               # Limpieza DOM y conversión determinista HTML → Markdown
│   ├── gold.py                     # Serialización de frontmatter YAML e índice JSONL
│   ├── pipeline.py                 # Orquestador de las capas Bronze, Silver y Gold
│   ├── knowledge.py                # Deduplicación SHA-256, métricas de embudo, inspector Medallion y chunking
│   ├── prompts.py                  # 3 estrategias de Prompt Engineering + plantillas de Resumen y FAQ
│   ├── assistant.py                # Orquestación LangChain 1.4 (`create_agent` + `ChatDeepSeek`)
│   ├── evaluation.py               # Batería de 22 preguntas (incluyendo control anti-alucinación)
│   ├── app.py                      # Interfaz interactiva en Streamlit (5 pestañas)
│   └── cli.py                      # Interfaz de línea de comandos (`emcali-corpus`)
└── tests/                          # Suite de 38 pruebas unitarias deterministas (sin red)
```

---

## 🖼️ Vista del Dashboard en Streamlit (`app.py`)

La aplicación interactiva (`uv run streamlit run app.py`) organiza la demostración en **5 pestañas**:

1. **💬 Chat Q&A (con Citas):** Asistente conversacional en *streaming* con selector de alcance (`164` docs institucionales o `18` semillas curadas), selector de estrategia de *Prompt Engineering* y citas verificables `[Sección / URL]`.
2. **🏗️ Pipeline Scraping (Bronze → Silver → Gold):** Embudo visual de las **5 etapas** (`Descubrir → Extraer → Limpiar → Deduplicar → Enriquecer`), inspector comparativo lado a lado (**Bronze HTML → Silver Markdown → Gold Frontmatter YAML → JSONL**) y explorador de los **`1.385` chunks**.
3. **📑 Resumen Ejecutivo:** Síntesis estructurada global o por área operativa generada con LangChain.
4. **❓ Generador de FAQ:** Construcción automática de preguntas frecuentes orientadas al ciudadano con enlaces oficiales.
5. **🧪 Evaluación (22 Preguntas) y Prompts:** Laboratorio comparativo de las 3 estrategias de *prompting* y ejecución en vivo del benchmark de 22 preguntas.

---

## ⚖️ Ética, Legalidad y Calidad de Código

* **Respeto a `robots.txt` y `sitemap.xml`:** El cliente HTTP valida las reglas del sitio antes de cada captura.
* **Identificación y *Rate Limiting*:** `User-Agent` explícito (`emcali-corpus/0.1 (+https://www.emcali.com.co; educational research)`) y pausa mínima de `0,75 s` entre solicitudes con backoff exponencial.
* **Cero datos privados:** Se excluyen explícitamente rutas de autenticación, pagos y trámites personales (`/login`, `/dashboard`, `/registro`, `/formulario`).
* **Verificación estática y pruebas:** `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check` y `uv run pytest` pasan al 100 %.

---

## 👥 Créditos y Roles del Equipo (Grupo 5)

Proyecto desarrollado para la asignatura **Técnicas Avanzadas de IA Aplicadas en Modelos de Lenguaje (2026-2S)** — **Universidad Autónoma de Occidente (UAO)**:

| Integrante | Correo Institucional | Rol en el Proyecto |
| :--- | :--- | :--- |
| **Jacobo Unzueta** | `jacobo.unzueta@uao.edu.co` | **Ingeniería de Datos y Pipeline de Scraping:** Diseño de la arquitectura Medallion (Bronze → Silver → Gold), descubrimiento por `sitemap.xml`, renderizado de iframes React con Playwright, extracción DOM → Markdown y catálogo JSONL. |
| **Rommel Prieto** | `rommel.prieto@uao.edu.co` | **Ingeniería de LLMs, Prompt Engineering e Interfaz:** Consolidación semántica y *chunking*, diseño de estrategias de *Prompt Engineering*, orquestación con LangChain + DeepSeek V4.1 Flash (`deepseek-flash`), evaluación sobre 22 preguntas e interfaz en Streamlit. |

Consulta también [AUTHORS.md](AUTHORS.md) y el informe técnico en [`docs/informe-taller-1.md`](docs/informe-taller-1.md).

---

## 📄 Licencia

Distribuido bajo la licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para el texto completo.
