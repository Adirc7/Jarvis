"""Hear the candidate voices before choosing one.

    uv run python scripts/voice_preview.py                 all British male Kokoro voices
    uv run python scripts/voice_preview.py --play          ...and play them one by one
    uv run python scripts/voice_preview.py --voices bm_george bm_lewis --text "Hello Adhi."

Writes samples/<voice>_raw.wav and samples/<voice>_styled.wav (with the
[voice_style] chain from settings.toml), so you can compare the raw voice with
the "Jarvis feel". Pick one, then set tts_voice in config/languages.toml.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.config import load_settings  # noqa: E402
from jarvis.voice.audio_io import save_wav  # noqa: E402
from jarvis.voice.effects import VoiceStyle, match_loudness  # noqa: E402
from jarvis.voice.tts import KokoroTTS  # noqa: E402

DEFAULT_TEXT = (
    "Good evening. All systems are running normally. "
    "Your build finished two minutes ago, and there are no new messages."
)
BRITISH_MALE = ["bm_george", "bm_lewis", "bm_daniel", "bm_fable"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--voices", nargs="+", default=BRITISH_MALE)
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--lang", default="en-gb")
    ap.add_argument("--play", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "samples"))
    args = ap.parse_args()

    settings = load_settings(load_env=False)
    style = VoiceStyle.from_dict(settings.get("voice_style", {}))
    style.enabled = True
    out = Path(args.out)
    speed = float(settings.get("tts.speed", 1.0))
    model = settings.path("tts.kokoro_model", "models/kokoro-v1.0.onnx")
    voices = settings.path("tts.kokoro_voices", "models/voices-v1.0.bin")

    for voice in args.voices:
        tts = KokoroTTS(model, voices, voice, args.lang, speed)
        dry = tts.synthesize(args.text)
        styled = style.process(dry, tts.sample_rate)
        # Same loudness as the styled version, so the comparison is fair.
        raw = match_loudness(dry, style.target_rms_db)
        save_wav(out / f"{voice}_raw.wav", raw, tts.sample_rate)
        save_wav(out / f"{voice}_styled.wav", styled, tts.sample_rate)
        print(f"{voice}: {len(raw) / tts.sample_rate:.1f} s -> {out / (voice + '_styled.wav')}")
        if args.play:
            import sounddevice as sd
            for label, audio in (("raw", raw), ("styled", styled)):
                print(f"  playing {voice} ({label})")
                sd.play(audio, tts.sample_rate)
                sd.wait()
    print("\nChoose one and set tts_voice under [en] in config/languages.toml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
