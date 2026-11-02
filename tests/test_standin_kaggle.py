"""Training the stand-in on Kaggle (scripts/train_standin.py) with a stand-in for Kaggle's API: what's
uploaded (only training pairs, privately), what runs (the GPU script, in which mode), and the test before
use (a new model is used only when it's better)."""

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.standin.pairs import PairLog

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("train_standin", ROOT / "scripts" / "train_standin.py")
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)

TOPICS = ["entropy", "the doppler effect", "a transistor", "a fourier series", "time dilation", "a capacitor",
          "an eigenvalue", "a vector field", "the gradient", "a laplace transform", "an integral", "a derivative",
          "resonance", "a black body", "a photon", "an electric field", "a magnetic flux", "a wave function",
          "the uncertainty principle", "a matrix", "a determinant", "a limit", "a series", "a sequence",
          "the divergence", "the curl", "a lens", "refraction", "diffraction", "interference", "momentum", "torque",
          "a pendulum", "an orbit", "gravity", "a spring", "heat capacity", "a gas law", "pressure", "density"]


def harness(mode: str, uploaded: Path, out: Path):
    """Run kaggle/standin/train_standin.py here, as Kaggle would, with the uploaded pairs."""
    spec = importlib.util.spec_from_file_location("harness", ROOT / "kaggle" / "standin" / "train_standin.py")
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    h.MODE, h.OUT = mode, out / "standin"
    h.load_pairs = lambda: [json.loads(x) for x in uploaded.read_text(encoding="utf-8").splitlines() if x.strip()]
    h.main()


class FakeKaggle:
    def __init__(self, outputs=None, statuses=("KernelWorkerStatus.QUEUED", "KernelWorkerStatus.RUNNING",
                                               "KernelWorkerStatus.COMPLETE")):
        self.calls, self.statuses, self.outputs = [], list(statuses), outputs
        self.meta = self.code = self.data_folder = None

    def dataset_create_new(self, folder, public, **kw):
        self.calls.append(("new", public))
        self.data_folder = Path(folder)

    def dataset_create_version(self, folder, version_notes, **kw):
        self.calls.append(("version", version_notes))
        self.data_folder = Path(folder)

    def dataset_status(self, ref):
        return "ready"

    def kernels_push(self, folder, timeout=None):
        self.meta = json.loads((Path(folder) / "kernel-metadata.json").read_text())
        self.code = (Path(folder) / "train_standin.py").read_text()
        self.calls.append(("push", timeout))

    def kernels_status(self, ref):
        return SimpleNamespace(status=self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0],
                               failure_message="")

    def kernels_output(self, ref, path, force=False, quiet=True, page_token=None):
        mode = "check" if 'MODE = "check"' in self.code else "train"
        if self.outputs:
            self.outputs(Path(path))
        else:
            harness(mode, self.data_folder / "pairs.jsonl", Path(path))
        return [str(p) for p in Path(path).rglob("*") if p.is_file()], None


def setup(settings, tmp_path, n=40):
    settings.raw["standin"].update(save=True, results=str(tmp_path / "standin_results.md"))
    log = PairLog(Path(settings.raw["standin"]["data_dir"]))
    start = datetime(2026, 11, 2, 9, 0)
    for i in range(n):
        log.add(f"what is {TOPICS[i % len(TOPICS)]}", f"{TOPICS[i % len(TOPICS)].capitalize()} is explained here, "
                f"answer {i}.", route="teach", now=start + timedelta(minutes=i))
    return log


def run(settings, api, *argv):
    said = []
    code = ts.main(list(argv), api_factory=lambda: (api, "thilinabandara9876"), say=said.append, settings=settings)
    return code, "\n".join(said)


def test_a_pipeline_check_uploads_privately_and_runs_on_the_gpu(settings, tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    setup(settings, tmp_path)
    api = FakeKaggle()
    code, said = run(settings, api, "--check")
    assert code == 0 and "the pipeline works: 34 pairs reached the GPU" in said
    assert api.calls[0] == ("new", False)                                   # a new, private dataset
    uploaded = (api.data_folder / "pairs.jsonl").read_text().splitlines()
    assert len(uploaded) == 34                                              # the newest 6 never leave the laptop
    assert api.meta["is_private"] and api.meta["enable_gpu"] and api.meta["kernel_type"] == "script"
    assert api.meta["dataset_sources"] == ["thilinabandara9876/jarvis-standin-pairs"]
    assert api.meta["id"] == "thilinabandara9876/jarvis-standin-training"
    assert 'MODE = "check"' in api.code
    state = json.loads((Path(settings.raw["general"]["state_dir"]) / "standin.json").read_text())
    assert state["dataset_made"] and state["uploaded"] == 0 and "pipeline works" in state["last_result"]
    code, said = run(settings, FakeKaggle(), "--check")
    assert code == 0                                                         # the second time: a new version


def test_until_train_student_is_written_a_run_says_so(settings, tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    setup(settings, tmp_path)
    code, said = run(settings, FakeKaggle())
    assert code == 0 and "your train_student isn't written yet" in said


def test_automatic_runs_wait_for_enough_new_pairs(settings, tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    setup(settings, tmp_path, n=20)
    settings.raw["standin"].update(auto_train=True, min_new_pairs=50)
    asked, said = [], []
    code = ts.main(["--auto"], api_factory=lambda: asked.append(1), say=said.append, settings=settings)
    assert code == 0 and asked == [] and "15 new pairs" in said[-1]           # not enough, Kaggle untouched
    settings.raw["standin"]["min_new_pairs"] = 10
    code = ts.main(["--auto"], api_factory=lambda: asked.append(1), say=said.append, settings=settings)
    assert code == 0 and asked == [] and "train_student isn't written yet" in said[-1]   # no wasted GPU runs
    settings.raw["standin"]["auto_train"] = False
    assert ts.main(["--auto"], api_factory=lambda: asked.append(1), say=lambda s: None, settings=settings) == 0
    assert asked == []


def test_a_failed_run_is_reported(settings, tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    setup(settings, tmp_path)
    code, said = run(settings, FakeKaggle(statuses=["KernelWorkerStatus.ERROR"]))
    assert code == 1 and "didn't finish: error" in said


def tiny_causal(folder: Path, manifest: dict):
    """A tiny random chat model, so the real loading and answering code runs."""
    pytest.importorskip("transformers")
    from tokenizers import Tokenizer, models, pre_tokenizers
    from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast
    words = "question answer what is the a of".split()
    vocab = {"[UNK]": 0, "[EOS]": 1, **{w: i + 2 for i, w in enumerate(words)}}
    tok = Tokenizer(models.WordLevel(vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    fast = PreTrainedTokenizerFast(tokenizer_object=tok, unk_token="[UNK]", eos_token="[EOS]", pad_token="[EOS]")
    model_dir = folder / "standin" / "model"
    fast.save_pretrained(model_dir)
    GPT2LMHeadModel(GPT2Config(vocab_size=len(vocab), n_positions=128, n_embd=8, n_layer=1, n_head=1)
                    ).save_pretrained(model_dir)
    (folder / "standin" / "manifest.json").write_text(json.dumps(manifest))


def test_a_new_model_is_used_only_when_its_better_on_conversations_it_never_saw(settings, tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    log = setup(settings, tmp_path)
    truth = {p.question: p.reply for p in log.read()}
    made = {"kind": "causal", "path": "model", "base": "tiny-test-gpt2", "max_new_tokens": 3}
    from jarvis.standin.student import Student
    real = Student.answer
    out = []

    def checked(self, question):
        out.append(real(self, question))                  # the real model runs, then answers as asked below
        return answers(question)
    monkeypatch.setattr(Student, "answer", checked)

    answers = lambda q: "Bananas are yellow and grow in bunches."      # noqa: E731 - a bad student
    code, said = run(settings, FakeKaggle(outputs=lambda p: tiny_causal(p, made)))
    models = Path(settings.raw["standin"]["model_dir"])
    assert code == 0 and "not better on the test: not used" in said and not (models / "current").exists()
    assert out and all(isinstance(x, str) for x in out)
    answers = lambda q: truth[q]                                        # noqa: E731 - a perfect student
    code, said = run(settings, FakeKaggle(outputs=lambda p: tiny_causal(p, made)))
    assert code == 0 and "in use from Jarvis's next start" in said
    assert (models / "current" / "manifest.json").is_file()
    report = Path(settings.raw["standin"]["results"]).read_text()
    assert "| the lookup | 6 |" in report and "| the new model (tiny-test-gpt2) | 6 |" in report
