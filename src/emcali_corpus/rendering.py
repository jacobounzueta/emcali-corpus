"""Renderizado de páginas con JavaScript mediante Playwright."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Playwright,
    Route,
    sync_playwright,
)
from playwright.sync_api import (
    Error as PlaywrightError,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from emcali_corpus import config

_BLOCKED_RESOURCES = {"image", "font", "media"}
_BLOCKED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".woff", ".woff2", ".ttf")


class RenderError(RuntimeError):
    """No fue posible renderizar la página con un navegador."""


def _candidate_executables() -> list[Path]:
    """Busca binarios de Chromium instalados por Playwright en la máquina."""
    roots: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        roots.append(Path(local_app_data) / "ms-playwright")
    roots.append(Path.home() / ".cache" / "ms-playwright")

    candidates: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        patterns = [
            "chromium-*/chrome-win64/chrome.exe",
            "chromium-*/chrome-linux/chrome",
            "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
        ]
        for pattern in patterns:
            candidates.extend(sorted(root.glob(pattern), reverse=True))
    return candidates


def _launch_browser(playwright: Playwright) -> Browser:
    """Lanza Chromium probando binario propio, canal del sistema y caché local."""
    chromium = playwright.chromium
    attempts: list[dict[str, Any]] = []

    env_path = os.environ.get("EMCALI_CHROMIUM_PATH")
    if env_path:
        attempts.append({"executable_path": env_path})
    attempts.append({})
    if sys.platform == "win32":
        attempts.append({"channel": "msedge"})
    attempts.append({"channel": "chrome"})
    for candidate in _candidate_executables():
        attempts.append({"executable_path": str(candidate)})

    errors: list[str] = []
    for options in attempts:
        try:
            return chromium.launch(headless=True, args=["--no-sandbox"], **options)
        except PlaywrightError as exc:
            errors.append(f"{options or 'predeterminado'}: {exc}".splitlines()[0])
    raise RenderError(
        "No se encontró un navegador Chromium. Ejecuta `uv run playwright install chromium` "
        f"o define EMCALI_CHROMIUM_PATH. Intentos: {'; '.join(errors)}"
    )


class BrowserRenderer:
    """Navegador reutilizable que espera el contenido dinámico antes de capturar."""

    def __init__(self, *, timeout_ms: int = config.RENDER_TIMEOUT_MS) -> None:
        self.timeout_ms = timeout_ms
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def start(self) -> None:
        if self._browser is not None:
            return
        self._playwright = sync_playwright().start()
        self._browser = _launch_browser(self._playwright)
        self._context = self._browser.new_context(
            viewport=config.RENDER_VIEWPORT,
            locale="es-CO",
            user_agent=config.USER_AGENT,
            ignore_https_errors=True,
        )
        self._context.route("**/*", self._route)

    def _route(self, route: Route) -> None:
        request = route.request
        url = request.url.lower()
        if request.resource_type in _BLOCKED_RESOURCES or url.endswith(_BLOCKED_EXTENSIONS):
            route.abort()
        else:
            route.continue_()

    def close(self) -> None:
        for resource in (self._context, self._browser):
            if resource is not None:
                with contextlib.suppress(PlaywrightError):
                    resource.close()
        self._context = None
        self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def render(self, url: str) -> str:
        """Devuelve el HTML del DOM después de ejecutar JavaScript."""
        if self._context is None:
            self.start()
        assert self._context is not None
        last_error: Exception | None = None
        for _ in range(2):
            page = self._context.new_page()
            try:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                except PlaywrightTimeoutError:
                    page.wait_for_load_state("domcontentloaded", timeout=15_000)
                with contextlib.suppress(PlaywrightTimeoutError):
                    page.wait_for_function(
                        "() => document.querySelector('#root')?.children.length > 0",
                        timeout=15_000,
                    )
                page.wait_for_timeout(config.RENDER_SETTLE_MS)
                return page.content()
            except PlaywrightError as exc:
                last_error = exc
            finally:
                page.close()
        raise RenderError(f"No se pudo renderizar {url}: {last_error}")
