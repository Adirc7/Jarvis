"""Your stand-in model (standin/): saving timeless answers, the lookup, answering when the models can't,
test-before-use, and the Kaggle run (with a stand-in for Kaggle's API)."""

import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from conftest import FakeClient, FakeStream

from jarvis.standin import StandIn
from jarvis.standin.evaluate import better, score, similarity_with
from jarvis.standin.lookup import Lookup, TfidfChars
from jarvis.standin.pairs import PairLog, keepable, split

QA = [("what is entropy in thermodynamics", "Entropy measures how many ways a system's energy can be spread out."),
      ("explain the doppler effect", "The pitch changes because the source moves relative to you."),
      ("how does a transistor work", "A small current at the base controls a large one between collector and emitter."),
      ("what is a fourier series", "A way to write a periodic function as a sum of sines and cosines."),
      ("explain time dilation", "Moving clocks run slow as seen by a stationary observer.")]


def test_only_timeless_answers_are_kept(tmp_path):
    log = PairLog(tmp_path)
    assert log.add("what is entropy in thermodynamics", "It measures...", route="teach") is not None
    assert log.add("what's the latest news in Sri Lanka", "Today ...") is None          # wrong next week
    assert log.add("what time is it", "Half past three.") is None
    assert log.add("will it rain tomorrow in Kaduwela", "Probably.") is None
    assert log.add("open notepad please", "Opened.", route="command") is None              # an action
    assert log.add("hi", "Hello.") is None and log.add("/mood calm", "x") is None
    assert log.add("Good morning, Jarvis.", "Good morning, sir. It's late.", route="quick") is None
    assert keepable("explain time dilation", "...") and keepable("what is electric current", "...")
    with log.path.open("a", encoding="utf-8") as f:                               # saved before a rule changed
        f.write(json.dumps({"id": "x", "time": "t", "question": "Good morning, Jarvis.", "reply": "Morning.",
                            "route": "quick"}) + "\n")
    [pair] = log.read()
    assert pair.route == "teach" and json.loads(log.path.read_text().splitlines()[0])["question"].startswith("what is entropy")


def test_the_newest_pairs_are_kept_back_for_the_test(tmp_path):
    log = PairLog(tmp_path)
    start = datetime(2026, 11, 2, 9, 0)
    for i in range(40):
        log.add(f"question number {i} about physics", f"answer {i}", now=start + timedelta(minutes=i))
    train, held = split(log.read(), 0.15)
    assert len(held) == 6 and len(train) == 34 and max(p.time for p in train) < min(p.time for p in held)
    assert split(log.read()[:8], 0.15)[1] == []                                    # too few to test on yet


def make_lookup(tmp_path):
    log = PairLog(tmp_path)
    for q, a in QA:
        log.add(q, a)
    return Lookup(log.read(), TfidfChars())


def test_the_lookup_answers_the_same_question_and_declines_a_new_one(tmp_path):
    lookup = make_lookup(tmp_path)
    match = lookup.answer("What is entropy in thermodynamics?")
    assert match is not None and match.pair.reply.startswith("Entropy") and match.score > 0.9
    assert lookup.answer("whats entropy in thermodynamic") is not None                    # typos
    assert lookup.answer("who won the cricket match") is None                             # only a guess: no
    assert lookup.answer("what is heat capacity") is None                                 # close letters, not the same
    lookup.add([next(iter(PairLog(tmp_path).read()))])
    assert len(lookup.pairs) == 6


def test_a_new_model_is_used_only_if_it_beats_the_current_one(tmp_path):
    lookup = make_lookup(tmp_path)
    held = PairLog(tmp_path).read()
    similar = similarity_with(TfidfChars())
    def current(q):
        m = lookup.answer(q)
        return m.pair.reply if m else None
    exact = score("lookup", current, held, similar)
    assert exact.coverage == 1.0 and exact.overall == pytest.approx(1.0, abs=0.01)
    silent = score("silent", lambda q: None, held, similar)
    wrong = score("wrong", lambda q: "Bananas are yellow.", held, similar)
    assert silent.overall == 0 and wrong.overall < 0.2 and wrong.coverage == 1.0
    assert better(exact, wrong) and not better(wrong, exact) and not better(exact, exact)   # a tie keeps the old


# ---- in Jarvis -----------------------------------------------------------------------------------------
class SlowStream(FakeStream):
    def __init__(self, pieces, delay):
        super().__init__(pieces)
        self.delay = delay

    async def _gen(self):
        await asyncio.sleep(self.delay)
        async for piece in super()._gen():
            yield piece


class SlowClient(FakeClient):
    def __init__(self, pieces, delay):
        super().__init__(pieces)
        self.delay = delay

    async def create(self, model, messages, stream=False, **kwargs):
        self.calls += 1
        self.last_stream = SlowStream(self.pieces, self.delay)
        return self.last_stream


def standin_app(settings, client, saved=QA):
    from test_llm_and_app import make_app
    settings.raw["standin"].update(save=True, after_s=0.3)
    app, out = make_app(settings, client)
    for q, a in saved:
        app.standin.log.add(q, a)
    app.standin.prepare()
    return app, out


async def test_unreachable_models_get_the_stand_in_and_jarvis_says_so(settings):
    app, _ = standin_app(settings, FakeClient(error=ConnectionError("offline")))
    reply = await app.handle_text("what is entropy in thermodynamics?")
    assert reply.startswith("I can't reach the language models, so this is from what I said before.")
    assert "Entropy measures" in reply
    assert "can't reach any language model" in await app.handle_text("who won the cricket match yesterday")


async def test_a_weak_connection_gets_the_stand_in_after_a_few_seconds(settings):
    client = SlowClient(["Live answer."], delay=2.0)
    app, _ = standin_app(settings, client)
    reply = await app.handle_text("explain the doppler effect")
    assert reply.startswith("The connection's slow, so this is from what I said before.") and "pitch" in reply
    assert client.last_stream is not None
    fast = SlowClient(["Live answer."], delay=0.0)
    app2, _ = standin_app(settings, fast)
    assert await app2.handle_text("explain the doppler effect") == "Live answer."          # no race when quick
    nothing = SlowClient(["Live, but slow."], delay=0.6)
    app3, _ = standin_app(settings, nothing)
    assert await app3.handle_text("tell me a joke about cats") == "Live, but slow."        # no match: it waits


async def test_timeless_replies_are_saved_and_the_lookup_learns_them(settings):
    app, _ = standin_app(settings, FakeClient(["A vector field assigns a vector to each point."]), saved=[])
    await app.handle_text("what is a vector field")
    await asyncio.sleep(0.2)                                       # saved on the stand-in's thread
    [pair] = app.standin.log.read()
    assert pair.question == "what is a vector field" and pair.reply.startswith("A vector field")
    assert app.standin.answer("What is a vector field?").text.startswith("A vector field")
    settings.raw["standin"]["save"] = False
    from test_llm_and_app import make_app
    off, _ = make_app(settings, FakeClient(["x"]))
    assert off.standin is not None and not off.standin.save


async def test_the_standin_command_says_what_it_knows(settings):
    app, out = standin_app(settings, FakeClient(["x"]))
    await app._command("/standin")
    assert "the lookup, over 5 saved answers (tfidf)" in out[-1] and "Saving is on" in out[-1]
    assert "No Kaggle run yet" in out[-1]


async def test_wikipedia_and_maths_answers_are_kept_but_news_never(settings, tmp_path):
    from test_knowledge import TwoStep, make_info

    from jarvis.agent.llm import FallbackLLM, Provider
    from jarvis.app import App
    from jarvis.telemetry import Telemetry
    settings.raw["standin"]["save"] = True
    info, _ = make_info(tmp_path)
    model = TwoStep("check_maths", json.dumps({"task": "differentiate", "expression": "x^3"}),
                    ["The derivative of x cubed is 3 x squared."])
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", model)]),
              out=lambda *a, **k: None, info=info)
    await app.handle_text("differentiate x cubed for me")
    model.tool, model.arguments, model.words = "get_news", '{"theme": "space"}', ["ISRO launched a satellite."]
    await app.handle_text("anything happening in space")
    await asyncio.sleep(0.2)
    assert [p.question for p in app.standin.log.read()] == ["differentiate x cubed for me"]
