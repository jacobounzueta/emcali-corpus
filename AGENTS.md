# AGENTS.md — Contexto para agentes LLM

Este repositorio captura el sitio público de EMCALI y produce un corpus Markdown
para RAG. Antes de cambiar código, lee `CONSTITUTION.md`.

## Comandos imprescindibles

```bash
uv sync                      # dependencias
uv run pytest                # pruebas (no requieren red)
uv run ruff check .          # lint
uv run ruff format --check . # formato
uv run ty check              # tipos
make check                   # todo lo anterior
uv run emcali-corpus status  # estado del corpus
uv run emcali-corpus reprocess  # reextraer gold/silver desde bronze, sin red
uv run emcali-corpus chunk      # consolidar knowledge_base.md y chunks.jsonl
uv run emcali-corpus ask "..."  # consultar el sistema Q&A con DeepSeek
uv run streamlit run src/emcali_corpus/app.py  # dashboard interactivo (Taller 1)
```

## Invariantes

1. **`uv` es el único gestor.** No uses `pip`, `requirements.txt` ni edites
   `uv.lock` a mano.
2. **La extracción no accede a la red.** `extracting.py` recibe HTML ya descargado.
3. **El *front matter* es la única fuente de metadatos.** No dupliques metadatos en
   el cuerpo.
4. **`data/gold/` es el contrato.** Los documentos viven en
   `data/gold/<sección>/<slug>.md`; usa `gold_path` del índice para localizarlos.
   Cambiar su forma es un cambio incompatible y debe documentarse en
   `CONSTITUTION.md`.
5. **Solo contenido público.** Nunca agregues semillas de login, dashboard, PQRS,
   pagos o formularios.
6. **Sé educado con el sitio.** Mantén el `User-Agent` identificable, el throttle y
   el respeto a `robots.txt`.

## Cómo funciona la captura

- `www.emcali.com.co` devuelve un envoltorio Liferay. Si el cuerpo es solo un
  `<iframe>` hacia `portalemcali.onrender.com`, `find_content_frame()` lo detecta y
  `BrowserRenderer` renderiza esa URL con Chromium.
- Las páginas `/w/...` sí traen el artículo en el HTML y se capturan sin navegador.
- `pipeline.capture_seed()` guarda bronze, extrae silver, escribe gold y actualiza
  `corpus.jsonl`. Si ya existen bronze y gold, omite la semilla salvo `--force`.

## Estilo

- Python 3.13, `snake_case`, `PascalCase`, docstrings en español.
- Ruff con `line-length = 100` y comillas dobles.
- Pruebas con `pytest` y patrón AAA.
- Identificadores en inglés; documentación y mensajes en español.

## Dónde tocar

| Necesidad | Archivo |
|-----------|---------|
| Añadir una página curada | `src/emcali_corpus/config.py` (`CURATED_SEEDS`) |
| Cambiar el alcance/exclusiones | `src/emcali_corpus/config.py` |
| Mejorar la conversión a Markdown | `src/emcali_corpus/extracting.py` |
| Cambiar el renderizado | `src/emcali_corpus/rendering.py` |
| Cambiar la orquestación | `src/emcali_corpus/pipeline.py` |
| Consolidación y chunking semántico | `src/emcali_corpus/knowledge.py` |
| Plantillas de Prompt Engineering | `src/emcali_corpus/prompts.py` |
| Agente y tareas LangChain + DeepSeek | `src/emcali_corpus/assistant.py` |
| Batería de 22 preguntas de prueba | `src/emcali_corpus/evaluation.py` |
| Dashboard interactivo en Streamlit | `src/emcali_corpus/app.py` |
| Cambiar la CLI | `src/emcali_corpus/cli.py` |

## Antes de terminar

1. Ejecuta `make check`.
2. Si cambió el comportamiento o la arquitectura, actualiza `CONSTITUTION.md` y el
   ADR correspondiente en `docs/adr/`.
3. No dejes archivos de `data/raw/` ni `data/processed/` en el commit.

## Búsqueda de código: `tgrep`

Si [`tgrep`](https://github.com/microsoft/tgrep) está instalado, úsalo para búsquedas de
código en lugar de `grep` o `find` (índice de trigramas en `.tgrep/`, ignorado por Git):

```bash
tgrep -- "patrón" .            # búsqueda regex (usa -- antes del patrón)
tgrep -F -- "simbolo" .        # coincidencia literal
tgrep -t py -- "def " .        # filtrar por tipo de archivo
tgrep -g "src/**" -- "kw" .    # filtrar por ruta
tgrep -l -- "import " .        # listar archivos coincidentes
tgrep index .                  # (re)indexar
```

En OpenCode la preferencia se aplica automáticamente mediante la regla
[`.opencode/rules/tgrep.md`](./.opencode/rules/tgrep.md).
