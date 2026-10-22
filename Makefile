SHELL := /bin/sh
UV ?= uv
CLI := $(UV) run emcali-corpus

.DEFAULT_GOAL := help

.PHONY: help sync install-browsers capture capture-all capture-sections discover \
	index reprocess status list lint format format-check typecheck test check pre-commit \
	clean-bronze clean

help: ## Muestra esta ayuda
	@echo "EMCALI Corpus — tareas disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

sync: ## Sincroniza el entorno con uv.lock
	$(UV) sync

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

clean-bronze: ## Borra las capas bronze y silver (conserva gold)
	$(UV) run python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in (pathlib.Path('data/raw'), pathlib.Path('data/processed'))]"

clean: ## Borra bronze, silver, errores e índice generado
	$(UV) run python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in (pathlib.Path('data/raw'), pathlib.Path('data/processed'))]; pathlib.Path('data/gold/corpus.jsonl').unlink(missing_ok=True)"
