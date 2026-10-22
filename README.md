# EMCALI Corpus

Pipeline reproducible para convertir las páginas públicas de
[EMCALI](https://www.emcali.com.co/) en un corpus Markdown citable, con metadatos
y un índice JSONL listo para un sistema de recuperación aumentada (RAG).

> **Alcance:** información pública del sitio institucional. No se atraviesan
> formularios, sesiones autenticadas, trámites ni datos personales.

## ¿Qué hace?

1. Descarga la página de EMCALI (envoltorio Liferay) y la guarda en **bronze**.
2. Detecta si el contenido editorial vive en un iframe React y, en ese caso, lo
   renderiza con un navegador real.
3. Extrae el cuerpo editorial a Markdown limpio (**silver**), descartando menús,
   cabeceras, pies, botones decorativos y bloques de métricas.
4. Añade *front matter* YAML y actualiza `data/gold/corpus.jsonl` (**gold**).

```text
www.emcali.com.co  ──►  data/raw/        ──►  data/processed/  ──►  data/gold/
   (Liferay)             bronze (HTML)         silver (MD)          gold (MD + YAML)
                              │
                              └── iframe React ──► Playwright ──► HTML renderizado
```

## Inicio rápido

Requisitos: [uv](https://docs.astral.sh/uv/) y Python 3.13 (uv lo instala).

```bash
# 1. Dependencias
uv sync

# 2. Navegador para las páginas React (solo la primera vez)
uv run playwright install chromium

# 3. Capturar la portada y las páginas principales
uv run emcali-corpus capture

# 4. Ver el resultado
uv run emcali-corpus status
uv run emcali-corpus list
```

Con `make`:

```bash
make sync
make install-browsers
make capture
make status
```

## Estado del corpus

Última captura completa (2026-10-22):

| Métrica | Valor |
|---------|-------|
| Documentos | 478 |
| Palabras | 167.072 |
| Renderizados con navegador | 166 |
| Secciones | 24 |
| Errores | 0 |

El sitemap declara 587 URLs; tras aplicar las exclusiones de alcance quedan 570.
Las 92 restantes se omitieron por contenido insuficiente, diapositivas o rutas
obsoletas. Ejecuta `uv run emcali-corpus status` para ver el estado actual.

## Comandos

| Comando | Descripción |
|---------|-------------|
| `emcali-corpus capture` | Captura las 18 semillas curadas (portada, energía, acueducto, telco, sostenibilidad, ciudadanía, noticias y transparencia). |
| `emcali-corpus capture --all` | Recorre el sitemap completo y captura todas las URLs públicas. |
| `emcali-corpus capture --all --no-news` | Igual, pero sin las noticias bajo `/w/`. |
| `emcali-corpus capture --force` | Ignora la caché de bronze y vuelve a descargar/renderizar. |
| `emcali-corpus capture --url URL` | Captura una URL concreta (repetible). |
| `emcali-corpus discover` | Lista las semillas descubiertas en el sitemap. |
| `emcali-corpus index` | Reconstruye `corpus.jsonl` desde los documentos gold. |
| `emcali-corpus reprocess` | Reextrae gold y silver desde bronze, sin volver a la red. |
| `emcali-corpus status` | Muestra documentos, palabras, secciones y errores. |
| `emcali-corpus list` | Lista los documentos indexados. |

`capture` es idempotente: si ya existen bronze y gold de una semilla, la omite
salvo que se use `--force`. Los errores se registran en `data/errors.jsonl` y no
interrumpen la ejecución.

## Estructura de datos

```text
data/
├── raw/            # bronze: HTML del envoltorio y del iframe renderizado
├── processed/      # silver: Markdown sin metadatos
├── gold/           # gold: Markdown + front matter (versionado)
│   ├── inicio/
│   │   └── portada.md
│   ├── energia/
│   │   └── tarifas-de-energia.md
│   └── corpus.jsonl
└── errors.jsonl    # incidencias de captura (no versionado)
```

El *slug* de cada página se deriva de su ruta, por lo que dos secciones distintas
pueden compartir nombre (por ejemplo `telco/indicadores-pqr` e
`indicadores-pqr`). Por eso gold y silver se organizan en subcarpetas por sección:
`data/gold/<sección>/<slug>.md`.

Cada documento gold luce así:

```markdown
---
title: "Tarifas de Energía"
slug: "tarifas-de-energia"
section: "energia"
source_url: "https://www.emcali.com.co/energia/tarifas-de-energia"
canonical_url: "https://www.emcali.com.co/energia/tarifas-de-energia"
description: "En EMCALI trabajamos para ofrecerte precios justos..."
captured_at: "2026-10-22T19:32:01+00:00"
render: "browser"
http_status: 200
language: "es"
content_sha256: "3d3b29c1..."
word_count: 79
iframe_url: "https://portalemcali.onrender.com/energia/ratesEnergy"
---

# Tarifas de Energía

...
```

## Arquitectura

| Módulo | Responsabilidad |
|--------|-----------------|
| `config.py` | Semillas curadas, rutas de las capas, política HTTP y hosts de renderizado. |
| `fetching.py` | Cliente `requests` con throttle, reintentos, decodificación y `robots.txt`. |
| `rendering.py` | Playwright reutilizable, con detección de Chromium y bloqueo de imágenes/fuentes. |
| `extracting.py` | Detección de iframes y conversor DOM → Markdown. |
| `discovery.py` | Lectura del `sitemap.xml` y generación de semillas. |
| `gold.py` | Front matter, índice JSONL y reconstrucción del catálogo. |
| `pipeline.py` | Orquestación de las tres capas y registro de errores. |
| `cli.py` | Interfaz `capture`, `discover`, `index`, `reprocess`, `status` y `list`. |

### Por qué Playwright

La portada y las páginas internas de `www.emcali.com.co` son envoltorios Liferay
que incrustan una aplicación React alojada en `portalemcali.onrender.com`. El HTML
servido por HTTP contiene poco más que un `<iframe>`; el texto solo existe después
de ejecutar JavaScript. El pipeline detecta el iframe, valida que pertenezca a un
host de confianza y renderiza esa URL con Chromium. Cuando la página sí trae
contenido en el HTML (por ejemplo las noticias `/w/...`), no se usa navegador.

## Desarrollo

```bash
make check       # Ruff + formato + ty + pytest
make pre-commit  # hooks sobre todo el repositorio
make index       # reconstruir el índice gold
make reprocess   # reextraer desde bronze sin red
```

- Gestión de dependencias exclusivamente con `uv` (sin `pip` ni `requirements.txt`).
- Python 3.13, `src-layout`, paquete `emcali_corpus`.
- Pruebas sin red: la extracción recibe HTML ya descargado.

## Ética y legalidad

- `robots.txt` permite el acceso; el cliente lo verifica antes de cada semilla.
- `User-Agent` identificable y una petición cada 0,75 s como mínimo.
- Solo contenido público; quedan fuera login, dashboard, PQRS, pagos y datos
  personales.
- El corpus conserva la URL de origen para poder citar y verificar cada fragmento.

## Licencia

MIT. Consulta [LICENSE](LICENSE).
