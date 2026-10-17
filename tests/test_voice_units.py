import threading
import time

import numpy as np
import pytest

from jarvis.state import SharedState
from jarvis.voice.capture import MicRecorder, PushToTalk
from jarvis.voice.effects import VoiceStyle
from jarvis.voice.player import AudioPlayer
from jarvis.voice.text_split import SentenceChunker, clean_for_speech


# ---- sentence chunking ------------------------------------------------------

def feed_all(chunker, pieces):
    out = []
    for p in pieces:
        out += chunker.feed(p)
    return out + chunker.flush()


def test_first_sentence_is_emitted_early():
    c = SentenceChunker(first_min_chars=10, min_chars=40)
    assert c.feed("Good evening. ") == ["Good evening."]


def test_later_short_sentences_are_merged():
    c = SentenceChunker(first_min_chars=5, min_chars=40)
    chunks = feed_all(c, ["Hi there. ", "Yes. ", "No. ", "This is a longer sentence that ends here. ", "Bye."])
    assert chunks[0] == "Hi there."
    assert chunks[1] == "Yes. No. This is a longer sentence that ends here."
    assert chunks[-1] == "Bye."


def test_token_by_token_stream_matches_whole_text():
    text = "Hello, I am Jarvis. I can help you with your laptop today. What would you like to do?"
    c = SentenceChunker(first_min_chars=10, min_chars=30)
    chunks = feed_all(c, list(text))                 # one character at a time
    assert " ".join(chunks) == text


def test_abbreviation_and_decimal_do_not_split():
    c = SentenceChunker(first_min_chars=5, min_chars=5)
    chunks = feed_all(c, ["Version 3.5 is out, e.g. today. Done."])
    assert chunks == ["Version 3.5 is out, e.g. today.", "Done."]


def test_long_first_sentence_breaks_at_comma():
    c = SentenceChunker(first_min_chars=10, min_chars=40)
    out = c.feed("When you open the settings panel on the left side of the window, you will see ")
    assert out == ["When you open the settings panel on the left side of the window,"]


def test_sinhala_and_tamil_sentences_split():
    c = SentenceChunker(first_min_chars=5, min_chars=5)
    assert feed_all(c, ["ආයුබෝවන්. මම ජාවිස්."]) == ["ආයුබෝවන්.", "මම ජාවිස්."]
    c = SentenceChunker(first_min_chars=5, min_chars=5)
    assert feed_all(c, ["வணக்கம். நான் ஜார்விஸ்."]) == ["வணக்கம்.", "நான் ஜார்விஸ்."]


def test_hard_cut_when_no_punctuation():
    c = SentenceChunker(first_min_chars=10, min_chars=10, max_chars=50)
    chunks = c.feed("word " * 30)
    assert chunks and all(len(ch) <= 50 for ch in chunks)


def test_clean_for_speech_strips_markdown():
    md = "## Steps\n- **Open** the `settings` panel\n1. See [docs](https://x.org) or https://y.org"
    assert clean_for_speech(md) == "Steps Open the settings panel See docs or a link"


# ---- effects ------------------------------------------------------------------

def test_voice_style_keeps_audio_sane():
    pytest.importorskip("pedalboard")
    sr = 24000
    t = np.arange(sr) / sr
    audio = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    out = VoiceStyle().process(audio, sr)
    assert out.dtype == np.float32
    assert len(out) >= len(audio)                  # reverb tail appended
    assert np.max(np.abs(out)) <= 1.0
    assert np.sqrt(np.mean(out ** 2)) > 0.05       # still audible


def test_disabled_style_is_passthrough():
    audio = np.random.default_rng(0).standard_normal(1000).astype(np.float32) * 0.1
    assert VoiceStyle(enabled=False).process(audio, 16000) is audio


def test_style_from_settings_ignores_unknown_keys():
    s = VoiceStyle.from_dict({"reverb_wet": 0.3, "made_up": 1})
    assert s.reverb_wet == 0.3


# ---- player ---------------------------------------------------------------------

class FakeBackend:
    def __init__(self, seconds_per_chunk=0.05):
        self.played = []
        self.stopped = 0
        self.dt = seconds_per_chunk

    def play(self, audio, sr, stop):
        self.played.append(len(audio))
        stop.wait(self.dt)

    def stop(self):
        self.stopped += 1


def test_player_plays_in_order_and_goes_idle():
    backend = FakeBackend(0.01)
    p = AudioPlayer(backend)
    started = []
    for n in (100, 200, 300):
        p.play(np.zeros(n, np.float32), 16000, on_start=lambda n=n: started.append(n))
    assert p.wait_idle(2)
    assert backend.played == [100, 200, 300] and started == [100, 200, 300]
    p.close()


def test_player_stop_drops_queue():
    backend = FakeBackend(0.2)
    p = AudioPlayer(backend)
    for _ in range(5):
        p.play(np.zeros(10, np.float32), 16000)
    time.sleep(0.05)
    p.stop()
    assert p.wait_idle(1)
    assert len(backend.played) == 1                # only the one already playing
    p.close()


def test_player_skips_cancelled_tokens():
    backend = FakeBackend(0.01)
    p = AudioPlayer(backend)
    state = SharedState()
    token = state.token()
    state.cancel_all()
    p.play(np.zeros(10, np.float32), 16000, token)
    assert p.wait_idle(1) and backend.played == []
    p.close()


# ---- capture --------------------------------------------------------------------

def test_recorder_keeps_only_frames_while_recording():
    r = MicRecorder(sample_rate=100, max_seconds=10)
    r.feed(np.ones(50, np.float32))                # before begin: discarded
    r.begin()
    r.feed(np.full(30, 2, np.float32))
    r.feed(np.full(20, 3, np.float32))
    audio = r.end()
    r.feed(np.ones(50, np.float32))                # after end: discarded
    assert audio.tolist() == [2] * 30 + [3] * 20
    assert r.end().size == 0


def test_recorder_caps_length():
    r = MicRecorder(sample_rate=10, max_seconds=2)  # 20 samples max
    r.begin()
    for _ in range(5):
        r.feed(np.ones(8, np.float32))
    assert len(r.end()) == 20


def test_push_to_talk_ignores_key_repeat_and_other_keys():
    events = []
    ptt = PushToTalk("ctrl_r", lambda: events.append("down"), lambda: events.append("up"))
    ptt._key = "K"                                  # stand-in for the parsed pynput key
    for key in ["K", "K", "K", "X", "K"]:            # Windows repeats key-down while held
        ptt.handle_press(key)
    ptt.handle_release("X")
    ptt.handle_release("K")
    ptt.handle_release("K")
    assert events == ["down", "up"]
