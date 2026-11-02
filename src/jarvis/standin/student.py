"""Version 2 of the stand-in: YOUR trained model (the student), loaded from what the Kaggle run made.

The Kaggle run (kaggle/standin/train_standin.py, your train_student) writes a folder with manifest.json:

    {"kind": "seq2seq", "path": "model", "base": "google/flan-t5-small", "max_new_tokens": 160, ...}
    {"kind": "causal",  "path": "model", "base": "HuggingFaceTB/SmolLM2-135M-Instruct", ...}

"path" is a Hugging Face model folder (save_pretrained of the model and its tokenizer). Jarvis loads it on
the CPU and asks it only when no language model answers (docs/TRAINING_STANDIN.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KINDS = ("seq2seq", "causal")


class Student:
    def __init__(self, folder: Path, manifest: dict, model: Any, tokenizer: Any):
        self.folder, self.manifest, self.model, self.tokenizer = folder, manifest, model, tokenizer
        self.kind = manifest["kind"]

    @classmethod
    def load(cls, folder: Path) -> Student | None:
        """The model in this folder, or None when there's none (or it isn't a model Jarvis can run)."""
        manifest = read_manifest(folder)
        if manifest.get("kind") not in KINDS:
            return None
        from transformers import AutoModelForCausalLM, AutoModelForSeq2SeqLM, AutoTokenizer
        path = folder / str(manifest.get("path", "model"))
        tokenizer = AutoTokenizer.from_pretrained(path)
        loader = AutoModelForSeq2SeqLM if manifest["kind"] == "seq2seq" else AutoModelForCausalLM
        model = loader.from_pretrained(path).eval()
        return cls(folder, manifest, model, tokenizer)

    def answer(self, question: str) -> str:
        import torch
        limit = int(self.manifest.get("max_new_tokens", 160))
        if self.kind == "seq2seq":
            prompt = str(self.manifest.get("prompt", "{question}")).format(question=question)
            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=256)
            with torch.no_grad():
                out = self.model.generate(**inputs, max_new_tokens=limit, num_beams=1, do_sample=False)
            return self.tokenizer.decode(out[0], skip_special_tokens=True).strip()
        if getattr(self.tokenizer, "chat_template", None):
            ids = self.tokenizer.apply_chat_template([{"role": "user", "content": question}],
                                                     add_generation_prompt=True, return_tensors="pt")
            inputs = {"input_ids": ids if not isinstance(ids, dict) else ids["input_ids"]}
        else:
            inputs = self.tokenizer(f"Question: {question}\nAnswer:", return_tensors="pt")
        start = inputs["input_ids"].shape[-1]
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=limit, do_sample=False,
                                      pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id)
        return self.tokenizer.decode(out[0][start:], skip_special_tokens=True).strip()


def read_manifest(folder: Path) -> dict:
    try:
        manifest = json.loads((Path(folder) / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return manifest if isinstance(manifest, dict) else {}


__all__ = ["KINDS", "Student", "read_manifest"]
