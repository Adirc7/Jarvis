"""One turn at a time, and stop means stop (docs/REVIEW_FIXES.md, group 1)."""

import asyncio
import threading
import time
from types import SimpleNamespace

import numpy as np
from conftest import FakeClient
from test_voice_pipeline import AUDIO, FakeWhisper, make_voice_app

from jarvis.agent.llm import FallbackLLM, Provider
from jarvis.app import REPLY_BROKE_OFF, App
from jarvis.state import Mode
from jarvis.telemetry import Telemetry
from jarvis.voice.player import AudioPlayer


class SlowWhisper(FakeWhisper):
    """Speech recognition that takes a while, like a long utterance on the GPU."""

    def __init__(self, texts, seconds=0.2):
        super().__init__(texts=texts)
        self.seconds = seconds

    def transcribe(self, audio, language=None, **kwargs):
        time.sleep(self.seconds)
        return super().transcribe(audio, language, **kwargs)


class EchoClient:
    """Streams "answer to <question>"; the question "first" is slow."""

    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, model, messages, stream=False, **kwargs):
        self.calls += 1
        question = messages[-1]["content"]

        async def gen():
            for word in ["Answer ", "to ", question, "."]:
                await asyncio.sleep(0.05 if question == "first" else 0.001)
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=word))])
        return gen()


def press_kill(app):
    """What the kill switch does (App._control_task)."""
    app.state.cancel_all()
    app.sink.stop()
    app.state.mode = Mode.PAUSED


async def test_kill_switch_during_speech_recognition_never_reaches_the_model(settings):
    app, spoken, backend, out = make_voice_app(settings, ["Never."], SlowWhisper({"en": "delete my notes"}))
    client = app.llm.providers[0].client
    turn = asyncio.create_task(app.voice_turn(AUDIO, 1.0))
    await asyncio.sleep(0.05)                       # Whisper is busy
    press_kill(app)
    assert await turn is None
    assert client.calls == 0 and spoken == [] and app.history == []
    assert any("was not sent" in line for line in out)
    assert app.state.mode == Mode.PAUSED            # stays stopped until a new request


async def test_a_new_request_after_the_kill_switch_resumes(settings):
    app, spoken, backend, out = make_voice_app(settings, ["Back."], FakeWhisper(texts={"en": "hello"}))
    press_kill(app)
    assert await app.voice_turn(AUDIO, 1.0) == "Back."
    assert app.state.mode == Mode.IDLE


async def test_barge_in_during_speech_recognition_drops_the_old_question(settings):
    app, spoken, backend, out = make_voice_app(settings, ["Ok."], SlowWhisper({"en": "question"}, seconds=0.1))
    client = app.llm.providers[0].client
    old = asyncio.create_task(app.voice_turn(AUDIO, 1.0))
    await asyncio.sleep(0.03)
    app.state.cancel_all()                          # push-to-talk pressed again
    app.sink.stop()
    new = asyncio.create_task(app.voice_turn(AUDIO, 1.0))
    assert await old is None
    assert await new == "Ok."
    assert client.calls == 1 and len(app.history) == 2


async def test_two_requests_at_once_are_answered_and_saved_in_order(settings):
    client = EchoClient()
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", client)]),
              out=lambda *a, **k: None)
    first = asyncio.create_task(app.handle_text("first"))       # slow
    await asyncio.sleep(0)
    second = asyncio.create_task(app.handle_text("second"))     # fast, but asked later
    await asyncio.gather(first, second)
    assert [m["content"] for m in app.history] == [
        "first", "Answer to first.", "second", "Answer to second."]


async def test_a_reply_stopped_halfway_is_not_saved(settings):
    pieces = [f"Sentence {i} is here. " for i in range(20)]
    app, spoken, backend, out = make_voice_app(settings, pieces, FakeWhisper(texts={"en": "talk a lot"}))

    async def stop_soon():
        while not spoken:
            await asyncio.sleep(0.001)
        press_kill(app)

    stopper = asyncio.create_task(stop_soon())
    await app.voice_turn(AUDIO, 1.0)
    await stopper
    assert app.history == [] and len(spoken) < 20


async def test_mute_mid_reply_stops_the_rest(settings):
    pieces = [f"Sentence number {i} is right here. " for i in range(12)]
    app, spoken, backend, out = make_voice_app(settings, pieces, FakeWhisper(texts={"en": "talk"}))
    played_at_mute = []

    async def mute_soon():
        while not backend.played:
            await asyncio.sleep(0.001)
        app.sink.toggle_mute()
        played_at_mute.append(len(backend.played))

    muter = asyncio.create_task(mute_soon())
    reply = await app.voice_turn(AUDIO, 1.0)
    await muter
    await asyncio.sleep(0.05)
    assert reply == "".join(pieces)                              # the text still arrives in full
    assert len(backend.played) <= played_at_mute[0] + 1         # at most the sentence already handed over


async def test_a_provider_dropping_mid_reply_does_not_crash(settings):
    client = FakeClient(["Hello", " there", " and more"], fail_at=1)
    out = []
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", client)]),
              out=lambda *a, **k: out.append("".join(map(str, a))))
    assert await app.handle_text("hi") == REPLY_BROKE_OFF
    assert app.history == [] and any("broke off" in line for line in out)
    assert await app.handle_text("hi again") == REPLY_BROKE_OFF       # still taking requests, no crash
    assert client.calls == 2


class BlockingBackend:
    def __init__(self):
        self.played = 0
        self.started = threading.Event()

    def play(self, audio, sr, stop):
        self.played += 1
        self.started.set()
        stop.wait(1.0)

    def stop(self):
        pass


def test_player_stop_drops_everything_queued_before_it():
    backend = BlockingBackend()
    player = AudioPlayer(backend)
    for _ in range(3):
        player.play(np.zeros(10, np.float32), 16000)
    assert backend.started.wait(1.0)
    player.stop()
    assert player.wait_idle(2.0)
    assert backend.played == 1                                   # the two queued never played
    player.play(np.zeros(10, np.float32), 16000)                 # and it still works afterwards
    time.sleep(0.05)
    player.stop()
    assert player.wait_idle(2.0) and backend.played == 2
