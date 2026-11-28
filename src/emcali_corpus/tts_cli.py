"""CLI de síntesis de voz neural para OpenClaw (@openclaw/tts-local-cli)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from emcali_corpus.voice import synthesize_neural_tts


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="EMCALI Melva Neural TTS CLI (ElevenLabs / Edge)")
    parser.add_argument("--text", default="", help="Texto a sintetizar (si vacío, lee stdin).")
    parser.add_argument("--output", default="", help="Ruta de archivo MP3 de salida.")
    args = parser.parse_args()

    text = (args.text or sys.stdin.read()).strip()
    if not text:
        sys.exit(1)

    audio_bytes, _media_type, _provider = synthesize_neural_tts(text, max_chars=900)
    if args.output:
        Path(args.output).write_bytes(audio_bytes)
    else:
        sys.stdout.buffer.write(audio_bytes)


if __name__ == "__main__":
    main()
