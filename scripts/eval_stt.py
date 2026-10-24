"""Measure how well Whisper models understand you: WER, CER and speed.

    uv run python scripts/eval_stt.py --lang en --model small --model large-v3-turbo
    uv run python scripts/eval_stt.py --lang si --model small --model models/whisper-si-small-ct2

Reads eval/recordings/<lang>/manifest.csv (made by record_eval_set.py; use
--set singlish for another folder),
transcribes every file with each model, and prints a table like:

    model                 WER     CER   median ms   p95 ms
    small                 0.31    0.12        420      610

Per-sentence results go to logs/eval-stt-<lang>-<time>.csv, so you can see
which words each model gets wrong. These numbers are what the plan calls the
"transcript accuracy check".
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.config import load_settings  # noqa: E402
from jarvis.evaluation.wer import Score, score  # noqa: E402
from jarvis.telemetry import percentile  # noqa: E402
from jarvis.voice.audio_io import load_wav, resample  # noqa: E402
from jarvis.voice.stt import load_whisper  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lang", required=True)
    ap.add_argument("--model", action="append", required=True, help="repeat to compare models")
    ap.add_argument("--beam", type=int, default=1)
    ap.add_argument("--set", dest="set_name", help="folder under eval/recordings (default: the language code)")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    settings = load_settings(load_env=False)
    lang = settings.languages[args.lang]
    set_name = args.set_name or args.lang
    manifest = ROOT / "eval" / "recordings" / set_name / "manifest.csv"
    if not manifest.is_file():
        print(f"No recordings yet. Run: uv run python scripts/record_eval_set.py eval/sentences_{args.lang}.txt --lang {args.lang}")
        return 1
    with open(manifest, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    clips = []
    for row in rows:
        audio, rate = load_wav(manifest.parent / row["file"])
        clips.append((row["file"], row["text"], resample(audio, rate, 16000)))
    print(f"{len(clips)} recordings in {lang.name}\n")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_csv = settings.path("telemetry.dir", "logs") / f"eval-stt-{set_name}-{stamp}.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    summary = []
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "file", "reference", "hypothesis", "wer", "cer", "ms"])
        for name in args.model:
            model_path = ROOT / name
            model = load_whisper(str(model_path) if model_path.exists() else name,
                                 settings.get("stt.device", "cuda"), settings.get("stt.compute_type", "int8_float16"))
            total, times = Score(0, 0, 0, 0), []
            for file, ref, audio in clips:
                t0 = time.perf_counter()
                segments, _ = model.transcribe(audio, language=lang.whisper_code, beam_size=args.beam,
                                               vad_filter=True)
                hyp = " ".join(s.text.strip() for s in segments)
                ms = (time.perf_counter() - t0) * 1000
                s = score(ref, hyp)
                total, times = total + s, times + [ms]
                writer.writerow([name, file, ref, hyp, round(s.wer, 3), round(s.cer, 3), round(ms)])
                print(f"  [{name}] {file}: WER {s.wer:.2f}  \"{hyp[:60]}\"")
            summary.append((name, total.wer, total.cer, percentile(times, 50), percentile(times, 95)))

    print(f"\n{'model':28} {'WER':>6} {'CER':>6} {'median ms':>10} {'p95 ms':>8}")
    for name, w, c, p50, p95 in summary:
        print(f"{name:28} {w:6.2f} {c:6.2f} {p50:10.0f} {p95:8.0f}")
    print(f"\nDetails: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
