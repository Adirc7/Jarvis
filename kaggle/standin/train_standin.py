"""Jarvis stand-in training, on Kaggle's free GPU. Pushed and run by scripts/train_standin.py.

In:  pairs.jsonl, from your private Kaggle dataset: questions you asked Jarvis and the language models'
     answers. Only the training pairs: the newest ones stay on the laptop, to test what this makes.
Out: /kaggle/working/standin/manifest.json, and your model in /kaggle/working/standin/model/.

YOUR PART is train_student() below (docs/TRAINING_STANDIN.md, step 3). Until it's written, a run checks the
pipeline: the data arrived, the GPU is there, and the result comes back to the laptop.
"""

import glob
import json
import platform
import time
from pathlib import Path

MODE = "train"                        # scripts/train_standin.py --check sets "check": only test the pipeline
OUT = Path("/kaggle/working/standin")


def load_pairs() -> list[dict]:
    files = sorted(glob.glob("/kaggle/input/**/pairs.jsonl", recursive=True))
    if not files:
        raise SystemExit("pairs.jsonl isn't under /kaggle/input: is the dataset attached to this notebook?")
    lines = Path(files[0]).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def gpu_name() -> str:
    try:
        import torch
        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none"
    except Exception as exc:  # noqa: BLE001
        return f"unknown ({type(exc).__name__})"


def train_student(pairs: list[dict], out_dir: Path) -> dict:
    """YOUR PART: train a small model to answer the way the language models did, and save it.

    pairs: [{"id", "question", "reply", "lang" ("en", "si", ...), "route", "time"}, ...], oldest first.
    Save the model and its tokenizer with save_pretrained into out_dir / "model", and return the manifest:
        {"kind": "seq2seq" or "causal", "path": "model", "base": "<the model you started from>",
         "max_new_tokens": 160, ...anything worth reporting: epochs, validation loss, ...}
    For seq2seq you may add "prompt": "answer: {question}" if you trained with a prefix.

    The plan (details and theory in docs/TRAINING_STANDIN.md: this is knowledge distillation, a small
    student learning from a big teacher's answers):
      1. A small base model: google/flan-t5-small (seq2seq, English, quick on the laptop's CPU), or
         google/mt5-small (seq2seq, Sinhala too), or a small chat model (causal), such as
         HuggingFaceTB/SmolLM2-135M-Instruct.
      2. The newest 10% of these pairs for validation (by "time"): never train on them.
      3. Tokenize: the question is the input, the reply the target (cut replies at about 256 tokens).
      4. Fine-tune: Seq2SeqTrainer (or Trainer for causal), a few epochs, learning rate about 3e-4 for T5
         (5e-5 for a causal model), fp16 on the GPU; keep the epoch with the lowest validation loss.
      5. model.save_pretrained(out_dir / "model") and tokenizer.save_pretrained(out_dir / "model").
      6. Return the manifest.
    """
    raise NotImplementedError("train_student isn't written yet")


def main() -> None:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = load_pairs()
    info = {"mode": MODE, "pairs": len(pairs), "gpu": gpu_name(), "python": platform.python_version(),
            "trained_ids": [p.get("id", "") for p in pairs]}
    print(f"{len(pairs)} pairs; GPU: {info['gpu']}; mode: {MODE}")
    if MODE == "check":
        manifest = {"kind": "check", **info}
    else:
        try:
            made = train_student(pairs, OUT)
            manifest = {**info, **made}
        except NotImplementedError as exc:
            manifest = {"kind": "none", "why": str(exc), **info}
    manifest["seconds"] = round(time.time() - start, 1)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "trained_ids"}, indent=1))


if __name__ == "__main__":
    main()
