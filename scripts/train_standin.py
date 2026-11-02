"""Train your stand-in model on Kaggle's free GPU, test it, and use it only if it's better.

    uv run python scripts/train_standin.py            # a run now
    uv run python scripts/train_standin.py --check    # only check the pipeline (a few minutes of GPU)
    uv run python scripts/train_standin.py --auto     # what Jarvis runs when it closes ([standin] auto_train)

1. Reads the saved pairs (data/standin/pairs.jsonl) and keeps the newest back ([standin] held_out): they
   never leave the laptop, so the test is on conversations the model never saw.
2. Uploads the rest to a private Kaggle dataset, and runs kaggle/standin/train_standin.py on a private GPU
   notebook (your train_student does the training: docs/TRAINING_STANDIN.md).
3. Downloads what it made to models/standin/candidates/<time>/.
4. Tests it against what Jarvis uses now (the lookup, or the student adopted last time) on the held-out
   pairs; only a better one goes to models/standin/current/, which Jarvis loads at its next start.
   The scores go to docs/standin_results.md.

Needs KAGGLE_API_TOKEN in .env (scripts/check_kaggle.cmd checks it); never prints it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.config import load_dotenv, load_settings  # noqa: E402
from jarvis.standin import reply_for  # noqa: E402
from jarvis.standin.evaluate import better, report, score, similarity_with  # noqa: E402
from jarvis.standin.kaggle_run import KaggleRun, find_manifest  # noqa: E402
from jarvis.standin.lookup import Lookup, make_encoder  # noqa: E402
from jarvis.standin.pairs import Pair, PairLog, split  # noqa: E402
from jarvis.standin.student import KINDS, Student  # noqa: E402


def read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1), encoding="utf-8")


def kaggle_api():
    """KaggleApi signed in with the token only (no kaggle.json fallback), and the username."""
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip().strip("'\"")
    if not token:
        raise SystemExit("No KAGGLE_API_TOKEN in .env (scripts/check_kaggle.cmd explains).")
    os.environ["KAGGLE_API_TOKEN"] = token
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    if not api._authenticate_with_access_token():
        raise SystemExit("Kaggle doesn't accept the token in .env; scripts/check_kaggle.cmd says more.")
    api._authenticated = True
    return api, api.config_values.get(api.CONFIG_NAME_USER, "")


def test_before_use(candidate_dir: Path, train: list[Pair], held: list[Pair], current_dir: Path, encoder_name: str,
                    student_min: float | None = None, say=print) -> tuple[bool, str]:
    """The candidate against what Jarvis uses now, on the held-out pairs. (adopt?, the report)"""
    if not held:
        return False, "Too few saved pairs to test on yet, so the new model isn't used."
    encoder = make_encoder(encoder_name)
    lookup = Lookup(train, encoder)
    floor = student_min if student_min is not None else getattr(encoder, "student_threshold", lookup.min_similarity)
    similar = similarity_with(encoder)

    def answers(student):
        def answer(question: str) -> str | None:
            got = reply_for(question, lookup, student, floor)
            return got.text if got else None
        return answer

    say(f"Testing on {len(held)} conversations it never saw...")
    scores = [score("the lookup", answers(None), held, similar)]
    current = Student.load(current_dir) if current_dir.is_dir() else None
    if current is not None:
        scores.append(score(f"your current model ({current.manifest.get('base', '?')})", answers(current), held,
                            similar))
    candidate = Student.load(candidate_dir)
    scores.append(score(f"the new model ({candidate.manifest.get('base', '?')})", answers(candidate), held, similar))
    best = max(scores[:-1], key=lambda s: s.overall)
    adopt = better(scores[-1], best)
    verdict = (f"The new model is better than {best.name} ({scores[-1].overall:.3f} against {best.overall:.3f}), "
               "so Jarvis uses it from his next start." if adopt else
               f"The new model isn't better than {best.name} ({scores[-1].overall:.3f} against {best.overall:.3f}), "
               "so Jarvis keeps what he has.")
    return adopt, report(scores, verdict)


def adopt(candidate_dir: Path, model_dir: Path) -> None:
    current, previous = model_dir / "current", model_dir / "previous"
    if previous.exists():
        shutil.rmtree(previous)
    if current.exists():
        current.rename(previous)
    shutil.copytree(candidate_dir, current)


def main(argv=None, api_factory=kaggle_api, say=print, settings=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="only check the pipeline: upload, GPU run, download")
    ap.add_argument("--auto", action="store_true", help="only when there's enough new to learn from")
    ap.add_argument("--now", action="store_true", help="(from Jarvis's /standin train: the same as no option)")
    args = ap.parse_args(argv)
    if settings is None:
        settings = load_settings()
        load_dotenv(ROOT / ".env")
    get = lambda key, default: settings.get(f"standin.{key}", default)   # noqa: E731
    state_path = settings.path("general.state_dir", "state") / "standin.json"
    state = read_state(state_path)
    pairs = PairLog(settings.path("standin.data_dir", "data/standin")).read()
    train, held = split(pairs, float(get("held_out", 0.15)))

    if args.auto:
        if not (get("save", False) and get("auto_train", False)):
            return 0
        new = len(train) - int(state.get("uploaded", 0))
        if new < int(get("min_new_pairs", 50)):
            say(f"{new} new pairs since the last run; waiting for {get('min_new_pairs', 50)}.")
            return 0
        if "isn't written yet" in (ROOT / "kaggle" / "standin" / "train_standin.py").read_text(encoding="utf-8"):
            say("train_student isn't written yet (kaggle/standin/train_standin.py): no automatic run until it is.")
            return 0
        last = state.get("last_run")
        if last and datetime.now() - datetime.fromisoformat(last) < timedelta(hours=float(get("every_hours", 20))):  # noqa: DTZ005
            say(f"The last run was at {last}; at most one every {get('every_hours', 20)} hours.")
            return 0
    if not train:
        if not args.check:
            say("No saved pairs yet: turn on [standin] save and talk to Jarvis (docs/TRAINING_STANDIN.md).")
            return 1
        train = [Pair("check", datetime.now().isoformat(timespec="seconds"), "pipeline check", "ok")]  # noqa: DTZ005

    api, user = api_factory()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005
    run = KaggleRun(api, user, str(get("kaggle_dataset", "jarvis-standin-pairs")),
                    str(get("kaggle_kernel", "jarvis-standin-training")),
                    work=settings.path("standin.data_dir", "data/standin") / "kaggle",
                    harness=ROOT / "kaggle" / "standin" / "train_standin.py", say=say)
    say(f"Signed in to Kaggle as {user}. Uploading {len(train)} pairs to your private dataset {run.dataset} "
        f"({len(held)} kept here for the test)...")
    run.upload(train, first=not state.get("dataset_made"))
    state.update(dataset_made=True, uploaded=len(train) if not args.check else state.get("uploaded", 0))
    save_state(state_path, state)
    mode = "check" if args.check else "train"
    say(f"Running {run.kernel} on Kaggle's GPU ({mode}); this takes a few minutes...")
    run.push(mode, int(get("timeout_min", 90)))
    status = run.wait(timeout_s=float(get("timeout_min", 90)) * 60 + 600)
    state.update(last_run=datetime.now().isoformat(timespec="seconds"))  # noqa: DTZ005
    if status != "complete":
        state["last_result"] = f"the Kaggle run ended with {status}"
        save_state(state_path, state)
        say(f"The Kaggle run didn't finish: {status}. Its log is on kaggle.com under Code, {run.kernel}.")
        return 1
    model_dir = settings.path("standin.model_dir", "models/standin")
    dest = model_dir / "candidates" / stamp
    run.download(dest)
    manifest_path = find_manifest(dest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path else {}
    kind = manifest.get("kind")
    if kind == "check":
        result = f"the pipeline works: {manifest.get('pairs')} pairs reached the GPU ({manifest.get('gpu')}) and back"
    elif kind == "none":
        result = "the pipeline works; your train_student isn't written yet (kaggle/standin/train_standin.py)"
    elif kind in KINDS:
        adopted, table = test_before_use(manifest_path.parent, train, held, model_dir / "current",
                                         str(get("encoder", "tfidf")), get("student_min_similarity", None), say)
        if adopted:
            adopt(manifest_path.parent, model_dir)
        settings.path("standin.results", "docs/standin_results.md").write_text(
            f"# Stand-in model: test before use\n\nRun {stamp}, made by `scripts/train_standin.py`. Held-out: the "
            f"newest {len(held)} saved conversations, never uploaded.\n\n{table}\n", encoding="utf-8")
        say(table)
        result = ("a new model, better on the test: in use from Jarvis's next start" if adopted
                  else "a new model, not better on the test: not used")
    else:
        result = "the run finished, but no manifest.json came back"
    state["last_result"] = result
    save_state(state_path, state)
    say(f"Done: {result}.")
    return 0 if kind in ("check", "none", *KINDS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
