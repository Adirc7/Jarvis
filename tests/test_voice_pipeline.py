"""The whole voice turn with fakes for the hardware and models:
audio -> Transcriber -> App.handle_text -> LLM stream -> VoiceSink -> TTS -> player."""

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from conftest import FakeClient
from jarvis.agent.llm import FallbackLLM, Provider
from jarvis.app import App
from jarvis.language import LanguageManager
from jarvis.telemetry import Telemetry
from jarvis.voice.effects import VoiceStyle
from jarvis.voice.player import AudioPlayer
from jarvis.voice.sink import VoiceSink
from jarvis.voice.stt import Transcriber
from jarvis.voice.tts import TTSRouter


# ---- fakes ------------------------------------------------------------------

class FakeWhisper:
    """detect_language -> (lang, p); transcribe -> text chosen per language."""

    def __init__(self, detected=("en", 0.99), texts=None):
        self.detected = detected
        self.texts = texts or {}
        self.transcribe_languages = []
        self.transcribe_options = []
        self.detect_calls = 0

    def detect_language(self, audio):
        self.detect_calls += 1
        return self.detected[0], self.detected[1], []

    def transcribe(self, audio, language=None, **kwargs):
        self.transcribe_languages.append(language)
        self.transcribe_options.append(kwargs)
        text = self.texts.get(language, "")
        return [SimpleNamespace(text=text)], SimpleNamespace(language=language)


class FakeEngine:
    sample_rate = 16000

    def __init__(self, lang_code, log):
        self.lang_code = lang_code
        self.log = log

    def synthesize(self, text, speed_factor=1.0):
        self.log.append((self.lang_code, text))
        self.last_speed = speed_factor
        return np.zeros(len(text) * 10, np.float32)


class RecordingBackend:
    def __init__(self):
        self.played = []

    def play(self, audio, sr, stop):
        self.played.append(len(audio))
        stop.wait(0.005)

    def stop(self):
        pass


def make_voice_app(settings, llm_pieces, whisper):
    spoken = []
    out = []
    router = TTSRouter(settings, style=VoiceStyle(enabled=False),
                       factory=lambda lang, s: FakeEngine(lang.code, spoken))
    backend = RecordingBackend()
    sink = VoiceSink(settings, router, AudioPlayer(backend), out=lambda *a, **k: out.append("".join(map(str, a))))
    llm = FallbackLLM([Provider("fake", "m", FakeClient(llm_pieces))])
    app = App(settings, Telemetry.disabled(), llm=llm, sink=sink, out=sink.out)
    app.transcriber = Transcriber(settings, app.lang, loader=lambda name: whisper)
    return app, spoken, backend, out


AUDIO = np.zeros(16000, np.float32)


async def _run_voice_loop(app, out, *events):
    task = asyncio.create_task(app._voice_task())
    await asyncio.sleep(0)                                  # let it subscribe
    for ev in events:
        app.bus.publish(ev)
    for _ in range(200):                                    # until the turn has been answered
        await asyncio.sleep(0.01)
        if any(line.startswith("You [") for line in out) and app.state.mode.name == "IDLE":
            break
    task.cancel()


async def test_recording_limit_is_reported(settings):
    from jarvis.events import UtteranceCaptured
    app, spoken, backend, out = make_voice_app(settings, ["Sure."], FakeWhisper(texts={"en": "hello"}))
    await _run_voice_loop(app, out, UtteranceCaptured(audio=np.zeros(30 * 16000, np.float32), seconds=30.0))
    assert any("30-second limit" in line for line in out)


async def test_normal_recording_has_no_limit_note(settings):
    from jarvis.events import UtteranceCaptured
    app, spoken, backend, out = make_voice_app(settings, ["Sure."], FakeWhisper(texts={"en": "hello"}))
    await _run_voice_loop(app, out, UtteranceCaptured(audio=AUDIO, seconds=1.0))
    assert not any("limit" in line for line in out)
    assert any("hello" in line for line in out)


# ---- Transcriber ----------------------------------------------------------------

def test_transcribes_in_active_language(settings):
    w = FakeWhisper(detected=("si", 0.9), texts={"si": "ආයුබෝවන්"})
    lm = LanguageManager(settings.languages, "si")
    r = Transcriber(settings, lm, loader=lambda n: w).transcribe(AUDIO)
    assert r.text == "ආයුබෝවන්" and r.language == "si" and not r.retranscribed
    assert w.transcribe_languages == ["si"]


def test_escape_hatch_hears_english_in_sinhala_mode(settings):
    w = FakeWhisper(detected=("en", 0.97), texts={"en": "switch to English", "si": "garbage"})
    lm = LanguageManager(settings.languages, "si")
    r = Transcriber(settings, lm, loader=lambda n: w).transcribe(AUDIO)
    assert r.text == "switch to English" and r.language == "en" and r.retranscribed


def test_low_confidence_detection_keeps_active_language(settings):
    w = FakeWhisper(detected=("en", 0.5), texts={"en": "x", "si": "සිංහල"})
    lm = LanguageManager(settings.languages, "si")
    r = Transcriber(settings, lm, loader=lambda n: w).transcribe(AUDIO)
    assert r.language == "si"


def test_models_are_cached_per_name(settings):
    loads = []
    w = FakeWhisper(texts={"en": "hi"})
    lm = LanguageManager(settings.languages, "en")
    t = Transcriber(settings, lm, loader=lambda n: loads.append(n) or w)
    t.transcribe(AUDIO)
    t.transcribe(AUDIO)
    assert loads == [settings.get("stt.model")]


def test_warm_up_runs_the_model_once_with_and_without_vad(settings):
    loads = []
    w = FakeWhisper()
    lm = LanguageManager(settings.languages, "en")
    Transcriber(settings, lm, loader=lambda n: loads.append(n) or w).warm_up()
    assert loads == [settings.get("stt.model")]                # one model shared by every language
    assert w.detect_calls == 1
    assert [o["vad_filter"] for o in w.transcribe_options] == [True, False]
    assert all(o["max_new_tokens"] <= 8 for o in w.transcribe_options)     # stays quick


def test_warm_up_failure_is_logged_not_raised(settings, tmp_path):
    import json

    class BrokenWhisper(FakeWhisper):
        def transcribe(self, audio, language=None, **kwargs):
            raise RuntimeError("cuDNN not found")

    tel = Telemetry(tmp_path / "t.jsonl")
    lm = LanguageManager(settings.languages, "en")
    Transcriber(settings, lm, telemetry=tel, loader=lambda n: BrokenWhisper()).warm_up()
    events = [json.loads(line) for line in (tmp_path / "t.jsonl").read_text(encoding="utf-8").splitlines()]
    warm = [e for e in events if e["event"] == "stt_warm"]
    assert len(warm) == 1 and "cuDNN" in warm[0]["error"]


# ---- full voice turns -----------------------------------------------------------

async def test_voice_turn_speaks_reply_sentence_by_sentence(settings):
    pieces = ["Good evening. ", "All systems ", "are running normally ", "and nothing needs your attention."]
    app, spoken, backend, out = make_voice_app(settings, pieces, FakeWhisper(texts={"en": "status report"}))
    reply = await app.voice_turn(AUDIO, 1.0)
    assert reply == "".join(pieces)
    assert spoken == [("en", "Good evening."),
                      ("en", "All systems are running normally and nothing needs your attention.")]
    assert len(backend.played) == 2
    assert any("You [English" in line for line in out)


async def test_spoken_language_switch_uses_new_voice(settings):
    app, spoken, backend, out = make_voice_app(settings, ["unused"], FakeWhisper(texts={"en": "switch to Tamil"}))
    await app.voice_turn(AUDIO, 1.0)
    assert app.state.language == "ta"
    assert spoken == [("ta", settings.languages["ta"].confirm)]


async def test_mute_prints_but_does_not_speak(settings):
    app, spoken, backend, out = make_voice_app(settings, ["Hello there, Adhi."], FakeWhisper(texts={"en": "hi"}))
    app.sink.toggle_mute()
    reply = await app.voice_turn(AUDIO, 1.0)
    assert reply == "Hello there, Adhi." and spoken == [] and backend.played == []


async def test_kill_switch_mid_reply_stops_speech(settings):
    pieces = [f"Sentence number {i} is here. " for i in range(20)]
    app, spoken, backend, out = make_voice_app(settings, pieces, FakeWhisper(texts={"en": "talk a lot"}))
    app.bus.bind()

    async def press_kill_soon():
        while not spoken:
            await asyncio.sleep(0.001)
        app.state.cancel_all()
        app.sink.stop()

    killer = asyncio.create_task(press_kill_soon())
    await app.voice_turn(AUDIO, 1.0)
    await killer
    assert len(spoken) < 20


async def test_empty_transcript_is_ignored(settings):
    app, spoken, backend, out = make_voice_app(settings, ["x"], FakeWhisper(texts={"en": ""}))
    assert await app.voice_turn(AUDIO, 1.0) is None
    assert spoken == [] and any("didn't catch" in line for line in out)


async def test_broken_voice_falls_back_to_text(settings):
    def broken_factory(lang, s):
        raise FileNotFoundError("Kokoro files missing")
    out = []
    sink = VoiceSink(settings, TTSRouter(settings, style=VoiceStyle(enabled=False), factory=broken_factory),
                     AudioPlayer(RecordingBackend()), out=lambda *a, **k: out.append("".join(map(str, a))))
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", FakeClient(["Hi."]))]), sink=sink)
    assert await app.handle_text("hello") == "Hi."
    assert sum("voice unavailable" in line for line in out) == 1


def test_system_prompt_asks_for_speakable_replies(settings):
    app, *_ = make_voice_app(settings, ["x"], FakeWhisper())
    assert "spoken aloud" in app.system_prompt()


# ---- real Kokoro, only where the model files exist ------------------------------

KOKORO_DIR = Path(os.environ.get("JARVIS_KOKORO_DIR", Path(__file__).resolve().parents[1] / "models"))


@pytest.mark.skipif(not (KOKORO_DIR / "kokoro-v1.0.onnx").is_file(), reason="Kokoro model not downloaded")
def test_real_kokoro_british_voice(settings):
    pytest.importorskip("kokoro_onnx")
    from jarvis.voice.tts import KokoroTTS
    tts = KokoroTTS(KOKORO_DIR / "kokoro-v1.0.onnx", KOKORO_DIR / "voices-v1.0.bin", "bm_george", "en-gb")
    audio = tts.synthesize("Good evening.")
    assert tts.sample_rate == 24000 and 0.4 < len(audio) / 24000 < 3
    styled = VoiceStyle().process(audio, tts.sample_rate)
    assert np.max(np.abs(styled)) <= 1.0


def test_kokoro_session_uses_cpu_without_a_gpu(monkeypatch, tmp_path):
    rt = pytest.importorskip("onnxruntime")
    from jarvis.voice import tts as tts_mod
    made = {}

    class FakeSession:
        def __init__(self, path, opts, providers):
            made["providers"] = providers

    monkeypatch.setattr(rt, "InferenceSession", FakeSession)
    monkeypatch.setattr(rt, "get_available_providers", lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"])
    import jarvis.gpu as gpu
    monkeypatch.setattr(gpu, "cuda_device_count", lambda: 0)          # GPU build installed, no NVIDIA card
    tts_mod.kokoro_session(tmp_path / "m.onnx", "auto")
    assert made["providers"] == ["CPUExecutionProvider"]

    monkeypatch.setattr(gpu, "cuda_device_count", lambda: 1)
    monkeypatch.setattr(gpu, "prepare_cuda", lambda: [])
    tts_mod.kokoro_session(tmp_path / "m.onnx", "auto")
    assert made["providers"] == [("CUDAExecutionProvider", tts_mod.CUDA_MEMORY_SAVER), "CPUExecutionProvider"]
    tts_mod.kokoro_session(tmp_path / "m.onnx", "auto", memory_saver=False)
    assert made["providers"] == ["CUDAExecutionProvider", "CPUExecutionProvider"]

    tts_mod.kokoro_session(tmp_path / "m.onnx", "cpu")
    assert made["providers"] == ["CPUExecutionProvider"]


def test_cpu_only_onnxruntime_never_asks_for_cuda(monkeypatch, tmp_path):
    rt = pytest.importorskip("onnxruntime")
    from jarvis.voice import tts as tts_mod
    made = {}
    monkeypatch.setattr(rt, "InferenceSession", lambda path, opts, providers: made.setdefault("p", providers))
    monkeypatch.setattr(rt, "get_available_providers", lambda: ["CPUExecutionProvider"])
    tts_mod.kokoro_session(tmp_path / "m.onnx", "cuda")
    assert made["p"] == ["CPUExecutionProvider"]


@pytest.mark.skipif(not (KOKORO_DIR / "kokoro-v1.0.onnx").is_file(), reason="Kokoro model not downloaded")
def test_jarvis_and_friday_share_one_kokoro(settings):
    pytest.importorskip("kokoro_onnx")
    from jarvis.voice.tts import KokoroTTS
    model, voices = KOKORO_DIR / "kokoro-v1.0.onnx", KOKORO_DIR / "voices-v1.0.bin"
    jarvis = KokoroTTS(model, voices, "bm_lewis", "en-gb", device="cpu")
    friday = KokoroTTS(model, voices, "bf_emma", "si", device="cpu")
    assert jarvis._kokoro is friday._kokoro                      # one model in memory
    audio = friday.synthesize("ආයුබෝවන්, මම ෆ්‍රයිඩේ.")
    assert 0.5 < len(audio) / friday.sample_rate < 5


def test_friday_in_sinhala_jarvis_in_english(settings):
    from jarvis.persona import Persona
    p = Persona.load()
    si = settings.languages["si"]
    prompt = p.system_prompt(language_instruction="", spoken=True, mode="balanced", assistant_name=si.assistant_name)
    assert prompt.startswith(f"You are {si.assistant_name}") and "JARVIS and FRIDAY" in prompt
    assert "two names" not in p.system_prompt(language_instruction="", spoken=True, mode="balanced")


def test_asking_for_friday_switches_to_sinhala(settings):
    lm = LanguageManager(settings.languages, "en")
    assert lm.detect_switch("talk to Friday") == "si"
    assert lm.detect_switch("Can I talk to Friday?") == "si"
    assert lm.detect_switch("Jarvis please") == "en"
    assert lm.detect_switch("Can you change my meeting to Friday?") is None   # just a weekday


async def test_a_piece_the_voice_cant_say_doesnt_silence_the_rest(settings):
    from jarvis.voice.tts import TTSRouter

    class Picky(FakeEngine):
        def synthesize(self, text, speed_factor=1.0):
            if "Phonemeless" in text:
                raise ValueError("Nothing to synthesize, 'Phonemeless' produced no phonemes")
            return super().synthesize(text, speed_factor)

    spoken = []
    router = TTSRouter(settings, style=VoiceStyle(enabled=False), factory=lambda lang, s: Picky(lang.code, spoken))
    sink = VoiceSink(settings, router, AudioPlayer(RecordingBackend()), out=lambda *a, **k: None)
    llm = FallbackLLM([Provider("fake", "m", FakeClient([
        "The first sentence is fine here. ",
        "Phonemeless piece goes here now, long enough to be a piece of its own. ",
        "And the last sentence is fine too, and long enough to be spoken alone."]))])
    app = App(settings, Telemetry.disabled(), llm=llm, sink=sink, out=sink.out)
    await app.handle_text("tell me three things")
    said = " ".join(t for _, t in spoken)
    assert "first sentence" in said and "last sentence" in said
