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
    client = FakeClient(["a", "b", "c", "d"])
    llm = llm_with(client)
    got = []
    async for piece in llm.stream_text([], token=token):
        got.append(piece)
        state.cancel_all()                      # kill switch pressed mid-reply
    assert got == ["a"] and client.last_stream.closed


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
