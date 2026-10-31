"""The empathy learner's frame (empathy/): feedback, counts, the coach in Jarvis, the simulator."""

import json
import random

import pytest
from conftest import FakeClient

from jarvis.agent.llm import FallbackLLM, Provider
from jarvis.app import App
from jarvis.empathy import (
    EmpathyCoach,
    EmpathyStore,
    FixedLearner,
    feedback_from,
    load_learner,
)
from jarvis.telemetry import Telemetry


# ---- what counts as feedback ------------------------------------------------------------------
@pytest.mark.parametrize("text, reward, why", [
    ("thanks, that helped", 1.0, "thanks"),
    ("ස්තූතියි", 1.0, "ස්තූතියි"),
    ("niyamai machan", 1.0, "niyamai"),
    ("too long, get to the point", 0.0, "too long"),
    ("that's not what I asked", 0.0, "that's not what i asked"),
])
def test_words_after_a_reply_are_feedback_on_its_mode(text, reward, why):
    [fb] = feedback_from(text, last_mode="balanced", seconds_since_reply=10)
    assert (fb.mode, fb.reward, fb.weight, fb.why) == ("balanced", reward, 1.0, why)


def test_other_signals_and_what_isnt_feedback():
    assert feedback_from("ok", last_mode="balanced", seconds_since_reply=5, interrupted=True)[0].weight == 0.5
    [fb] = feedback_from("how do I integrate x squared", last_mode="logical", seconds_since_reply=30,
                         last_question="how do i integrate x squared?")
    assert (fb.why, fb.reward) == ("repeated", 0.0)                      # asked again: the reply missed
    [fb] = feedback_from("be gentler", last_mode="logical", seconds_since_reply=5, asked_mode="supportive")
    assert (fb.mode, fb.reward, fb.why) == ("logical", 0.0, "asked for supportive")
    assert feedback_from("back to normal", last_mode="balanced", seconds_since_reply=5, asked_mode="balanced") == []
    long = "thanks for the help earlier, now can you explain how the Fourier transform of a Gaussian works in detail"
    assert feedback_from(long, last_mode="balanced", seconds_since_reply=5) == []   # a new question, not feedback
    assert feedback_from("thanks", last_mode="balanced", seconds_since_reply=3600) == []   # too long after
    assert feedback_from("thanks", last_mode=None) == []                                  # no reply yet


# ---- the counts --------------------------------------------------------------------------------
def test_counts_are_kept_with_a_log_and_never_the_words(tmp_path):
    store = EmpathyStore.load(tmp_path / "empathy.json")
    for fb in feedback_from("thanks", last_mode="logical", seconds_since_reply=1) + \
            feedback_from("ok", last_mode="logical", seconds_since_reply=1, interrupted=True):
        store.add(fb)
    store.save()
    again = EmpathyStore.load(tmp_path / "empathy.json")
    assert again.for_context("all") == {"logical": (1.0, 0.5)}
    log = (tmp_path / "empathy-log.jsonl").read_text().splitlines()
    assert [json.loads(line)["why"] for line in log] == ["thanks", "interrupted"]
    assert "ok" not in (tmp_path / "empathy.json").read_text()
    (tmp_path / "broken.json").write_text("{nope")
    assert EmpathyStore.load(tmp_path / "broken.json").counts == {}


# ---- the coach: limits, distress, your choice first ----------------------------------------------
class Always:
    def __init__(self, mode):
        self.mode, self.name, self.calls = mode, f"always {mode}", 0

    def choose(self, modes, counts, rng):
        self.calls += 1
        return self.mode


def coach(learner, allowed=("logical", "balanced", "supportive"), every=3):
    return EmpathyCoach(EmpathyStore(None), learner, list(allowed), rechoose_every=every, rng=random.Random(1),
                        clock=lambda: 100.0)


def test_the_coach_asks_the_learner_now_and_then_within_limits():
    learner = Always("logical")
    c = coach(learner)
    assert c.mode_for("hi", "balanced") == ("logical", "learner")
    c.replied("hi", "logical")
    assert c.mode_for("and then?", "logical") == ("logical", "kept") and learner.calls == 1
    c.after_user_turn("too long")                                       # feedback: choose again
    assert c.mode_for("next", "logical")[1] == "learner" and learner.calls == 2
    outside = coach(Always("sarcastic"), allowed=("balanced", "supportive"))
    assert outside.mode_for("hi", "balanced") == ("balanced", "learner")       # can't leave your limits


def test_distress_and_your_own_choice_come_first():
    c = coach(Always("logical"))
    assert c.mode_for("I can't take it anymore", "logical") == ("supportive", "distress")
    c.after_user_turn("be gentler", asked_mode="supportive")
    assert c.mode_for("explain entropy", "supportive") == ("supportive", "manual")


def test_no_learner_file_means_the_fixed_mode_with_a_note():
    learner, note = load_learner("thompson", "balanced")
    try:
        import jarvis.empathy.thompson  # noqa: F401
        assert note == ""                                                    # yours exists
    except ImportError:
        assert isinstance(learner, FixedLearner) and "thompson.py" in note
    assert load_learner("fixed")[0].choose(["logical", "balanced"], {}, random.Random()) == "balanced"


# ---- in Jarvis --------------------------------------------------------------------------------
class Capture(Telemetry):
    def __init__(self):
        super().__init__(None)
        self.events = []

    def log(self, event, **fields):
        self.events.append({"event": event, **fields})


async def test_jarvis_counts_feedback_and_lets_the_learner_choose(settings):
    tel = Capture()
    app = App(settings, tel, llm=FallbackLLM([Provider("groq", "m", FakeClient(["Sure."]))]), out=lambda *a, **k: None)
    app.coach.learner = Always("logical")
    await app.handle_text("explain recursion")
    assert app.state.empathy == "logical"
    assert {"event": "empathy_changed", "old": "balanced", "new": "logical", "source": "learner"} in tel.events
    await app.handle_text("too long")
    fb = next(e for e in tel.events if e["event"] == "empathy_feedback")
    assert (fb["mode"], fb["reward"], fb["why"]) == ("logical", 0.0, "too long")
    assert app.coach.store.for_context("all")["logical"] == (0.0, 1.0)
    await app.handle_text("be gentler")                                  # yours wins, for the session
    await app.handle_text("explain recursion again")
    assert app.state.empathy == "supportive" and app.coach.manual == "supportive"


async def test_a_mode_set_by_command_isnt_overruled(settings):
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", FakeClient(["Ok."]))]),
              out=lambda *a, **k: None)
    app.coach.learner = Always("logical")
    assert await app._command("/empathy supportive")
    await app.handle_text("help me with this proof")
    assert app.state.empathy == "supportive"
    lines = []
    app.out = lambda *a, **k: lines.append(" ".join(map(str, a)))
    await app._command("/empathy stats")
    assert "learner: always logical" in lines[-1]


def test_the_simulator_runs_and_writes_its_report(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("simulate_empathy", "scripts/simulate_empathy.py")
    sim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sim)
    assert sim.main(["--turns", "40", "--runs", "3", "--out", str(tmp_path / "sim")]) == 0
    table = (tmp_path / "sim.md").read_text()
    assert "| wants-logical | 12.0 ± 0.0 |" in table                     # fixed: 40 x (0.8 - 0.5)
    assert (tmp_path / "sim.svg").read_text().startswith("<svg")
    assert sim.run(sim.FixedLearner("logical"), "wants-logical", 50, 1)[-1] == 0.0   # the best mode: no regret
