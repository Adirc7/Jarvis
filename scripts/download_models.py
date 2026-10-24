"""Download the model files Jarvis needs into models/.

    uv run python scripts/download_models.py            everything for your languages
    uv run python scripts/download_models.py --small    int8 Kokoro (88 MB instead of 310 MB)

Downloads:
  - MediaPipe hand landmarker                      (Google, Apache-2.0)
  - Kokoro-82M model + voices for English          (GitHub release, Apache-2.0)
  - Piper voices for languages that use "piper"    (Hugging Face)
Whisper models download themselves on first use, and so do MMS voices.
Files that already exist are skipped.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.config import load_settings  # noqa: E402

HAND = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
KOKORO = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
# Piper voices that don't live in the official rhasspy/piper-voices repo.
PIPER_EXTRA = {
    "si_LK-dilu-medium": "https://huggingface.co/chaturadilan/dilu-tts/resolve/main/onnx/si_LK-dilu-medium.onnx",
}


def official_piper_url(voice: str) -> str:
    """en_GB-alan-medium -> .../en/en_GB/alan/medium/en_GB-alan-medium.onnx"""
    locale, name, quality = voice.split("-", 2)
    lang = locale.split("_")[0]
    return f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang}/{locale}/{name}/{quality}/{voice}.onnx"


def fetch(url: str, dest: Path) -> bool:
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"  [skip] {dest.relative_to(ROOT)} already exists")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  [get ] {dest.relative_to(ROOT)}")
    try:
        with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as f:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while chunk := resp.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r         {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        print()
        tmp.replace(dest)
        return True
    except Exception as exc:
        print(f"\n  [FAIL] {url}\n         {exc}")
        tmp.unlink(missing_ok=True)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--small", action="store_true", help="use the int8 Kokoro model (smaller, slightly lower quality)")
    args = ap.parse_args()
    settings = load_settings(load_env=False)
    ok = True

    print("Hand tracking")
    ok &= fetch(HAND, settings.path("vision.hand_model", "models/hand_landmarker.task"))

    engines = {lang.tts_engine for lang in settings.languages.values()}
    if "kokoro" in engines:
        print("Kokoro (English voices)")
        model_name = "kokoro-v1.0.int8.onnx" if args.small else "kokoro-v1.0.onnx"
        model_dest = settings.path("tts.kokoro_model", "models/kokoro-v1.0.onnx")
        if args.small:
            print("  (saving the int8 model under the configured name)")
        ok &= fetch(KOKORO + model_name, model_dest)
        ok &= fetch(KOKORO + "voices-v1.0.bin", settings.path("tts.kokoro_voices", "models/voices-v1.0.bin"))

    piper_dir = settings.path("tts.piper_dir", "models/piper")
    for lang in settings.languages.values():
        if lang.tts_engine != "piper":
            continue
        print(f"Piper voice for {lang.name}: {lang.tts_voice}")
        url = PIPER_EXTRA.get(lang.tts_voice) or official_piper_url(lang.tts_voice)
        ok &= fetch(url, piper_dir / f"{lang.tts_voice}.onnx")
        ok &= fetch(url + ".json", piper_dir / f"{lang.tts_voice}.onnx.json")

    mms = [lang.name for lang in settings.languages.values() if lang.tts_engine == "mms"]
    if mms:
        print(f"MMS voices ({', '.join(mms)}) download on first use; they need: uv sync --extra mms")
    print("\nDone." if ok else "\nSome downloads failed; see above.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
