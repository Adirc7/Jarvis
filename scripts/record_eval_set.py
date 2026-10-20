"""Record yourself reading test sentences, to measure speech recognition later.

    uv run python scripts/record_eval_set.py eval/sentences_en.txt --lang en
    uv run python scripts/record_eval_set.py eval/sentences_si.txt --lang si
    uv run python scripts/record_eval_set.py eval/sentences_singlish.txt --lang si --set singlish
    uv run python scripts/record_eval_set.py eval/sentences_si.txt --lang si --speaker friend1

For each sentence: press Enter, read it aloud, press Enter again. Recordings go
to eval/recordings/<set>/ (the language code unless --set is given) with a
manifest.csv of file -> correct text. Recording again never overwrites a clip.
They stay on your laptop (the folder is in .gitignore). Only record other
people if they agree.

Then score models with scripts/eval_stt.py.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.voice.audio_io import save_wav  # noqa: E402

RATE = 16000


def read_sentences(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")]


def clip_name(out_dir: Path, speaker: str, sentences: Path, index: int) -> str:
    """me_sentences_si_003.wav, or me_sentences_si_003-2.wav if that exists."""
    base = f"{speaker}_{sentences.stem}_{index:03d}"
    name, n = f"{base}.wav", 1
    while (out_dir / name).exists():
        n += 1
        name = f"{base}-{n}.wav"
    return name


def record_until_enter() -> np.ndarray:
    import sounddevice as sd

    frames: list[np.ndarray] = []

    def callback(indata, n, t, status):
        frames.append(indata[:, 0].copy())

    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", callback=callback):
        input("   recording... press Enter when done ")
    return np.concatenate(frames) if frames else np.zeros(0, np.float32)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("sentences", type=Path)
    ap.add_argument("--lang", required=True, help="Jarvis language code: en, si, ta")
    ap.add_argument("--speaker", default="me", help="label for whoever is reading")
    ap.add_argument("--set", dest="set_name", help="folder under eval/recordings (default: the language code)")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    sentences = read_sentences(args.sentences)
    out_dir = ROOT / "eval" / "recordings" / (args.set_name or args.lang)
    manifest = out_dir / "manifest.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = manifest.is_file()
    with open(manifest, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not existing:
            writer.writerow(["file", "text", "speaker", "lang"])
        for i, text in enumerate(sentences, 1):
            print(f"\n[{i}/{len(sentences)}] {text}")
            cmd = input("   Enter = record, s = skip, q = quit: ").strip().lower()
            if cmd == "q":
                break
            if cmd == "s":
                continue
            audio = record_until_enter()
            name = clip_name(out_dir, args.speaker, args.sentences, i)
            save_wav(out_dir / name, audio, RATE)
            writer.writerow([name, text, args.speaker, args.lang])
            f.flush()
            print(f"   saved {name} ({len(audio) / RATE:.1f} s)")
    print(f"\nManifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
