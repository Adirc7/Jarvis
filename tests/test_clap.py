"""The double clap (perception/clap.py, D29) on made-up audio: what counts as one, and what never does."""

import numpy as np
import pytest

from jarvis.perception.clap import ClapDetector, ClapListener, ClapSettings, SpeechEnd

RATE = 16000


def room(seconds: float, level: float = 0.002, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(0, level, int(seconds * RATE)).astype(np.float32)


def clap(seed: int = 1) -> np.ndarray:
    """A sharp broadband burst that dies away in a few tens of ms, like a hand clap."""
    n = int(0.06 * RATE)
    burst = np.random.default_rng(seed).normal(0, 0.3, n)
    return (burst * np.exp(-np.arange(n) / (0.008 * RATE))).astype(np.float32)


def thump() -> np.ndarray:
    """The same envelope at 90 Hz: a desk tap or a knock, low-pitched."""
    n = int(0.06 * RATE)
    t = np.arange(n) / RATE
    return (0.3 * np.sin(2 * np.pi * 90 * t) * np.exp(-np.arange(n) / (0.008 * RATE))).astype(np.float32)


def at(audio: np.ndarray, sound: np.ndarray, second: float) -> np.ndarray:
    i = int(second * RATE)
    audio[i:i + len(sound)] += sound
    return audio


def heard(audio: np.ndarray, block: int = 480, **kwargs) -> list:
    detector = ClapDetector(RATE, **kwargs)
    events = []
    for i in range(0, len(audio), block):
        events += detector.feed(audio[i:i + block])
    return events


def doubles(audio, **kwargs) -> list[float]:
    return [round(e.t, 2) for e in heard(audio, **kwargs) if e.kind == "double"]


def test_two_claps_a_third_of_a_second_apart_are_a_double_clap():
    audio = at(at(room(4), clap(1), 1.0), clap(2), 1.3)
    events = heard(audio)
    peaks = [e for e in events if e.kind == "peak"]
    assert [round(p.t, 2) for p in peaks] == [1.0, 1.3] and all(p.counted for p in peaks)
    assert all(p.high_share > 0.5 and p.above > 30 for p in peaks)          # broadband, and loud
    assert doubles(audio) == pytest.approx([1.9], abs=0.02)               # 0.6 s after the second: no third
    assert doubles(audio, block=37) == pytest.approx([1.9], abs=0.02)     # any block size


@pytest.mark.parametrize("times", [[1.0], [1.0, 1.1], [1.0, 1.9], [1.0, 1.3, 1.6], [1.0, 1.3, 1.6, 1.9]])
def test_one_clap_too_close_too_far_or_three_is_not(times):
    audio = room(4)
    for k, t in enumerate(times):
        at(audio, clap(k + 1), t)
    assert doubles(audio) == []


def test_long_sounds_and_low_thumps_never_count():
    tone = room(4)
    tone[int(1 * RATE):int(2 * RATE)] += (0.3 * np.sin(2 * np.pi * 440 * np.arange(RATE) / RATE)).astype(np.float32)
    assert doubles(tone) == [] and not [e for e in heard(tone) if e.kind == "peak"]
    noise = room(4)
    noise[int(1 * RATE):int(2.5 * RATE)] += room(1.5, 0.2, seed=5)       # a burst of noise, a fan, a hiss
    assert doubles(noise) == []
    knocks = at(at(room(4), thump(), 1.0), thump(), 1.3)
    peaks = [e for e in heard(knocks) if e.kind == "peak"]
    assert peaks and not any(p.counted for p in peaks) and peaks[0].why == "low-pitched"
    assert doubles(knocks) == []


def test_nothing_counts_while_jarvis_speaks_or_just_after():
    speaking = {"now": False}
    audio = at(at(room(6), clap(1), 1.0), clap(2), 1.3)
    at(at(audio, clap(3), 4.0), clap(4), 4.3)
    detector = ClapDetector(RATE, muted=lambda: speaking["now"])
    found = []
    for i in range(0, len(audio), 480):
        speaking["now"] = i < int(1.2 * RATE)                              # speaking until 1.2 s
        found += [round(e.t, 2) for e in detector.feed(audio[i:i + 480]) if e.kind == "double"]
    assert found == pytest.approx([4.9], abs=0.02)                         # the first pair was during speech


def test_after_a_double_clap_the_next_two_seconds_rest():
    audio = room(6)
    for t in (1.0, 1.3, 2.2, 2.5, 4.0, 4.3):
        at(audio, clap(int(t * 10)), t)
    assert doubles(audio) == pytest.approx([1.9, 4.9], abs=0.02)


def test_a_quiet_room_learns_first_and_settings_come_from_the_config(settings):
    assert doubles(at(at(room(3), clap(1), 0.1), clap(2), 0.4)) == []      # before it knows the room
    settings.raw["clap"] = {"min_gap_s": 0.1, "min_high_share": 0.5, "enabled": True}
    s = ClapSettings.from_settings(settings)
    assert s.min_gap_s == 0.1 and s.min_high_share == 0.5 and s.max_gap_s == 0.6


def test_listening_ends_when_you_pause_or_says_nothing_was_said():
    floor = -54.0
    end = SpeechEnd(floor)
    speech = room(1.0, 0.05, seed=9)
    states = [end.feed(b) for b in np.split(np.concatenate([room(0.5), speech, room(1.0)]), 50)]
    assert "ended" in states and states.index("ended") > 30                # after the speech and 0.8 s quiet
    quiet = SpeechEnd(floor)
    assert [quiet.feed(b) for b in np.split(room(6), 60)].count("nothing") >= 1


class FakeRecorder:
    def __init__(self):
        self.frames, self.recording = [], False

    def begin(self):
        self.frames, self.recording = [], True

    def end(self):
        self.recording = False
        return np.concatenate(self.frames) if self.frames else np.zeros(0, np.float32)

    def feed(self, samples):
        if self.recording:
            self.frames.append(samples)


def test_the_listener_hears_a_double_clap_then_records_until_you_pause():
    rec, got = FakeRecorder(), {"double": 0, "heard": None, "nothing": 0}
    listener = ClapListener(rec, on_double=lambda: got.__setitem__("double", got["double"] + 1),
                            on_heard=lambda a: got.__setitem__("heard", a),
                            on_nothing=lambda: got.__setitem__("nothing", got["nothing"] + 1))
    audio = at(at(room(3), clap(1), 1.0), clap(2), 1.3)
    for i in range(0, len(audio), 480):
        rec.feed(audio[i:i + 480])
        listener.feed(audio[i:i + 480])
    assert got["double"] == 1
    listener.listen()
    talk = np.concatenate([room(0.3), room(1.2, 0.05, seed=4), room(1.0)])
    for i in range(0, len(talk), 480):
        rec.feed(talk[i:i + 480])
        listener.feed(talk[i:i + 480])
    assert got["heard"] is not None and 2.0 < len(got["heard"]) / RATE < 2.6 and listener.listening is None
    listener.listen()
    listener.cancel()                                                      # push-to-talk took over
    assert listener.listening is None and got["nothing"] == 0


async def test_in_jarvis_a_double_clap_means_listen_now_and_never_while_he_speaks(settings):
    import asyncio

    from test_voice_pipeline import FakeWhisper, make_voice_app

    from jarvis.events import UtteranceCaptured
    from jarvis.state import Mode

    class Mic(FakeRecorder):
        sample_rate = RATE
        listeners: list = []

    app, spoken, _, out = make_voice_app(settings, ["Fourier series add up sines."],
                                         FakeWhisper(texts={"en": "what is a fourier series"}))
    app.recorder = Mic()
    app.recorder.listeners = []
    app.bus.bind(asyncio.get_running_loop())               # as run() does: events from the microphone's thread
    assert app._start_clap() and app.recorder.listeners == [app._clap.feed]
    got = app.bus.subscribe(UtteranceCaptured, name="test")
    app._clap.feed(room(1.0))                                 # the room, heard before the claps
    await app._double_clap()
    assert any("Yes" in text for _, text in spoken) and app.state.mode == Mode.LISTENING and app._clap.listening is not None
    talk = np.concatenate([room(0.3), room(1.0, 0.05, seed=4), room(1.0)])
    for i in range(0, len(talk), 480):                       # what the microphone's thread does
        app.recorder.feed(talk[i:i + 480])
        app._clap.feed(talk[i:i + 480])
    await asyncio.sleep(0.05)
    ev = got.get_nowait()
    assert 1.9 < ev.seconds < 2.5 and app._clap.listening is None
    reply = await app.voice_turn(ev.audio, ev.seconds)
    assert reply == "Fourier series add up sines."
    spoken.clear()
    app.state.mode = Mode.SPEAKING                            # while he speaks: ignored
    await app._double_clap()
    assert spoken == [] and app._clap.listening is None
    app.state.mode = Mode.IDLE
    app._clap_command("off")
    await app._double_clap()
    assert spoken == [] and "[clap] off." in out[-1]


# ---- three claps open Jarvis (clap_launcher.py, 4 Nov) ------------------------------------------
def launches(audio, block: int = 1600) -> int:
    from jarvis.clap_launcher import Launcher
    started = []
    launcher = Launcher(start=lambda: started.append(1), log=lambda line: None)
    for i in range(0, len(audio), block):
        launcher.feed(audio[i:i + block])
    return len(started)


def test_three_claps_start_jarvis_once():
    audio = at(at(at(room(5), clap(1), 1.0), clap(2), 1.35), clap(3), 1.7)
    assert launches(audio) == 1


def test_two_claps_four_claps_slow_claps_or_knocks_start_nothing():
    assert launches(at(at(room(4), clap(1), 1.0), clap(2), 1.3)) == 0                      # Jarvis's double clap
    four = room(5)
    for i, t in enumerate((1.0, 1.3, 1.6, 1.9)):
        four = at(four, clap(i + 1), t)
    assert launches(four) == 0                                                          # applause
    slow = at(at(at(room(6), clap(1), 1.0), clap(2), 2.0), clap(3), 3.0)
    assert launches(slow) == 0                                                          # a second apart
    knocks = at(at(at(room(5), thump(), 1.0), thump(), 1.35), thump(), 1.7)
    assert launches(knocks) == 0                                                        # low-pitched


def test_after_starting_it_rests_before_counting_again():
    audio = room(8)
    for t in (1.0, 1.35, 1.7, 3.0, 3.35, 3.7):
        audio = at(audio, clap(int(t * 10)), t)
    assert launches(audio) == 1


def test_three_claps_a_little_slower_than_a_double_still_count():
    """4 Nov on the laptop: Adhi's claps came 0.57-0.6 s apart, at the double clap's 0.6 s limit."""
    audio = at(at(at(room(5), clap(1), 1.0), clap(2), 1.7), clap(3), 2.45)
    assert launches(audio) == 1


def test_jarvis_is_started_through_run_jarvis_cmd_not_start_with_a_bare_title(monkeypatch, tmp_path):
    import subprocess

    from jarvis import clap_launcher
    ran = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: ran.append(args))
    clap_launcher.start_jarvis(tmp_path)
    assert ran == [["cmd.exe", "/c", str(tmp_path / "scripts" / "run_jarvis.cmd"), "voice"]]
