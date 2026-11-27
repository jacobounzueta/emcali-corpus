"""Procesamiento de voz, hotword ('Doña Melva', 'Oye Doña Melva') y síntesis neural TTS."""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

import requests
from pydantic import BaseModel, Field

DEFAULT_EDGE_VOICE = "es-CO-SalomeNeural"
DEFAULT_ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"
DEFAULT_ELEVENLABS_MODEL = "eleven_flash_v2_5"

HOTWORD_ALIASES: tuple[str, ...] = (
    "oye doña melva",
    "hola doña melva",
    "doña melva",
    "hey doña melva",
    "ok doña melva",
    "oye dona melva",
    "hola dona melva",
    "dona melva",
    "oye doña melba",
    "hola doña melba",
    "doña melba",
    "oye melva",
    "hola melva",
    "melva",
    "hey melva",
    "ok melva",
    "oye melba",
    "hola melba",
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
    r"(?:(?:do[nñ]a\s+)?(?:melva|melba)|mile|myle|mila|milena|"
    r"eder|éder|edher|heber|ever|emcali|em\s+cali|en\s+cali)\b[,.:;!\s-]*",
    re.IGNORECASE,
)

SLEEP_REGEX = re.compile(
    r"^\s*(?:(?:muchas\s+)?gracias(?:\s+(?:(?:do[nñ]a\s+)?(?:melva|melba)|mile|eder))?|"
    r"adi[oó]s(?:\s+(?:(?:do[nñ]a\s+)?(?:melva|melba)|mile|eder))?|"
    r"hasta\s+luego(?:\s+(?:(?:do[nñ]a\s+)?(?:melva|melba)|mile|eder))?|"
    r"eso\s+es\s+todo(?:\s+(?:(?:do[nñ]a\s+)?(?:melva|melba)|mile|eder))?|"
    r"detente(?:\s+(?:(?:do[nñ]a\s+)?(?:melva|melba)|mile|eder))?|"
    r"para\s+(?:(?:do[nñ]a\s+)?(?:melva|melba)|mile|eder)|"
    r"terminar\s+sesi[oó]n|modo\s+espera)\s*[.!]*$",
    re.IGNORECASE,
)

SELF_ECHO_REGEX = re.compile(
    r"(?:soy\s+(?:(?:do[nñ]a\s+)?(?:melva|melba)|mile|eder)(?:\s+live)?|"
    r"aqu[ií]\s+do[nñ]a\s+melva|listo\s+vecino|te\s+dej[eé]\s+el\s+detalle\s+en\s+la\s+tabla|"
    r"te\s+escucho\s+en\s+vivo|datos\s+exactos\s+validados|fuente\s+estructurada|"
    r"tarifa\s+aplicada\s+promedio|paso\s+a\s+modo\s+de\s+espera|"
    r"subsidio\s+contribuci[oó]n|emcali\s+e\s+i\s+c\s+e)",
    re.IGNORECASE,
)

PHONETIC_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(do[nñ]a\s+(?:melba|melva))\b", re.IGNORECASE), "Doña Melva"),
    (re.compile(r"\b(melba|melva)\b", re.IGNORECASE), "Melva"),
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
    """Resultado de procesar una transcripción de voz con Hotword ('Oye Melva' / 'Hola Melva')."""

    raw_transcript: str = Field(description="Transcripción cruda capturada del micrófono.")
    normalized_transcript: str = Field(
        description="Transcripción con corrección fonética de dominio EMCALI."
    )
    hotword_detected: bool = Field(
        default=False,
        description=(
            "True si se pronunció la palabra de activación ('Melva', 'Oye Melva' o 'Hola Melva')."
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
            "True si el usuario pidió cerrar el modo Melva Live ('Gracias Melva', 'Eso es todo')."
        ),
    )
    should_enter_live: bool = Field(
        default=False,
        description="True si la sesión debe mantenerse en escucha continua (Melva Live).",
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
            matched_hotword="Melva Live Off",
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
            matched_hotword=matched_hw or "Melva Live Off",
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
    clean_query = remainder if remainder else ("Hola Melva" if hotword_detected else normalized)

    return VoiceCommandAnalysis(
        raw_transcript=transcript,
        normalized_transcript=normalized,
        hotword_detected=hotword_detected or live_session_active,
        matched_hotword=matched_hw or ("Melva Live" if live_session_active else None),
        clean_query=clean_query,
        wake_only=wake_only,
        sleep_requested=False,
        should_enter_live=True,
    )


TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
HR_LINE_RE = re.compile(r"^\s*[-*_]{3,}\s*$", re.MULTILINE)
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
RAW_URL_RE = re.compile(r"https?://\S+")
BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s+", re.MULTILINE)
DASH_RE = re.compile(r"[\u2014\u2013]+|\s-\s|--+")


def build_tts_speech_summary(markdown_answer: str, *, max_chars: int = 260) -> str:
    """Convierte Markdown en resumen hablado natural (2-3 frases) sin tablas, guiones ni URLs."""
    without_sources = markdown_answer.split("### 🔗 Fuentes Oficiales")[0]
    had_table = bool(TABLE_ROW_RE.search(without_sources))
    text = CODE_FENCE_RE.sub(" ", without_sources)
    text = TABLE_ROW_RE.sub(" ", text)
    text = HR_LINE_RE.sub(" ", text)
    text = MARKDOWN_LINK_RE.sub(r"\1", text)
    text = RAW_URL_RE.sub(" ", text)
    text = BULLET_PREFIX_RE.sub("", text)
    text = EMOJI_RE.sub(" ", text)
    text = MARKDOWN_FORMATTING_RE.sub(" ", text)
    text = DASH_RE.sub(", ", text)
    clean = re.sub(r"\s*,\s*,\s*", ", ", text)
    clean = re.sub(r"\s+", " ", clean).strip(" ,;-")

    if not clean and had_table:
        return "Listo vecino, te dejé el detalle completo en la tabla del chat."

    if len(clean) <= max_chars:
        if had_table and len(clean) + 52 <= max_chars + 40:
            return f"{clean.rstrip('.')} . Te dejé el detalle en la tabla del chat.".replace(
                " .", "."
            )
        return clean

    # Cortar limpiamente al final de la última oración completa dentro de max_chars
    window = clean[:max_chars]
    best_end = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
    if best_end >= 60:
        return window[: best_end + 1].strip()
    return window.rsplit(" ", 1)[0].rstrip(" ,;:") + "."


async def _synthesize_edge_tts_bytes(text: str, voice: str) -> bytes:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+5%")
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            data = chunk.get("data")
            if isinstance(data, bytes):
                chunks.append(data)
    return b"".join(chunks)


async def stream_edge_tts_chunks(text: str, *, max_chars: int = 260):
    """Generador asíncrono que emite frames MP3 conforme llegan de Edge Neural TTS."""
    import edge_tts

    clean = build_tts_speech_summary(text, max_chars=max_chars)
    if not clean:
        return
    edge_voice = os.getenv("EMCALI_TTS_VOICE", DEFAULT_EDGE_VOICE).strip() or DEFAULT_EDGE_VOICE
    communicate = edge_tts.Communicate(text=clean, voice=edge_voice, rate="+5%")
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            data = chunk.get("data")
            if isinstance(data, bytes):
                yield data


def synthesize_neural_tts(text: str, *, max_chars: int = 260) -> tuple[bytes, str, str]:
    """Sintetiza voz neural colombiana para Melva (ElevenLabs o Edge es-CO-SalomeNeural)."""
    clean = build_tts_speech_summary(text, max_chars=max_chars)
    if not clean:
        raise ValueError("El texto para síntesis de voz está vacío.")

    eleven_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if eleven_key:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_ELEVENLABS_VOICE_ID).strip()
        model_id = os.getenv("ELEVENLABS_MODEL_ID", DEFAULT_ELEVENLABS_MODEL).strip()
        try:
            resp = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": eleven_key,
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                },
                json={
                    "text": clean,
                    "model_id": model_id,
                    "voice_settings": {"stability": 0.48, "similarity_boost": 0.78},
                },
                timeout=15,
            )
            if resp.status_code == 200 and resp.content:
                return resp.content, "audio/mpeg", f"elevenlabs:{model_id}"
        except requests.RequestException:
            pass

    edge_voice = os.getenv("EMCALI_TTS_VOICE", DEFAULT_EDGE_VOICE).strip() or DEFAULT_EDGE_VOICE
    audio_bytes = asyncio.run(_synthesize_edge_tts_bytes(clean, edge_voice))
    if not audio_bytes:
        raise RuntimeError("No se generó audio desde Edge Neural TTS.")
    return audio_bytes, "audio/mpeg", f"edge-tts:{edge_voice}"


def describe_voice_capabilities() -> dict[str, Any]:
    """Devuelve la especificación del módulo de voz y hotword para el frontend."""
    eleven_ready = bool(os.getenv("ELEVENLABS_API_KEY", "").strip())
    edge_voice = os.getenv("EMCALI_TTS_VOICE", DEFAULT_EDGE_VOICE).strip() or DEFAULT_EDGE_VOICE
    return {
        "hotwords_supported": ["Doña Melva", "Oye Doña Melva", "Hola Doña Melva"],
        "default_locale": "es-CO",
        "phonetic_corrections": ["Doña Melva", "EMCALI", "PQR", "PQRS", "kWh", "Ley 1581", "PSE"],
        "tts_enabled": True,
        "neural_tts_provider": "elevenlabs" if eleven_ready else f"edge-tts ({edge_voice})",
        "elevenlabs_configured": eleven_ready,
    }
