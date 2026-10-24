"""Get a Sinhala Whisper model that someone already fine-tuned, and try it.

Base Whisper barely knows Sinhala: it hears that you speak Sinhala, then
writes nonsense. Others have fine-tuned Whisper on Sinhala speech and shared
it on Hugging Face. This script downloads one, converts it for Jarvis
(faster-whisper's CTranslate2 format, int8 on the GPU), and compares it with
today's model on Sinhala test sentences read by the Piper "dilu" voice.

    uv run python scripts/get_sinhala_whisper.py                  # the small one (fast, like today's)
    uv run python scripts/get_sinhala_whisper.py --model medium   # bigger: maybe better, slower
    uv run python scripts/get_sinhala_whisper.py --check models/whisper-si-small-ct2   # check again only

Then, to use it, in config/languages.toml under [si]:
    stt_model = "models/whisper-si-small-ct2"     (the script prints the exact line)

Needs transformers and torch to convert (the "mms" extra; update.cmd
installs it). The dilu voice is clean synthetic speech, so these numbers are
better than you will get; the real score is on your own recordings
(scripts/eval_stt.py). Licences: the small model is "for research and
educational purposes"; the medium one states none. Fine for your own study;
don't share the converted files.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# Downloads go next to the project (D:), not to C: (setup_windows.ps1 sets this too).
os.environ.setdefault("HF_HOME", str(ROOT.parent / ".cache" / "huggingface"))

from jarvis.config import load_settings  # noqa: E402
from jarvis.evaluation.wer import corpus_score, score  # noqa: E402
from jarvis.gpu import prepare_cuda  # noqa: E402
from jarvis.voice.audio_io import resample  # noqa: E402

# Checked on Hugging Face, 21 Oct 2026. Their own scores are on small or
# unnamed test sets, so only your recordings will tell which is better.
CANDIDATES = {
    "small": ("hlasith/whisper-sinhala-small",
              "whisper-small fine-tuned on about 10,000 Sinhala clips; its card reports CER 15% (on 10 clips). "
              "Download about 1 GB"),
    "medium": ("seniruk/whisper-medium-si-v2",
               "whisper-medium fine-tuned on a Sinhala dataset; its card reports WER 22%; about 3x slower. "
               "Download about 3 GB"),
}
BASE_TOKENIZER = "openai/whisper-small"          # all multilingual Whisper models share this vocabulary


def test_sentences(n_each: int = 6) -> list[str]:
    """The first few of each Sinhala test file: commands, study, conversation."""
    out = []
    for name in ("sentences_si.txt", "sentences_si_study.txt", "sentences_si_talk.txt"):
        path = ROOT / "eval" / name
        if path.is_file():
            lines = [ln.strip() for ln in path.read_text(encoding="utf-8-sig").splitlines()]
            out += [ln for ln in lines if ln and not ln.startswith("#")][:n_each]
    return out


def convert(repo: str, out: Path) -> None:
    from huggingface_hub import list_repo_files

    try:
        from ctranslate2.converters import TransformersConverter
        import transformers  # noqa: F401
        import torch  # noqa: F401
    except ImportError as exc:
        raise SystemExit(f"Converting needs transformers and torch ({exc}). Run: uv sync --extra mms") from exc

    files = set(list_repo_files(repo))
    if "config.json" not in files:
        raise SystemExit(f"{repo} isn't a transformers model (no config.json); pick another.")
    copy = [f for f in ("tokenizer.json", "preprocessor_config.json") if f in files]
    print(f"Downloading and converting {repo} (a few minutes the first time)...")
    t0 = time.perf_counter()
    TransformersConverter(repo, copy_files=copy).convert(str(out), quantization="int8_float16", force=True)
    if "tokenizer.json" not in copy:            # faster-whisper needs it next to the model
        from transformers import WhisperTokenizerFast
        with tempfile.TemporaryDirectory() as tmp:
            try:
                WhisperTokenizerFast.from_pretrained(repo).save_pretrained(tmp)
            except Exception:
                WhisperTokenizerFast.from_pretrained(BASE_TOKENIZER).save_pretrained(tmp)
            shutil.copy(Path(tmp) / "tokenizer.json", out / "tokenizer.json")
    print(f"Saved to {out} ({time.perf_counter() - t0:.0f} s)")


def check(folder: Path) -> None:
    from jarvis.voice.stt import load_whisper
    from jarvis.voice.tts import PiperTTS

    settings = load_settings(load_env=False)
    prepare_cuda()
    sentences = test_sentences()
    dilu_path = settings.path("tts.piper_dir", "models/piper") / "si_LK-dilu-medium.onnx"
    if not dilu_path.is_file():
        raise SystemExit(f"No dilu voice at {dilu_path}: run scripts/download_models.py first.")
    dilu = PiperTTS(dilu_path)
    clips = [resample(dilu.synthesize(s), dilu.sample_rate, 16000) for s in sentences]
    print(f"\n{len(clips)} Sinhala sentences read by the dilu voice "
          f"({sum(len(c) for c in clips) / 16000:.0f} s of speech).\n")

    today = str(settings.get("stt.model", "small"))
    results = {}
    for label, name in (("today: " + today, today), ("new: " + folder.name, str(folder))):
        model = load_whisper(name, settings.get("stt.device", "cuda"), settings.get("stt.compute_type", "int8_float16"))
        texts, ms = [], []
        for clip in clips:
            t0 = time.perf_counter()
            segments, _ = model.transcribe(clip, language="si", beam_size=1, vad_filter=True,
                                           temperature=(0.0, 0.4))
            texts.append(" ".join(s.text.strip() for s in segments).strip())
            ms.append((time.perf_counter() - t0) * 1000)
        total = corpus_score(zip(sentences, texts))
        results[label] = texts
        print(f"{label:<44} CER {total.cer:6.1%}  WER {total.wer:6.1%}  "
              f"{sorted(ms)[len(ms) // 2]:5.0f} ms per sentence")
        del model

    new = list(results.values())[1]
    print("\nWhat the new model wrote (correct text first):")
    for ref, hyp in list(zip(sentences, new))[:8]:
        print(f"  {ref}\n  {hyp}   (CER {score(ref, hyp).cer:.0%})\n")
    print("CER = share of letters wrong (lower is better). This voice is clean and synthetic;")
    print("your own voice will score worse. Test on it: record eval/sentences_si*.txt, then")
    print(f"  uv run python scripts/eval_stt.py --lang si --model small --model {folder.relative_to(ROOT).as_posix()}")
    print("\nTo use it, in config\\languages.toml under [si], set:")
    print(f'  stt_model = "{folder.relative_to(ROOT).as_posix()}"')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=list(CANDIDATES), default="small")
    ap.add_argument("--repo", help="any other Hugging Face Whisper fine-tune (transformers format)")
    ap.add_argument("--check", type=Path, metavar="FOLDER", help="skip the download; compare this folder")
    args = ap.parse_args()

    if args.check:
        folder = args.check if args.check.is_absolute() else ROOT / args.check
    else:
        repo = args.repo or CANDIDATES[args.model][0]
        if not args.repo:
            print(f"{repo}: {CANDIDATES[args.model][1]}")
        folder = ROOT / "models" / f"whisper-si-{args.model if not args.repo else repo.split('/')[-1]}-ct2"
        convert(repo, folder)
    check(folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
