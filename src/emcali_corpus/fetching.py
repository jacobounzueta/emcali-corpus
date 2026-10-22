"""Cliente HTTP educado y política de robots.txt."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Protocol, Self
from urllib.parse import urlparse, urlunparse

import requests

from emcali_corpus import config
from emcali_corpus.models import FetchResult


class Fetcher(Protocol):
    """Contrato mínimo de un cliente capaz de descargar una URL."""

    def fetch(self, url: str) -> FetchResult:
        """Descarga una URL y devuelve el cuerpo decodificado."""
        ...


_CHARSET_RE = re.compile(r"""charset=["']?([\w-]+)""", re.IGNORECASE)
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    """Error irrecuperable al descargar una URL."""


def normalize_url(url: str) -> str:
    """Quita fragmentos y normaliza el esquema/host de una URL."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def decode_html(content: bytes, content_type: str) -> str:
    """Decodifica HTML priorizando el charset declarado en la cabecera o el meta."""
    encoding = ""
    match = _CHARSET_RE.search(content_type or "")
    if match:
        encoding = match.group(1)
    if not encoding:
        meta = re.search(rb"""<meta[^>]+charset=["']?([\w-]+)""", content[:8192], re.IGNORECASE)
        if meta:
            encoding = meta.group(1).decode("ascii", errors="ignore")
    try:
        return content.decode(encoding or "utf-8", errors="replace")
    except LookupError:
        return content.decode("utf-8", errors="replace")


@dataclass(slots=True)
class RobotsPolicy:
    """Subconjunto de robots.txt suficiente para un crawler de un solo host."""

    rules: list[tuple[bool, str]] = field(default_factory=list)

    @classmethod
    def from_text(cls, text: str, user_agent: str = "EMCALI-Corpus") -> Self:
        agent_token = user_agent.split("/")[0].strip().lower()
        groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
        current_agents: list[str] = []
        current_rules: list[tuple[bool, str]] = []

        def flush() -> None:
            if current_agents:
                groups.append((list(current_agents), list(current_rules)))
            current_agents.clear()
            current_rules.clear()

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if current_rules:
                    flush()
                current_agents.append(value.lower())
            elif key in {"allow", "disallow"} and current_agents:
                if value:
                    current_rules.append((key == "allow", value))
        flush()

        selected: list[tuple[bool, str]] = []
        wildcard: list[tuple[bool, str]] = []
        for agents, rules in groups:
            if any(agent_token in agent or agent == "*" for agent in agents):
                if any(agent_token in agent for agent in agents):
                    selected.extend(rules)
                else:
                    wildcard.extend(rules)
        return cls(rules=selected or wildcard)

    def allowed(self, url: str) -> bool:
        """Aplica la regla de coincidencia más larga, con empate a favor de Allow."""
        path = urlparse(url).path or "/"
        best: tuple[int, bool] | None = None
        for allow, pattern in self.rules:
            if pattern == "/" or path.startswith(pattern.rstrip("*")):
                length = len(pattern)
                if best is None or length > best[0] or (length == best[0] and allow):
                    best = (length, allow)
        return True if best is None else best[1]


class HttpClient:
    """Sesión HTTP única con throttle, reintentos y User-Agent identificable."""

    def __init__(
        self,
        *,
        user_agent: str = config.USER_AGENT,
        timeout: int = config.REQUEST_TIMEOUT_SECONDS,
        delay: float = config.REQUEST_DELAY_SECONDS,
        max_retries: int = config.MAX_RETRIES,
    ) -> None:
        self.timeout = timeout
        self.delay = delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-CO,es;q=0.9,en;q=0.5",
            }
        )
        self._last_request = 0.0

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.session.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.monotonic()

    def fetch(self, url: str, *, allow_redirects: bool = True) -> FetchResult:
        """Descarga una URL y devuelve el cuerpo decodificado."""
        target = normalize_url(url)
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            started = time.monotonic()
            try:
                response = self.session.get(
                    target,
                    timeout=self.timeout,
                    allow_redirects=allow_redirects,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(min(2**attempt, 15))
                continue

            elapsed_ms = int((time.monotonic() - started) * 1000)
            if response.status_code in _RETRYABLE_STATUS and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After", "")
                wait = int(retry_after) if retry_after.isdigit() else min(2**attempt, 15)
                time.sleep(wait)
                continue

            content_type = response.headers.get("Content-Type", "")
            return FetchResult(
                url=target,
                final_url=response.url,
                status=response.status_code,
                text=decode_html(response.content, content_type),
                content_type=content_type,
                elapsed_ms=elapsed_ms,
            )

        raise FetchError(f"No se pudo descargar {target}: {last_error}")


def load_robots(client: HttpClient, robots_url: str = config.ROBOTS_URL) -> RobotsPolicy:
    """Carga robots.txt de forma tolerante a fallos."""
    try:
        result = client.fetch(robots_url)
    except FetchError:
        return RobotsPolicy()
    if not result.ok:
        return RobotsPolicy()
    return RobotsPolicy.from_text(result.text)
