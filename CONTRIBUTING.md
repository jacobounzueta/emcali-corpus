# Contribuir a EMCALI Corpus

Gracias por tu interés. Este proyecto captura información pública y debe seguir
siendo reproducible, citable y respetuoso con el sitio de origen.

## Entorno

```bash
uv sync
uv run playwright install chromium   # solo para páginas React
uv run pytest
```

No uses `pip` ni `requirements.txt`. Las dependencias se gestionan con `uv add` o
`uv add --dev`.

## Flujo

1. Crea una rama: `feat/...`, `fix/...`, `docs/...`, `refactor/...`, `test/...` o
   `chore/...`.
2. Haz cambios pequeños y enfocados.
3. Ejecuta `make check`.
4. Actualiza `CONSTITUTION.md` y los ADR si cambió la arquitectura o el contrato de
   `data/gold/`.
5. Abre un Pull Request describiendo el cambio y cómo lo verificaste.

## Commits

Usa [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat: agregar semilla de tarifas de acueducto
fix: conservar listas anidadas en el Markdown
docs: documentar el renderizado de iframes
test: cubrir la exclusión de rutas privadas
```

## Reglas de captura

- No agregues rutas de login, dashboard, PQRS, pagos, formularios o datos
  personales.
- Respeta `robots.txt`, el throttle y el `User-Agent` identificable.
- La extracción debe poder probarse sin red.
- No versiones `data/raw/`, `data/processed/` ni `data/errors.jsonl`.
- Si agregas una dependencia, justifícala en el PR.

## Pruebas

- `pytest` con patrón **AAA** (Arrange · Act · Assert).
- Prefiere HTML de fixture sobre llamadas reales a la red.
- Toda corrección de extracción debe incluir un caso que falle sin el cambio.
