"""Procesamiento de voz, detección de hotword ('Eder', 'Oye Eder', 'Hola Eder') y síntesis TTS."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

HOTWORD_ALIASES: tuple[str, ...] = (
    "oye eder",
    "hola eder",
    "eder",
    "hey eder",
    "ok eder",
    "oye éder",
    "hola éder",
    "oye emcali",
    "hola emcali",
)

HOTWORD_REGEX = re.compile(
    r"^\s*(?:(?:oye|hola|hey|ok|buenos\s+d[ií]as|buenas\s+tardes)\s+)?"
    r"(?:eder|éder|edher|heber|ever|emcali|em\s+cali|en\s+cali)\b[,.:;!\s-]*",
    re.IGNORECASE,
)

SLEEP_REGEX = re.compile(
    r"^\s*(?:(?:muchas\s+)?gracias(?:\s+eder)?|adi[oó]s(?:\s+eder)?|"
    r"hasta\s+luego(?:\s+eder)?|eso\s+es\s+todo(?:\s+eder)?|"
    r"detente(?:\s+eder)?|para\s+eder|terminar\s+sesi[oó]n|modo\s+espera)\s*[.!]*$",
    re.IGNORECASE,
)

SELF_ECHO_REGEX = re.compile(
    r"(?:soy\s+eder\s+live|te\s+escucho\s+en\s+vivo|datos\s+exactos\s+validados|"
    r"fuente\s+estructurada|tarifa\s+aplicada\s+promedio|paso\s+a\s+modo\s+de\s+espera|"
    r"subsidio\s+contribuci[oó]n)",
    re.IGNORECASE,
)

PHONETIC_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(éder|edher|heber)\b", re.IGNORECASE), "Eder"),
    (re.compile(r"\b(em\s+cali|en\s+cali)\b", re.IGNORECASE), "EMCALI"),
    (re.compile(r"\b(pe\s*cu\s*erre\s*ese|p\s*q\s*r\s*s)\b", re.IGNORECASE), "PQRS"),
    (re.compile(r"\b(pe\s*cu\s*erre|p\s*q\s*r)\b", re.IGNORECASE), "PQR"),
    (re.compile(r"\b(kilovatio\s+hora|kilovatios\s+hora)\b", re.IGNORECASE), "kWh"),
    (re.compile(r"\b(ley\s+quince\s+ochenta\s+y\s+uno)\b", re.IGNORECASE), "Ley 1581"),
    (re.compile(r"\b(pe\s*ese\s*e)\b", re.IGNORECASE), "PSE"),
)

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
MARKDOWN_FORMATTING_RE = re.compile(r"[#*`_~>|]+")
EMOJI_RE = re.compile(
    r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2300-\u23FF\u2B00-\u2BFF\uFE0F\u200D]+",
    flags=re.UNICODE,
)


class VoiceCommandAnalysis(BaseModel):
    """Resultado de procesar una transcripción de voz con Hotword ('Oye Eder' / 'Hola Eder')."""

    raw_transcript: str = Field(description="Transcripción cruda capturada del micrófono.")
    normalized_transcript: str = Field(
        description="Transcripción con corrección fonética de dominio EMCALI."
    )
    hotword_detected: bool = Field(
        default=False,
        description=(
            "True si se pronunció la palabra de activación ('Eder', 'Oye Eder' o 'Hola Eder')."
        ),
    )
    matched_hotword: str | None = Field(
        default=None,
        description="Frase de activación detectada al inicio del comando.",
    )
    clean_query: str = Field(
        description="Consulta limpia lista para enviar al Router Jev y al grafo LangGraph.",
    )
    wake_only: bool = Field(
        default=False,
        description="True si el usuario solo dijo el hotword sin formular aún la pregunta.",
    )
    sleep_requested: bool = Field(
        default=False,
        description=(
            "True si el usuario pidió cerrar el modo Eder Live ('Gracias Eder', 'Eso es todo')."
        ),
    )
    should_enter_live: bool = Field(
        default=False,
        description="True si la sesión debe mantenerse en escucha continua (Eder Live).",
    )


def normalize_domain_speech(transcript: str) -> str:
    """Corrige variaciones fonéticas comunes del reconocimiento de voz en español para EMCALI."""
    text = transcript.strip()
    for pattern, replacement in PHONETIC_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip()


def parse_voice_hotword_command(
    transcript: str,
    *,
    require_hotword: bool = False,
    live_session_active: bool = False,
) -> VoiceCommandAnalysis:
    """Detecta hotword ('Eder', 'Oye Eder', 'Hola Eder') o turnos continuos en Eder Live."""
    normalized = normalize_domain_speech(transcript)
    lowered = normalized.lower()

    if SELF_ECHO_REGEX.search(normalized):
        return VoiceCommandAnalysis(
            raw_transcript=transcript,
            normalized_transcript=normalized,
            hotword_detected=False,
            matched_hotword=None,
            clean_query="",
            wake_only=False,
            sleep_requested=False,
            should_enter_live=live_session_active,
        )

    if SLEEP_REGEX.match(normalized):
        return VoiceCommandAnalysis(
            raw_transcript=transcript,
            normalized_transcript=normalized,
            hotword_detected=True,
            matched_hotword="Eder Live Off",
            clean_query="",
            wake_only=False,
            sleep_requested=True,
            should_enter_live=False,
        )

    matched_hw: str | None = None
    for alias in HOTWORD_ALIASES:
        if lowered.startswith(alias):
            matched_hw = alias
            break

    m = HOTWORD_REGEX.match(normalized)
    if m:
        hotword_detected = True
        matched_hw = matched_hw or m.group(0).strip(" ,.:;!-")
        remainder = normalized[m.end() :].strip(" ,.:;!-")
    else:
        hotword_detected = False
        remainder = normalized

    if SLEEP_REGEX.match(remainder) and remainder:
        return VoiceCommandAnalysis(
            raw_transcript=transcript,
            normalized_transcript=normalized,
            hotword_detected=True,
            matched_hotword=matched_hw or "Eder Live Off",
            clean_query="",
            wake_only=False,
            sleep_requested=True,
            should_enter_live=False,
        )

    if require_hotword and not hotword_detected and not live_session_active:
        return VoiceCommandAnalysis(
            raw_transcript=transcript,
            normalized_transcript=normalized,
            hotword_detected=False,
            matched_hotword=None,
            clean_query="",
            wake_only=False,
            sleep_requested=False,
            should_enter_live=False,
        )

    wake_only = hotword_detected and len(remainder) == 0
    clean_query = remainder if remainder else ("Hola Eder" if hotword_detected else normalized)

    return VoiceCommandAnalysis(
        raw_transcript=transcript,
        normalized_transcript=normalized,
        hotword_detected=hotword_detected or live_session_active,
        matched_hotword=matched_hw or ("Eder Live" if live_session_active else None),
        clean_query=clean_query,
        wake_only=wake_only,
        sleep_requested=False,
        should_enter_live=True,
    )


def build_tts_speech_summary(markdown_answer: str, *, max_chars: int = 460) -> str:
    """Convierte una respuesta Markdown con citas en texto fluido sin emojis para voz (TTS)."""
    without_sources = markdown_answer.split("### 🔗 Fuentes Oficiales")[0]
    without_links = MARKDOWN_LINK_RE.sub(r"\1", without_sources)
    without_emojis = EMOJI_RE.sub(" ", without_links)
    clean = MARKDOWN_FORMATTING_RE.sub(" ", without_emojis)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= max_chars:
        return clean
    cutoff = clean[:max_chars].rsplit(".", 1)[0]
    return (cutoff + ".") if len(cutoff) > 80 else (clean[:max_chars].rstrip() + "...")


def describe_voice_capabilities() -> dict[str, Any]:
    """Devuelve la especificación del módulo de voz y hotword para el frontend."""
    return {
        "hotwords_supported": ["Eder", "Oye Eder", "Hola Eder"],
        "default_locale": "es-CO",
        "phonetic_corrections": ["Eder", "EMCALI", "PQR", "PQRS", "kWh", "Ley 1581", "PSE"],
        "tts_enabled": True,
    }
