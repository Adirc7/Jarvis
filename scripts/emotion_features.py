"""Features from a public emotional speech set, in the same form as your /mood labels.

    uv run python scripts/emotion_features.py ravdess D:\\data\\RAVDESS
    uv run python scripts/emotion_features.py cremad D:\\data\\CREMA-D\\AudioWAV
    uv run python scripts/emotion_features.py csv D:\\data\\EmoTa --labels D:\\data\\EmoTa\\labels.csv

Each recording goes through the same emotion model Jarvis uses, and its features (every layer) are written
to data/emotion/corpus-<name>.jsonl, one row per recording: the corpus's own label ("angry", "sad", ...),
the speaker as the "session" (so GroupKFold keeps a speaker out of training when it's tested), and
how="corpus". Your own labels stay in labels.jsonl; your training script decides whether and how to mix
them (docs/EMOTION_RESEARCH.md: more voices for the classifier to learn from, then your own to fit it to you).

The audio isn't copied anywhere; only its features are kept. Check each set's licence before using it
(RAVDESS: CC BY-NC-SA 4.0; CREMA-D: see its GitHub repository; EmoTa: its own academic licence).

csv: a file with columns path, label, speaker (path relative to the folder).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.config import load_settings  # noqa: E402
from jarvis.perception.emotion import BASELINE, EmotionEars, encode_layers  # noqa: E402

# RAVDESS file names: modality-channel-EMOTION-intensity-statement-repetition-ACTOR.wav
RAVDESS = {"01": "neutral", "02": "calm", "03": "happy", "04": "sad", "05": "angry", "06": "fearful",
           "07": "disgust", "08": "surprised"}
# CREMA-D file names: ACTOR_SENTENCE_EMOTION_LEVEL.wav
CREMAD = {"ANG": "angry", "DIS": "disgust", "FEA": "fearful", "HAP": "happy", "NEU": "neutral", "SAD": "sad"}
AUDIO = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}


def ravdess(folder: Path) -> list[tuple[Path, str, str]]:
    found = []
    for path in sorted(folder.rglob("*.wav")):
        parts = path.stem.split("-")
        if len(parts) == 7 and parts[:2] == ["03", "01"] and parts[2] in RAVDESS:   # audio only, speech
            found.append((path, RAVDESS[parts[2]], f"ravdess:{parts[6]}"))
    return found


def cremad(folder: Path) -> list[tuple[Path, str, str]]:
    found = []
    for path in sorted(folder.rglob("*.wav")):
        parts = path.stem.split("_")
        if len(parts) >= 3 and parts[2] in CREMAD:
            found.append((path, CREMAD[parts[2]], f"cremad:{parts[0]}"))
    return found


def from_csv(folder: Path, labels: Path) -> list[tuple[Path, str, str]]:
    with labels.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    missing = {"path", "label", "speaker"} - set(rows[0] if rows else {})
    if missing:
        raise SystemExit(f"{labels} needs the columns path, label, speaker (missing: {', '.join(sorted(missing))})")
    name = folder.name.lower()
    return [(folder / r["path"], r["label"].strip().lower(), f"{name}:{r['speaker'].strip()}") for r in rows]


def load_audio(path: Path):
    """16 kHz mono float32. 16-bit WAV (RAVDESS, CREMA-D, EmoTa) with the standard library; anything else
    with PyAV, which Whisper already brings. (faster-whisper's own decode_audio fails with PyAV 19.)"""
    import wave
    from math import gcd

    import numpy as np

    from jarvis.voice.audio_io import load_wav
    try:
        audio, rate = load_wav(path)
    except (ValueError, EOFError, OSError, wave.Error):  # not 16-bit WAV
        import av
        with av.open(str(path)) as container:
            resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
            chunks = [f.to_ndarray().reshape(-1) for frame in container.decode(audio=0)
                      for f in resampler.resample(frame)]
            chunks += [f.to_ndarray().reshape(-1) for f in resampler.resample(None)]
        return np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(0, np.float32)
    if rate == 16000:
        return audio
    from scipy.signal import resample_poly                # filtered: no aliasing from 48 kHz recordings
    g = gcd(16000, rate)
    return resample_poly(audio, 16000 // g, rate // g).astype(np.float32)


def main(argv=None, ears=None, loader=load_audio, say=print) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("kind", choices=("ravdess", "cremad", "csv"))
    ap.add_argument("folder")
    ap.add_argument("--labels", help="csv only: the file with path, label, speaker")
    ap.add_argument("--name", help="the corpus name in the output file (default: the kind, or the folder's name)")
    ap.add_argument("--out", help="default: data/emotion/corpus-<name>.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="only the first N recordings (to try it)")
    args = ap.parse_args(argv)
    folder = Path(args.folder)
    if args.kind == "csv":
        if not args.labels:
            raise SystemExit("csv needs --labels <file.csv> with columns path, label, speaker")
        items = from_csv(folder, Path(args.labels))
    else:
        items = ravdess(folder) if args.kind == "ravdess" else cremad(folder)
    if args.limit:
        items = items[: args.limit]
    if not items:
        say(f"No {args.kind} recordings found in {folder}.")
        return 1
    name = args.name or (folder.name.lower() if args.kind == "csv" else args.kind)
    settings = load_settings()
    out = Path(args.out) if args.out else settings.path("emotion.labels_dir", "data/emotion") / f"corpus-{name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    if ears is None:
        ears = EmotionEars(str(settings.get("emotion.model", BASELINE)), str(settings.get("emotion.device", "cpu")))
    say(f"{len(items)} recordings from {name}; features to {out} (about 0.3 s each on the CPU)...")
    done = skipped = 0
    with out.open("w", encoding="utf-8") as f:
        for i, (path, label, speaker) in enumerate(items, 1):
            try:
                heard = ears.hear(loader(path))
            except Exception as exc:  # noqa: BLE001 - one unreadable file shouldn't stop the rest
                skipped += 1
                say(f"  skipped {path.name}: {type(exc).__name__}: {str(exc)[:80]}")
                continue
            row = {"time": datetime.now().isoformat(timespec="seconds"), "session": speaker, "label": label,  # noqa: DTZ005
                   "heard": heard.label, "heard_confidence": heard.confidence, "level": 1, "scores": heard.baseline,
                   "baseline": heard.baseline, "features": heard.features, "how": "corpus", "corpus": name,
                   "file": path.name}
            if heard.layers is not None:
                row["layers"] = encode_layers(heard.layers)
            f.write(json.dumps(row) + "\n")
            done += 1
            if i % 100 == 0:
                say(f"  {i} of {len(items)}")
    speakers = len({s for _, _, s in items})
    say(f"Done: {done} recordings from {speakers} speakers ({skipped} skipped), in {out}.")
    return 0 if done else 1


if __name__ == "__main__":
    raise SystemExit(main())
