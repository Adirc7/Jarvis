""""Hey Jarvis" without the key (perception/wake.py), with a stand-in for openWakeWord's model."""

from __future__ import annotations

import numpy as np

from jarvis.perception.wake import CHUNK, WakeWord


class FakeModel:
    """Scores 0.99 for chunks that are loud (a stand-in for "Hey Jarvis"), 0.01 otherwise."""

    def __init__(self):
        self.resets = 0

    def predict(self, chunk):
        return {"hey_jarvis_v0.1": 0.99 if np.abs(chunk).mean() > 1000 else 0.01}

    def reset(self):
        self.resets += 1


def run(blocks, muted=lambda: False, clock=None):
    woke, t = [], {"now": 0.0}
    wake = WakeWord(FakeModel(), on_wake=lambda: woke.append(t["now"]), muted=muted, thread=False,
                    clock=clock or (lambda: t["now"]))
    for loud in blocks:
        t["now"] += CHUNK / 16000
        wake.process(np.full(CHUNK, 3000 if loud else 10, np.int16))
    return woke, wake


def test_hey_jarvis_wakes_once_then_rests():
    woke, _ = run([False] * 10 + [True] * 5 + [False] * 10 + [True] * 3)
    assert len(woke) == 1                                       # 2 s rest: the second one is too soon
    woke, _ = run([False] * 5 + [True] * 2 + [False] * 30 + [True] * 2)
    assert len(woke) == 2                                       # after the rest, it wakes again


def test_deaf_while_jarvis_speaks_and_a_second_after():
    speaking = {"on": True}
    t = {"now": 0.0}
    woke = []
    wake = WakeWord(FakeModel(), on_wake=lambda: woke.append(t["now"]), muted=lambda: speaking["on"],
                    thread=False, clock=lambda: t["now"])
    for _ in range(20):                                         # his own "Jarvis here, sir"
        t["now"] += 0.08
        wake.process(np.full(CHUNK, 3000, np.int16))
    speaking["on"] = False
    t["now"] += 0.5
    wake.process(np.full(CHUNK, 3000, np.int16))                # still within a second of him stopping
    assert woke == [] and wake.model.resets == 1
    t["now"] += 1.0
    wake.process(np.full(CHUNK, 3000, np.int16))
    assert len(woke) == 1


def test_the_microphone_thread_only_queues():
    wake = WakeWord(FakeModel(), on_wake=lambda: None, thread=False)
    for _ in range(100):                                        # never blocks, even when nobody reads
        wake.feed(np.zeros(480, np.float32))
    assert wake._queue.qsize() == 64


async def test_in_jarvis_hey_jarvis_means_listen_now_even_with_the_claps_off(settings, monkeypatch):
    import asyncio

    from test_clap import RATE, FakeRecorder, room
    from test_voice_pipeline import FakeWhisper, make_voice_app

    from jarvis.perception import wake
    from jarvis.state import Mode

    class Mic(FakeRecorder):
        sample_rate = RATE

    monkeypatch.setattr(wake, "load_model", lambda folder: FakeModel())
    app, spoken, _, out = make_voice_app(settings, ["Hello."], FakeWhisper(texts={"en": "hello"}))
    app.recorder = Mic()
    app.recorder.listeners = []
    app.bus.bind(asyncio.get_running_loop())
    assert app._start_wake() and app._clap is not None and not app._clap.on      # the claps stay off
    assert app.recorder.listeners == [app._clap.feed, app._wake.feed]
    app._clap.feed(room(1.0))
    await app._listen_hands_free("wake")
    assert any("Yes" in text for _, text in spoken) and app.state.mode == Mode.LISTENING
    assert any("[Hey Jarvis] listening" in line for line in out)
    app._wake_command("off")
    assert not app._wake.on and "[wake word] off." in out[-1]
