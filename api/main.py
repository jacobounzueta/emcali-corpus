"""Punto de entrada oficial para FastAPI CLI (`uv run fastapi dev api/main.py`)."""

from __future__ import annotations

from emcali_corpus.api import app

__all__ = ["app"]
