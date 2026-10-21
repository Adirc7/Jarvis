import pytest

from conftest import FakeClient
from jarvis.app import App
from jarvis.agent.llm import FallbackLLM, LLMUnavailable, Provider
from jarvis.events import KillSwitchPressed
from jarvis.state import Mode, SharedState
from jarvis.telemetry import Telemetry


def llm_with(*clients):
    return FallbackLLM([Provider(f"p{i}", "m", c) for i, c in enumerate(clients)])


async def collect(agen):
    return "".join([x async for x in agen])


async def test_first_provider_answers():
    a, b = FakeClient(["Hi"]), FakeClient(["Other"])
    llm = llm_with(a, b)
    assert await collect(llm.stream_text([{"role": "user", "content": "x"}])) == "Hi"
    assert llm.last_provider == "p0" and b.calls == 0


async def test_falls_back_when_provider_errors():
    a, b = FakeClient(error=TimeoutError("rate limited")), FakeClient(["From backup"])
    llm = llm_with(a, b)
    assert await collect(llm.stream_text([])) == "From backup"
    assert llm.last_provider == "p1"


async def test_all_fail_raises_with_reasons():
    llm = llm_with(FakeClient(error=ConnectionError("offline")), FakeClient(error=TimeoutError("slow")))
    with pytest.raises(LLMUnavailable) as info:
        await collect(llm.stream_text([]))
    assert [name for name, _ in info.value.failures] == ["p0", "p1"]


async def test_no_silent_switch_after_reply_started():
    a = FakeClient(["one", "two", "three"], fail_at=1)
    b = FakeClient(["backup"])
    llm = llm_with(a, b)
    with pytest.raises(RuntimeError):
        await collect(llm.stream_text([]))
    assert b.calls == 0


async def test_cancel_token_stops_stream():
    state = SharedState()
    token = state.token()
    client = FakeClient(["Hello", " b", " c", " d"])
    llm = llm_with(client)
    got = []
    async for piece in llm.stream_text([], token=token):
        got.append(piece)
        state.cancel_all()                      # kill switch pressed mid-reply
    assert got == ["Hello"] and client.last_stream.closed


async def test_complete_falls_back():
    llm = llm_with(FakeClient(error=RuntimeError("down")), FakeClient(["tool result"]))
    provider, msg = await llm.complete([], tools=[{"type": "function"}])
    assert provider == "p1" and msg.content == "tool result"


# ---- App: language switching + LLM in one turn ----------------------------

def make_app(settings, client):
    out = []
    app = App(settings, Telemetry.disabled(), llm=llm_with(client), out=lambda *a, **k: out.append("".join(map(str, a))))
    return app, out


async def test_short_switch_command_does_not_call_llm(settings):
    client = FakeClient(["should not be used"])
    app, out = make_app(settings, client)
    reply = await app.handle_text("switch to Tamil")
    assert app.state.language == "ta"
    assert reply == settings.languages["ta"].confirm
    assert client.calls == 0


async def test_language_instruction_reaches_llm(settings):
    client = FakeClient(["ආයුබෝවන්"])
    app, _ = make_app(settings, client)
    await app.handle_text("සිංහලෙන් කතා කරන්න")
    reply = await app.handle_text("hello, who are you?")
    system = client.last_messages[0]["content"]
    assert "Sinhala" in system and "සිංහල" in system
    assert reply == "ආයුබෝවන්"


async def test_llm_unavailable_gives_spoken_error(settings):
    app, out = make_app(settings, FakeClient(error=ConnectionError("offline")))
    reply = await app.handle_text("hello")
    assert "can't reach" in reply
    assert app.state.mode == Mode.IDLE


async def test_kill_switch_pauses(settings):
    import asyncio
    app, out = make_app(settings, FakeClient())
    app.bus.bind()
    task = asyncio.create_task(app._control_task())
    await asyncio.sleep(0)
    app.bus.publish(KillSwitchPressed(source="test"))
    await asyncio.sleep(0.01)
    assert app.state.mode == Mode.PAUSED and app.state.cancel_generation == 1
    await app.handle_text("hello again")        # a new request resumes
    assert app.state.mode == Mode.IDLE
    task.cancel()


async def test_provider_options_go_in_extra_body():
    seen = {}

    class Recording(FakeClient):
        async def create(self, model, messages, stream=False, **kwargs):
            seen.update(kwargs)
            return await super().create(model, messages, stream=stream)

    llm = FallbackLLM([Provider("oss", "openai/gpt-oss-120b", Recording(["Hi"]), {"reasoning_effort": "low"})])
    assert await collect(llm.stream_text([{"role": "user", "content": "x"}], temperature=0.5)) == "Hi"
    assert seen == {"temperature": 0.5, "extra_body": {"reasoning_effort": "low"}}


def test_groq_oss_provider_configured(settings):
    by_name = {p.name: p for p in settings.providers()}
    oss = by_name["groq_oss"]
    assert oss.model == "openai/gpt-oss-120b"
    assert oss.api_key_env == "GROQ_API_KEY"
    assert oss.options == {"reasoning_effort": "low"}
    assert [p.name for p in settings.providers()][:2] == ["groq_oss", "groq"]   # fastest first


def test_no_retired_models_and_thinking_kept_short(settings):
    """Groq retired llama-3.3-70b-versatile (2026-08-16); OpenRouter's Llama 3.3
    stopped being free. Thinking models get reasoning_effort = low for speech."""
    by_name = {p.name: p for p in settings.providers()}
    assert by_name["groq"].model == "openai/gpt-oss-20b"
    assert "llama-3.3" not in by_name["openrouter"].model and "free" in by_name["openrouter"].model
    for name in ("gemini", "groq", "groq_oss"):
        assert by_name[name].options.get("reasoning_effort") == "low"


class ThinkingStream:
    """Like gpt-oss on Groq: reasoning chunks first, then the reply."""

    def __init__(self):
        self.closed = False

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        from types import SimpleNamespace as NS
        for r in ("The user wants", " a short answer."):
            yield NS(choices=[NS(delta=NS(content=None, reasoning=r))])
        for c in ("Sure", ", sir."):
            yield NS(choices=[NS(delta=NS(content=c))])

    async def close(self):
        self.closed = True


async def test_thinking_before_the_first_word_is_measured():
    from types import SimpleNamespace as NS

    class Capture(Telemetry):
        def __init__(self):
            super().__init__(None)
            self.events = []

        def log(self, event, **fields):
            self.events.append({"event": event, **fields})

    async def create(model, messages, stream=False, **kwargs):
        return ThinkingStream()

    tel = Capture()
    client = NS(chat=NS(completions=NS(create=create)))
    llm = FallbackLLM([Provider("groq_oss", "openai/gpt-oss-120b", client)], tel)
    text = "".join([p async for p in llm.stream_text([{"role": "user", "content": "hi"}])])
    assert text == "Sure, sir."                                   # reasoning is never spoken
    first = next(e for e in tel.events if e["event"] == "llm_first_token")
    assert first["thinking_chars"] == len("The user wants a short answer.")
    assert first["first_chunk_ms"] <= first["ms"]
    assert first["prompt_chars"] == 2 and first["messages"] == 1


def test_llm_speed_try_option():
    import importlib.util

    from jarvis.config import PROJECT_ROOT, ProviderConfig
    spec = importlib.util.spec_from_file_location("llm_speed", PROJECT_ROOT / "scripts" / "llm_speed.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    groq = ProviderConfig("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-20b",
                          {"reasoning_effort": "low"})
    cfg = mod.parse_try("groq=qwen/qwen3-32b,reasoning_effort=none", {"groq": groq})
    assert (cfg.name, cfg.model, cfg.options) == ("groq:qwen/qwen3-32b", "qwen/qwen3-32b", {"reasoning_effort": "none"})
    assert cfg.base_url == groq.base_url and cfg.api_key_env == "GROQ_API_KEY"
    with pytest.raises(SystemExit):
        mod.parse_try("nobody=some-model", {"groq": groq})


async def test_warm_opens_the_first_providers_connection():
    from types import SimpleNamespace as NS
    calls = []

    async def list_models():
        calls.append("models")
        return []

    first = Provider("groq_oss", "m", NS(models=NS(list=list_models)))
    second = Provider("gemini", "m", NS(models=NS(list=list_models)))
    await FallbackLLM([first, second]).warm()
    assert calls == ["models"]                                     # only the first provider


async def test_warm_ignores_failures_and_missing_support():
    from types import SimpleNamespace as NS

    async def broken():
        raise ConnectionError("offline")

    await FallbackLLM([Provider("p", "m", NS(models=NS(list=broken)))]).warm()   # no exception
    await FallbackLLM([Provider("p", "m", FakeClient())]).warm()                 # no models.list at all
    await FallbackLLM([]).warm()


def test_provider_keeps_connections_open_between_turns():
    from jarvis.config import ProviderConfig
    p = Provider.from_config(ProviderConfig("groq", "https://api.groq.com/openai/v1", "X", "m"), 20, 90)
    assert p.client._client._transport._pool._keepalive_expiry == 90   # library default is 5 s


async def test_pressing_push_to_talk_warms_the_llm(settings):
    import asyncio

    from jarvis.events import PushToTalkPressed
    warmed = []

    class CountingLLM(FallbackLLM):
        async def warm(self, timeout_s=3.0):
            warmed.append(True)

    app = App(settings, Telemetry.disabled(), llm=CountingLLM([Provider("f", "m", FakeClient())]),
              out=lambda *a, **k: None)
    task = asyncio.create_task(app._voice_task())
    await asyncio.sleep(0)
    app.bus.publish(PushToTalkPressed())
    await asyncio.sleep(0.05)
    task.cancel()
    assert warmed == [True]
