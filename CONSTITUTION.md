# CONSTITUTION — EMCALI Corpus

> **Verdad central del proyecto.** Este documento define el propósito, el stack, la
> estructura, las convenciones y el flujo de trabajo de `EMCALI Corpus`. Si algo aquí
> contradice al código, el código manda **y este archivo se actualiza**.

> ⚠️ **Directiva de mantenimiento:** cada vez que se realicen cambios significativos
> (nuevas funcionalidades, cambios arquitectónicos, adición de clases/módulos o ajustes
> de tecnologías), **se debe actualizar este archivo en el mismo commit** para mantener
> la verdad central del proyecto bien documentada.

---

## 0. Identidad del proyecto

| Campo | Valor |
|-------|-------|
| **Nombre** | EMCALI Corpus |
| **Descripción** | Pipeline de captura y curaduría del sitio web público de EMCALI, consolidación semántica y sistema Q&A para RAG. |
| **Repositorio** | [`https://github.com/jacobounzueta/emcali-corpus`](https://github.com/jacobounzueta/emcali-corpus) |
| **Autoría** | Jacobo Unzueta — jacobo.unzueta@uao.edu.co · Rommel Prieto — rommel.prieto@uao.edu.co |
| **Licencia** | MIT |
| **Rama principal** | `main` |
| **Estado** | Operativo 🟢 |

## 1. Propósito y no-propósito

### Propósito

Convertir las páginas públicas de EMCALI en un corpus Markdown citable, reproducible
y listo para un pipeline de RAG, respetando `robots.txt` y sin depender de una API
del sitio, integrando su consolidación semántica, segmentación (*chunking*) y un
asistente Q&A/Resumen/FAQ con atribución verificable de fuentes.

### No-propósito

No es un *crawler* masivo de Internet, ni un motor de búsqueda, ni un sistema que
atraviese formularios, sesiones autenticadas, trámites o datos personales.

## 2. Alcance

### Dentro del alcance

- Capturar la portada de `www.emcali.com.co` y las páginas de contenido que de ella
  dependen: servicios (energía, acueducto y alcantarillado, telco), sostenibilidad,
  atención a la ciudadanía, noticias, transparencia e información institucional.
- Mantener tres capas: **bronze** (HTML crudo), **silver** (Markdown limpio) y
  **gold** (Markdown + *front matter* + índice JSONL).
- Resolver los envoltorios Liferay que incrustan la aplicación React de EMCALI.
- Extraer el cuerpo editorial descartando menús, formularios, modales, pies y
  bloques de métricas.
- Versionar `data/gold/` como entregable del corpus.
- Reprocesar gold y silver desde bronze sin volver a la web.
- Consolidar la base de conocimiento institucional deduplicada por `content_sha256`
  (`data/knowledge_base.md`) y segmentarla en *chunks* semánticos (`data/chunks.jsonl`).
- Orquestar con LangChain y DeepSeek (`deepseek-flash`) las tareas de Q&A citado,
  Resumen Ejecutivo, Generación de FAQ y evaluación sobre 22 preguntas (`docs/evaluacion_preguntas.md`).
- Ofrecer una CLI, un Makefile y un dashboard en Streamlit (`app.py`) como interfaces del proyecto.

### Fuera del alcance (por ahora)

- Rutas transaccionales o privadas: login, registro, dashboard, PQRS, pagos,
  consulta de facturas y actualización de datos prediales.
- Formularios externos incrustados (por ejemplo el formulario de clausura de
  servicios tras el sismo).
- PDFs, imágenes, vídeos y transcripciones.
- Indexación en base de datos vectorial (proyectada para el Módulo 2).

### Fases

| Fase | Estado | Entregable |
|------|--------|------------|
| 1. Captura de la portada | ✅ Hecha | `data/gold/portada/inicio.md` |
| 2. Páginas de contenido principales | ✅ Hecha | 18 documentos curados + `corpus.jsonl` |
| 3. Cobertura del sitemap | ✅ Hecha | `capture --all` sobre 570 URLs públicas: 478 documentos |
| 4. Enriquecimiento (PDFs, vídeo) | ⬜ Pendiente | Nuevas semillas y extractores |
| 5. Consolidación, Chunking y Sistema Q&A (Taller 1) | ✅ Hecha | `knowledge.py`, `prompts.py`, `assistant.py`, `evaluation.py`, `app.py` y `docs/informe-taller-1.md` |

### Estado del corpus (2026-10-22)

| Métrica | Valor |
|---------|-------|
| Documentos gold | 478 |
| Palabras | 167.072 |
| Documentos renderizados con navegador | 166 |
| Secciones | 24 |
| URLs en alcance descubiertas | 570 |
| Errores de captura | 0 |

Las 92 URLs restantes se omitieron por contenido insuficiente, páginas de diapositivas
o rutas obsoletas del sitemap. La captura es idempotente: `capture --all` reanuda sin
volver a descargar lo ya capturado.

## 3. Stack técnico

| Categoría | Tecnología |
|-----------|------------|
| **Lenguaje** | Python 3.13+ |
| **Gestor de paquetes y entorno** | [`uv`](https://docs.astral.sh/uv/) |
| **Build backend** | `uv_build` (src-layout) |
| **Paquete Python** | `emcali_corpus` |
| **HTTP** | `requests` (sesión única, `User-Agent` identificable, `timeout`, throttle) |
| **Parseo HTML** | `beautifulsoup4` + `lxml` |
| **Renderizado JS** | [`playwright`](https://playwright.dev/python/) + Chromium |
| **Orquestación LLM y Chunking** | `langchain`, `langchain-deepseek` (`deepseek-flash`), `langchain-text-splitters` |
| **Interfaz de Prueba (Taller 1)** | `streamlit` (`src/emcali_corpus/app.py`) |
| **Tipado estático** | [`ty`](https://github.com/astral-sh/ty) |
| **Testing** | [`pytest`](https://docs.pytest.org/) |
| **Linting / Formato** | [Ruff](https://docs.astral.sh/ruff/) |
| **Pre-commit** | [pre-commit](https://pre-commit.com) |
| **CI/CD** | [GitHub Actions](.github/workflows/ci.yml) |
| **Dependencias automáticas** | [Dependabot](.github/dependabot.yml) |

> ⚠️ **Regla dura:** toda gestión de dependencias y entornos pasa por `uv`. Está
> **prohibido** `pip` y `requirements.txt`.

> 📝 **Decisión sobre `trafilatura`:** se evaluó y se descartó como extractor
> principal. Es excelente con artículos de prensa, pero descarta las tarjetas y los
> acordeones de las *landings* institucionales —justo el contenido que el RAG
> necesita—. El extractor propio recorre el DOM y conserva encabezados, listas,
> tablas y enlaces.

> 📝 **Decisión sobre Playwright:** el HTML de `www.emcali.com.co` es un envoltorio
> Liferay con un `<iframe>` hacia `portalemcali.onrender.com`. Sin ejecutar
> JavaScript no hay texto. Playwright se usa **solo** cuando se detecta ese iframe;
> el resto de páginas se captura con HTTP simple.

## 4. Estructura del repositorio

```text
emcali-corpus/
├── app.py                   # punto de entrada raíz para Streamlit
├── src/emcali_corpus/       # código del paquete (src-layout)
│   ├── config.py            # semillas, capas, política HTTP, hosts de renderizado
│   ├── fetching.py          # cliente HTTP educado y robots.txt
│   ├── rendering.py         # Playwright + Chromium
│   ├── extracting.py        # detección de iframes y HTML → Markdown
│   ├── discovery.py         # sitemap.xml → semillas
│   ├── gold.py              # front matter + índice JSONL
│   ├── pipeline.py          # orquestación de las tres capas
│   ├── knowledge.py         # deduplicación SHA-256, métricas de embudo y chunking
│   ├── prompts.py           # estrategias de Prompt Engineering (Q&A, Resumen, FAQ)
│   ├── assistant.py         # orquestación LangChain + DeepSeek (deepseek-flash)
│   ├── evaluation.py        # batería de 22 preguntas de prueba y evaluación
│   ├── app.py               # dashboard interactivo en Streamlit (5 pestañas)
│   ├── models.py            # modelos del dominio
│   ├── cli.py               # capture / discover / index / reprocess / status / list / chunk / ask / summarize / faq / evaluate
│   └── __main__.py          # python -m emcali_corpus
├── data/                    # capas Medallion (raw y processed ignoradas)
│   ├── raw/                 # bronze — HTML crudo por sección
│   ├── processed/           # silver — Markdown limpio por sección
│   └── gold/                # gold — entregable versionado por sección
│       ├── <sección>/
│       │   └── <slug>.md
│       └── corpus.jsonl     # índice con rutas completas
├── tests/                   # pruebas (pytest, patrón AAA)
├── docs/                    # ADRs, informe-taller-1.md y evaluacion_preguntas.md
├── .github/                 # gobernanza (PR/issue templates, CI, Dependabot)
├── AGENTS.md                # contexto para agentes LLM
├── CONSTITUTION.md          # este archivo — verdad central
├── README.md                # puerta de entrada pública
├── CONTRIBUTING.md          # guía de contribución
├── CODE_OF_CONDUCT.md       # código de conducta
├── LICENSE                  # licencia MIT
├── Makefile                 # automatización de tareas
├── pyproject.toml           # metadatos y dependencias (uv)
├── uv.lock                  # lockfile determinista (versionado)
├── .python-version          # versión de Python fijada
└── .pre-commit-config.yaml  # hooks de calidad
```

## 5. Convenciones de código

- **Estilo:** [PEP 8](https://peps.python.org/pep-0008/) y [PEP 257](https://peps.python.org/pep-0257/),
  impuesto por **Ruff** (`line-length = 100`, comillas dobles).
- **Tipado:** anotaciones en funciones y firmas públicas.
- **Nomenclatura:** `snake_case` (funciones/variables), `PascalCase` (clases),
  `UPPER_CASE` (constantes).
- **Docstrings:** en módulos, clases y funciones públicas.
- **Pruebas:** `pytest` con el patrón **AAA** (*Arrange · Act · Assert*).
- **Idioma:** UI, documentación y commits en español; identificadores de código en inglés.
- **Reglas propias:**
  - La extracción **nunca** depende de la red: `extracting` recibe HTML ya descargado.
  - El *front matter* es la única fuente de metadatos; no se duplica en el cuerpo.
  - El cuerpo Markdown solo conserva contenido editorial: sin menús, pies, botones
    decorativos, imágenes ni contadores de visitas.
  - `data/gold/` es el contrato con el proyecto consumidor: cambiarlo es un cambio
    incompatible y se documenta en esta constitución.

## 6. Calidad y automatización

| Herramienta | Rol | Comando |
|-------------|-----|---------|
| `uv` | Entornos y dependencias | `uv sync` |
| Ruff | Lint + formato | `make lint` / `make format` |
| `ty` | Verificación de tipos | `make typecheck` |
| `pytest` | Pruebas | `make test` |
| `pre-commit` | Hooks antes de cada commit | `make pre-commit` |
| GitHub Actions | CI (pre-commit + ty + pytest) | `.github/workflows/ci.yml` |

- Ningún commit se salta los hooks (`--no-verify` está prohibido salvo causa justificada y documentada).
- La **CI debe estar en verde** antes de fusionar un Pull Request.
- Toda dependencia nueva entra con `uv add` / `uv add --dev` (nunca editando `uv.lock` a mano).

## 7. Repositorio y Git

- **Rama principal:** `main`
- **Estrategia de ramas:** `feat/...`, `fix/...`, `docs/...`, `refactor/...`, `test/...`, `chore/...`; integración vía Pull Request.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) —
  `feat:`, `fix:`, `docs:`, `refactor:`, `style:`, `test:`, `chore:`.
- **Datos:** se versiona `data/gold/`; `data/raw/`, `data/processed/` y
  `data/errors.jsonl` son reproducibles y quedan fuera de Git.

## 8. Flujo diario (commit + push)

```bash
# 1. Ver cambios
git status

# 2. Verificación completa (lint + formato + tipos + pruebas)
make check

# 3. Agregar y commitear (los hooks se ejecutan solos)
git add -A
git commit -m "tipo: mensaje descriptivo"

# 4. Subir a GitHub
git push
```

## 9. Historial de decisiones técnicas

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-10-22 | Adoptar `uv` como gestor único de entornos y dependencias | Reproducibilidad; prohibido `pip`/`requirements.txt` |
| 2026-10-22 | Adoptar Ruff (lint + formato), ty y pre-commit | Calidad automatizada antes de cada commit |
| 2026-10-22 | Adoptar Conventional Commits | Historial legible y automatizable |
| 2026-10-22 | Adoptar licencia MIT y `CONSTITUTION.md` como fuente única de verdad | Claridad legal y operativa |
| 2026-10-22 | Patrón Medallion (bronze/silver/gold) con `data/gold/` versionado | Permite reprocesar sin volver a la web; el entregable queda en Git |
| 2026-10-22 | Descartar `trafilatura` como extractor principal | Pierde tarjetas y acordeones de las *landings* institucionales |
| 2026-10-22 | Extractor propio basado en DOM | Control explícito de qué es contenido y qué es *chrome* |
| 2026-10-22 | Renderizar con Playwright solo los iframes de `portalemcali.onrender.com` | El sitio es Liferay + React; sin JS no hay contenido |
| 2026-10-22 | Resolver las semillas desde `sitemap.xml` | Cobertura completa sin rastrear enlaces de navegación |
| 2026-10-22 | Excluir imágenes del Markdown | El corpus es textual; las URLs quedan registradas en el modelo |
| 2026-10-22 | Excluir login, dashboard, PQRS, pagos y formularios | Evitar trámites, sesiones y datos personales |
| 2026-10-22 | Organizar gold y silver en `<sección>/<slug>.md` (ADR 0006) | Evitar colisiones de *slug* entre secciones al cubrir todo el sitemap |
| 2026-10-22 | Ignorar sitemaps vacíos o mal formados y sufijar colisiones con SHA-256 | El sitemap responde esporádicamente vacío; el sufijo debe ser estable entre ejecuciones |
| 2026-10-22 | Esperar `domcontentloaded` + hidratación de `#root` en lugar de `networkidle` | El portal nunca alcanza `networkidle`; cada página tardaba 60 s y la captura completa era inviable |
| 2026-10-22 | Añadir `reprocess` para reextraer desde bronze | Permite mejorar el extractor sin volver a descargar el sitio |
| 2026-10-29 | Integrar consolidación, chunking semántico, LangChain + DeepSeek (`deepseek-flash`) y Streamlit (ADR 0007) | Entregar en un único repositorio el Taller 1 completo (scraping, base de conocimiento, Q&A/Resumen/FAQ, interfaz y pruebas) |

## 10. Notas y tareas pendientes

- [x] Publicar el repositorio y fijar la URL remota en esta constitución (`https://github.com/jacobounzueta/emcali-corpus`).
- [x] Definir el contrato de *chunking* semántico (`data/chunks.jsonl`) y el informe de evaluación (`docs/evaluacion_preguntas.md`).
- [ ] Añadir extracción de PDFs (informes, tarifas y documentos de transparencia).
- [ ] Añadir transcripciones de vídeo (`yt-dlp` / `youtube-transcript-api`).
- [ ] Enriquecer el *front matter* con entidades, dependencias y categorías.
- [ ] Evaluar *deduplicación* de *boilerplate* entre documentos por hash de bloque.

## 11. Configuración local (no trackear)

Variables de entorno opcionales:

| Variable | Efecto |
|----------|--------|
| `EMCALI_DATA_DIR` | Cambia el directorio de datos (por defecto `./data`). |
| `EMCALI_CHROMIUM_PATH` | Ruta explícita al binario de Chromium. |

Sin `EMCALI_CHROMIUM_PATH`, el renderizador prueba el Chromium instalado por
Playwright y, si no existe, los canales del sistema (`msedge`, `chrome`) y la caché
local de Playwright.

> No se versionan credenciales, rutas personales ni configuración específica de la
> máquina. El proyecto no necesita secretos: solo accede a información pública.

## 12. Gobierno de este documento

- **Regla de sincronización:** cualquier cambio arquitectónico, tecnológico, de modelo de
  datos o de proceso debe reflejarse en `CONSTITUTION.md` en el **mismo Pull Request** (y
  documentarse mediante un ADR en `docs/adr/` cuando la decisión tenga alternativas no
  triviales).
- **Precedencia:** ante cualquier contradicción entre `README.md`, `AGENTS.md` o
  comentarios en código, prevalece lo establecido en este documento.
- **Revisión en PR:** la plantilla de Pull Request incluye la verificación explícita de que
  `CONSTITUTION.md` permanece alineado con el estado real del sistema.
