"""One training run on Kaggle: upload the pairs, run the training script on the GPU, bring the result back.

    run = KaggleRun(api, "thilinabandara9876", work=Path("data/standin/kaggle"), harness=Path("kaggle/standin/..."))
    run.upload(train_pairs, first=True)      # a private dataset: <user>/jarvis-standin-pairs
    run.push(mode="train")                   # a private GPU script: <user>/jarvis-standin-training
    status = run.wait(timeout_s=5400)        # "complete", "error: ..." or "timeout"
    files = run.download(Path("models/standin/candidates/20261102-1700"))

`api` is kaggle's KaggleApi, signed in with KAGGLE_API_TOKEN (scripts/train_standin.py); the tests pass a
stand-in for it. Everything made on Kaggle is private to your account.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .pairs import Pair


class KaggleRun:
    def __init__(self, api: Any, user: str, dataset: str = "jarvis-standin-pairs",
                 kernel: str = "jarvis-standin-training", work: Path = Path("data/standin/kaggle"),
                 harness: Path = Path("kaggle/standin/train_standin.py"), say: Callable[[str], None] = print,
                 sleep: Callable[[float], None] | None = None):
        self.api, self.user, self.say = api, user, say
        self.sleep = sleep or (lambda s: time.sleep(s))
        self.dataset, self.kernel = f"{user}/{dataset}", f"{user}/{kernel}"
        self.work, self.harness = Path(work), Path(harness)

    def upload(self, pairs: list[Pair], first: bool) -> None:
        folder = self.work / "dataset"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "pairs.jsonl").write_text("".join(json.dumps(p.row(), ensure_ascii=False) + "\n" for p in pairs),
                                            encoding="utf-8")
        (folder / "dataset-metadata.json").write_text(json.dumps(
            {"title": "Jarvis standin pairs", "id": self.dataset, "licenses": [{"name": "other"}]}), encoding="utf-8")
        options = {"quiet": True, "convert_to_csv": False, "dir_mode": "skip"}
        if first:
            self.api.dataset_create_new(str(folder), public=False, **options)
        else:
            try:
                self.api.dataset_create_version(str(folder), version_notes=f"{len(pairs)} pairs", **options)
            except Exception as exc:  # noqa: BLE001 - deleted on the website? make it again
                if "404" not in str(exc) and "not found" not in str(exc).lower():
                    raise
                self.api.dataset_create_new(str(folder), public=False, **options)
        for _ in range(60):                                   # Kaggle processes a new version before it's usable
            try:
                status = str(self.api.dataset_status(self.dataset)).lower()
            except Exception:  # noqa: BLE001 - a brand-new dataset can be "not found" for a few seconds
                status = "pending"
            if "ready" in status:
                return
            if "error" in status:
                raise RuntimeError(f"Kaggle couldn't process the dataset ({status})")
            self.sleep(10)
        raise RuntimeError("the dataset wasn't ready after 10 minutes")

    def push(self, mode: str = "train", timeout_min: int = 90) -> None:
        folder = self.work / "kernel"
        folder.mkdir(parents=True, exist_ok=True)
        code = re.sub(r'^MODE = "\w+"', f'MODE = "{mode}"', self.harness.read_text(encoding="utf-8"), count=1,
                      flags=re.M)
        (folder / "train_standin.py").write_text(code, encoding="utf-8")
        slug = self.kernel.split("/", 1)[1]
        (folder / "kernel-metadata.json").write_text(json.dumps({
            "id": self.kernel, "title": slug.replace("-", " ").capitalize(), "code_file": "train_standin.py",
            "language": "python", "kernel_type": "script", "is_private": True, "enable_gpu": True,
            "enable_internet": True, "dataset_sources": [self.dataset], "competition_sources": [],
            "kernel_sources": [], "model_sources": []}), encoding="utf-8")
        self.api.kernels_push(str(folder), timeout=str(int(timeout_min * 60)))

    def wait(self, timeout_s: float = 5400, every_s: float = 30) -> str:
        """"complete", "error: <why>", or "timeout"."""
        waited, last = 0.0, ""
        while waited <= timeout_s:
            try:
                response = self.api.kernels_status(self.kernel)
            except Exception:  # noqa: BLE001 - just pushed, or the network blinked: ask again
                response, status = None, "no answer yet"
            else:
                status = str(getattr(response, "status", response)).lower()
            if status != last:
                self.say(f"Kaggle: {status.split('.')[-1]}")
                last = status
            if "complete" in status:
                return "complete"
            if "error" in status or "cancel" in status:
                why = getattr(response, "failure_message", "") or status
                return f"error: {why}"
            self.sleep(every_s)
            waited += every_s
        return "timeout"

    def download(self, dest: Path) -> list[str]:
        dest.mkdir(parents=True, exist_ok=True)
        files: list[str] = []
        token = None
        for _ in range(50):
            got, token = self.api.kernels_output(self.kernel, str(dest), force=True, quiet=True, page_token=token)
            files += list(got or [])
            if not token:
                break
        return files


def find_manifest(folder: Path) -> Path | None:
    """Where the run's manifest.json landed in the downloaded output."""
    found = sorted(Path(folder).rglob("manifest.json"), key=lambda p: len(p.parts))
    return found[0] if found else None


__all__ = ["KaggleRun", "find_manifest"]
