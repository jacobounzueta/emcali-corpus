SHELL := /bin/sh
UV ?= uv
CLI := $(UV) run emcali-corpus

.DEFAULT_GOAL := help

.PHONY: help install dev pre-commit-install sync install-browsers capture capture-all capture-sections discover \
	index reprocess status list chunk app evaluate lint format format-check typecheck test check pre-commit build \
	clean-bronze clean-data clean

help: ## Muestra esta ayuda
	@echo "EMCALI Corpus — tareas disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Sincroniza el entorno virtual desde uv.lock
	$(UV) sync

dev: install pre-commit-install ## Configura el entorno de desarrollo completo (uv sync + hooks)

pre-commit-install: ## Instala los hooks de pre-commit en .git/hooks
	$(UV) run pre-commit install

sync: install ## Alias de install: sincroniza el entorno con uv.lock

install-browsers: ## Instala Chromium para Playwright
	$(UV) run playwright install chromium

capture: ## Captura las semillas curadas (portada y páginas principales)
	$(CLI) capture

capture-all: ## Captura todas las URLs del sitemap (incluye noticias)
	$(CLI) capture --all

capture-sections: ## Captura el sitemap sin noticias (páginas institucionales)
	$(CLI) capture --all --no-news

discover: ## Lista las semillas descubiertas en el sitemap
	$(CLI) discover

index: ## Reconstruye data/gold/corpus.jsonl desde los documentos gold
	$(CLI) index

reprocess: ## Reextrae gold y silver desde bronze (sin volver a la red)
	$(CLI) reprocess

status: ## Muestra el estado del corpus
	$(CLI) status

list: ## Lista los documentos indexados
	$(CLI) list

chunk: ## Consolida la base de conocimiento limpia y genera los chunks
	$(CLI) chunk

app: ## Inicia el dashboard interactivo de Streamlit (Taller 1)
	$(UV) run streamlit run app.py

evaluate: ## Ejecuta la batería de 22 preguntas de prueba y genera docs/evaluacion_preguntas.md
	$(CLI) evaluate

lint: ## Ejecuta Ruff sobre el código
	$(UV) run ruff check .

format: ## Formatea el código con Ruff
	$(UV) run ruff format .

format-check: ## Verifica el formato sin modificar archivos
	$(UV) run ruff format --check .

typecheck: ## Verifica tipos con ty
	$(UV) run ty check

test: ## Ejecuta la suite de pruebas
	$(UV) run pytest

check: lint format-check typecheck test ## Verificación completa antes de commitear

pre-commit: ## Ejecuta los hooks de pre-commit sobre todo el repositorio
	$(UV) run pre-commit run --all-files

build: ## Construye el paquete (sdist + wheel) en dist/
	$(UV) build

clean-bronze: ## Borra las capas bronze y silver (conserva gold)
	$(UV) run python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in (pathlib.Path('data/raw'), pathlib.Path('data/processed'))]"

clean-data: ## Borra bronze, silver e índice corpus.jsonl generado
	$(UV) run python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in (pathlib.Path('data/raw'), pathlib.Path('data/processed'))]; pathlib.Path('data/gold/corpus.jsonl').unlink(missing_ok=True)"

clean: ## Limpia artefactos temporales y cachés de Python (.pytest_cache, .ruff_cache, dist, build)
	$(UV) run python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in (pathlib.Path('.pytest_cache'), pathlib.Path('.ruff_cache'), pathlib.Path('.coverage'), pathlib.Path('htmlcov'), pathlib.Path('dist'), pathlib.Path('build'))]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
