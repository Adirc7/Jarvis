"""Routing requests to models (agent/router.py) and the routed, rate-limit-aware LLM (agent/llm.py)."""

from types import SimpleNamespace

import pytest
from conftest import FakeClient

from jarvis.agent.llm import (
    FallbackLLM,
    LLMUnavailable,
    Provider,
    ThinkFilter,
    rate_limit_wait,
)
from jarvis.agent.router import (
    INTENT_ROUTE,
    ROUTES,
    IntentRouter,
    KeywordRouter,
    route_for_intent,
)
from jarvis.app import App
from jarvis.config import ProviderConfig
from jarvis.intents.patterns import LANGUAGES
from jarvis.telemetry import Telemetry


async def collect(agen):
    return "".join([x async for x in agen])


@pytest.mark.parametrize("text, lang, route", [
    ("solve this integral step by step", "en", "maths"),
    ("me equation eka solve karala denna", "si-Latn", "maths"),
    ("මේ ගණන විසඳන්න", "si", "maths"),
    ("what is 12 * 7 + 3", "en", "maths"),
    ("mata answer eka 2.5 J awa, eka harida", "si-Latn", "maths"),
    ("write python code for the Runge-Kutta method", "en", "code"),
    ("mata index error ekak enawa, fix karanna", "si-Latn", "code"),
    ("explain the Fourier transform", "en", "teach"),
    ("fourier series eka gana podi explanation ekak denna", "si-Latn", "teach"),
    ("ෆූරියර් සීරීස් එක කියන්නේ මොකක්ද?", "si", "teach"),
    ("pmat 21272 exam ekata padam karanna plan ekak hadala denna", "si-Latn", "teach"),
    ("summarize this PDF", "en", "long"),
    ("what do you think is the meaning of life", "en", "talk"),
    ("mata godak mahansiyi", "si-Latn", "talk"),
    ("open VS Code", "en", "command"),
    ("ක්‍රෝම් එක ඕපන් කරන්න", "si", "command"),
    ("what time is it", "en", "quick"),
    ("thanks Jarvis", "en", "quick"),
    ("what's the weather in Kandy tomorrow", "en", "general"),
])
def test_keyword_routes(text, lang, route):
    assert KeywordRouter().route(text, lang).route == route


def test_long_prompts_go_to_big_context_models():
    router = KeywordRouter(long_prompt_chars=12000)
    assert router.route("explain this", "en", prompt_chars=13000).route == "long"
    assert router.route("explain this", "en", prompt_chars=5000).route == "teach"
    assert router.route("මේක පැහැදිලි කරන්න", "si", prompt_chars=7000).route == "long"   # Sinhala counts double


def test_every_intent_has_a_route():
    intents = {p.intent for _, patterns in LANGUAGES.values() for p in patterns}
    assert intents <= set(INTENT_ROUTE), intents - set(INTENT_ROUTE)
    assert set(INTENT_ROUTE.values()) <= set(ROUTES)
    assert route_for_intent("not_an_intent") == "general"


def test_keyword_baseline_on_generated_sentences():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from route_check import check

    per_lang, _, _ = check()
    right = sum(r for r, _ in per_lang.values())
    total = sum(n for _, n in per_lang.values())
    assert right / total >= 0.93                                   # 95.8% on 21 Oct
    assert all(r / n >= 0.9 for r, n in per_lang.values()), per_lang


def test_intent_router_uses_the_classifier_when_sure():
    sure = IntentRouter(lambda text, lang: ("derive_proof", 0.9), KeywordRouter())
    d = sure.route("hello there friend", "en")
    assert (d.route, d.intent) == ("maths", "derive_proof")
    unsure = IntentRouter(lambda text, lang: ("derive_proof", 0.3), KeywordRouter())
    assert unsure.route("write python code", "en").route == "code"            # the keyword rules decide
    assert sure.route("x", "en", prompt_chars=50000).route == "long"           # too big for fast models anyway


# ---- the routed LLM ------------------------------------------------------

def routed(**clients):
    providers = [Provider(name, f"model-{name}", c) for name, c in clients.items()]
    routes = {"general": list(clients), "maths": ["think", "backup"], "code": ["missing", "backup"]}
    return FallbackLLM(providers, routes=routes)


async def test_each_route_has_its_own_order():
    llm = routed(fast=FakeClient(["fast"]), think=FakeClient(["think"]), backup=FakeClient(["backup"]))
    assert await collect(llm.stream_text([], route="maths")) == "think"
    assert await collect(llm.stream_text([], route="code")) == "backup"          # "missing" has no key: skipped
    assert await collect(llm.stream_text([], route="teach")) == "fast"           # unknown route: general
    assert await collect(llm.stream_text([])) == "fast"
    assert llm.last_route == "general"


class RateLimited(Exception):
    status_code = 429

    def __init__(self, message="Rate limit reached on tokens per day (TPD). Please try again in 7m12.5s.",
                 headers=None):
        super().__init__(message)
        self.response = SimpleNamespace(headers=headers or {})


def test_rate_limit_wait():
    assert rate_limit_wait(RateLimited()) == pytest.approx(432.5)
    assert rate_limit_wait(RateLimited(headers={"retry-after": "30"})) == 30
    assert rate_limit_wait(RateLimited("Too many requests per day")) == 1800
    assert rate_limit_wait(RateLimited("Too many requests")) == 60
    assert rate_limit_wait(RateLimited("try again in 2h0m0s")) == 7200
    assert rate_limit_wait(TimeoutError("slow")) is None


async def test_a_model_at_its_limit_rests_and_is_skipped():
    now = [1000.0]
    limited = FakeClient(error=RateLimited(headers={"retry-after": "60"}))
    backup = FakeClient(["backup"])
    llm = FallbackLLM([Provider("oss", "gpt-oss-120b", limited), Provider("b", "m2", backup)],
                      clock=lambda: now[0])
    assert await collect(llm.stream_text([])) == "backup"
    assert await collect(llm.stream_text([])) == "backup"
    assert limited.calls == 1                                   # second time: skipped, no waiting on it
    now[0] += 61
    await collect(llm.stream_text([]))
    assert limited.calls == 2                                   # rested: tried again


async def test_same_model_twice_shares_its_rest():
    limited, same_model = FakeClient(error=RateLimited()), FakeClient(["never"])
    llm = FallbackLLM([Provider("oss", "gpt-oss-120b", limited, base_url="groq"),
                       Provider("oss_think", "gpt-oss-120b", same_model, {"reasoning_effort": "medium"}, "groq"),
                       Provider("other", "qwen", FakeClient(["qwen"]), base_url="groq")])
    assert await collect(llm.stream_text([])) == "qwen"
    assert same_model.calls == 0                                # same model, same free limits


async def test_all_resting_raises():
    llm = FallbackLLM([Provider("oss", "m", FakeClient(error=RateLimited()))])
    with pytest.raises(LLMUnavailable):
        await collect(llm.stream_text([]))
    with pytest.raises(LLMUnavailable) as info:
        await collect(llm.stream_text([]))
    assert "resting" in info.value.failures[0][1]


def test_think_filter_takes_out_thinking_even_when_split():
    f = ThinkFilter()
    out, thought = [], 0
    for piece in ["<thi", "nk>Let me ", "see.</th", "ink>\n\nThe answer", " is x < 3."]:
        text, n = f.feed(piece)
        out.append(text)
        thought += n
    out.append(f.flush())
    assert "".join(out) == "\n\nThe answer is x < 3." and thought == len("Let me see.")


async def test_inline_thinking_is_never_spoken():
    llm = FallbackLLM([Provider("qwen", "m", FakeClient(["<think>", "hmm, maths", "</think>", "\n\n", "Four."]))])
    assert await collect(llm.stream_text([])) == "Four."


async def test_empty_reply_falls_back():
    llm = FallbackLLM([Provider("a", "m", FakeClient(["<think>only thinking</think>"])),
                       Provider("b", "m2", FakeClient(["Answer."]))])
    assert await collect(llm.stream_text([])) == "Answer."


# ---- settings and the app ------------------------------------------------

def test_settings_routes(settings):
    routes = settings.routes()
    assert routes["general"] == settings.get("llm.order")
    assert {"quick", "maths", "teach", "code", "long", "talk", "command"} <= set(routes)
    names = [p.name for p in settings.providers()]
    assert len(names) == len(set(names)) and {"groq_qwen", "groq_oss_think", "gemini_lite"} <= set(names)
    settings.raw["llm"]["routing"] = False
    assert list(settings.routes()) == ["general"]
    settings.raw["llm"]["routing"] = True
    settings.raw["llm"]["routes"]["maths"] = ["nope"]
    with pytest.raises(ValueError, match="llm.routes.maths"):
        settings.routes()


def test_providers_at_one_address_share_a_connection(monkeypatch):
    from jarvis.agent.llm import configured_providers
    monkeypatch.setenv("GROQ_TEST_KEY", "k")
    url = "https://api.groq.com/openai/v1"
    ps = configured_providers([ProviderConfig("a", url, "GROQ_TEST_KEY", "m1"),
                               ProviderConfig("b", url, "GROQ_TEST_KEY", "m2"),
                               ProviderConfig("c", "https://other.example/v1", "GROQ_TEST_KEY", "m3")])
    assert ps[0].client is ps[1].client and ps[2].client is not ps[0].client


async def test_app_sends_each_request_down_its_route(settings, tmp_path):
    seen = []

    class RecordingLLM(FallbackLLM):
        def stream_text(self, messages, token=None, route=None, **kw):
            seen.append(route)
            return super().stream_text(messages, token=token, route=route, **kw)

    tel = Telemetry(tmp_path / "t.jsonl")
    app = App(settings, tel, llm=RecordingLLM([Provider("f", "m", FakeClient(["Ok."]))]), out=lambda *a, **k: None)
    await app.handle_text("solve this equation step by step")
    await app.handle_text("write python code for bubble sort")
    assert seen == ["maths", "code"]
    from jarvis.telemetry import turn_rows
    assert [r["route"] for r in turn_rows(tmp_path / "t.jsonl")] == ["maths", "code"]


async def test_a_language_can_have_its_own_order():
    llm = FallbackLLM([Provider("qwen", "q", FakeClient(["qwen"])), Provider("oss", "o", FakeClient(["oss"]))],
                      routes={"general": ["oss"], "code": ["qwen", "oss"], "code:si": ["oss", "qwen"]})
    assert await collect(llm.stream_text([], route="code", lang="en")) == "qwen"
    assert await collect(llm.stream_text([], route="code", lang="si")) == "oss"     # Sinhala: the better writer
    assert await collect(llm.stream_text([], route="code")) == "qwen"


def test_slow_or_overloaded_models_rest_briefly():
    from jarvis.agent.llm import SLOW_REST_S, failure_rest

    class Overloaded(Exception):
        status_code = 503

    class APITimeoutError(Exception):
        pass

    assert failure_rest(Overloaded()) == SLOW_REST_S
    assert failure_rest(APITimeoutError("Request timed out.")) == SLOW_REST_S
    assert failure_rest(TimeoutError()) == SLOW_REST_S
    assert failure_rest(RateLimited(headers={"retry-after": "30"})) == 30
    assert failure_rest(ConnectionError("refused")) is None        # fails fast anyway (Ollama not started)


async def test_a_timed_out_model_is_skipped_next_turn():
    slow, fast = FakeClient(error=TimeoutError("timed out")), FakeClient(["fast"])
    llm = FallbackLLM([Provider("gemini", "g", slow), Provider("groq", "o", fast)])
    await collect(llm.stream_text([]))
    await collect(llm.stream_text([]))
    assert slow.calls == 1


def test_settings_language_routes(settings):
    routes = settings.routes()
    assert routes["code:si"][0] == "groq_oss" and routes["code"][0] == "groq_qwen"
    settings.raw["llm"]["language_routes"]["si"]["code"] = ["nope"]
    with pytest.raises(ValueError, match="llm.language_routes.si.code"):
        settings.routes()


def test_leaked_reasoning_is_dropped():
    from jarvis.agent.llm import LeakFilter

    def run(pieces):
        f = LeakFilter()
        return "".join(f.feed(p) for p in pieces) + f.flush(), f.dropped

    out, dropped = run(["Sure, sir. What would you like to discuss about Friday?", "User wants to talk Friday.",
                        "Do you have an appointment?"])              # what Jarvis printed on 21 Oct
    assert out == "Sure, sir. What would you like to discuss about Friday? Do you have an appointment?"
    assert dropped == ["User wants to talk Friday."]
    assert run(["Sure", ", sir. ", "Us", "er wa", "nts to talk Friday.Do you", " have one?"])[0] \
        == "Sure, sir. Do you have one?"
    kept = "User accounts are stored in a table. We should check the units first. The user interface is simple."
    assert run([kept]) == (kept, [])                                   # real sentences that start alike


async def test_leak_never_reaches_the_reply():
    tel_events = []

    class Tel(Telemetry):
        def __init__(self):
            super().__init__(None)

        def log(self, event, **fields):
            tel_events.append((event, fields))

    llm = FallbackLLM([Provider("oss", "m", FakeClient(["We need to respond briefly. ", "Hello, sir."]))], Tel())
    assert await collect(llm.stream_text([])) == "Hello, sir."
    assert any(e == "llm_leak_dropped" and "respond briefly" in f["text"] for e, f in tel_events)


async def test_sinhala_typed_in_english_mode_switches_to_friday(settings):
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", FakeClient(["හරි."]))]),
              out=lambda *a, **k: None)
    assert app.lang.current.code == "en"
    await app.handle_text("ඔයාට සිංහල තේරෙනවද?")
    assert app.lang.current.code == "si"


async def test_saying_the_current_name_with_a_request_just_answers(settings):
    client = FakeClient(["Of course."])
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", client)]), out=lambda *a, **k: None)
    assert await app.handle_text("Jarvis, I need help") == "Of course."      # no "English it is" confirmation
    assert client.calls == 1
