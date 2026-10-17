import asyncio
from datetime import datetime

from conftest import FakeClient
from jarvis.agent.llm import FallbackLLM, Provider
from jarvis.app import App
from jarvis.persona import Persona, time_context
from jarvis.telemetry import Telemetry
from jarvis.voice.effects import VoiceStyle
from jarvis.voice.player import AudioPlayer
from jarvis.voice.sink import VoiceSink
from jarvis.voice.tts import TTSRouter
from test_voice_pipeline import FakeEngine, RecordingBackend


# ---- persona -------------------------------------------------------------------

def test_persona_file_loads_with_three_modes():
    p = Persona.load()
    assert p.name == "Jarvis"
    assert set(p.modes) == {"logical", "balanced", "supportive"}
    assert p.default_mode == "balanced"
    assert p.modes["supportive"].speed < 1.0


def test_system_prompt_has_character_honesty_and_context():
    p = Persona.load()
    prompt = p.system_prompt(language_instruction="Reply in English.", spoken=True, mode="supportive",
                             now=datetime(2026, 10, 17, 19, 40))
    assert "You are Jarvis" in prompt
    assert "you're an AI" in prompt                          # honest about being an AI
    assert "Emotional style (supportive)" in prompt
    assert "spoken aloud" in prompt
    assert "Saturday evening, 17 October 2026, 7:40 pm" in prompt
    assert "can't yet" in prompt                             # never promises missing abilities


def test_user_name_only_when_set():
    p = Persona.load()
    assert "user's name" not in p.system_prompt(language_instruction="", spoken=False, mode="balanced")
    p.user_name = "Adhi"
    assert "The user's name is Adhi" in p.system_prompt(language_instruction="", spoken=False, mode="balanced")


def test_time_of_day_buckets():
    assert "morning" in time_context(datetime(2026, 1, 1, 8, 0))
    assert "afternoon" in time_context(datetime(2026, 1, 1, 13, 0))
    assert "evening" in time_context(datetime(2026, 1, 1, 18, 0))
    assert "night" in time_context(datetime(2026, 1, 1, 2, 0))
    assert "night" in time_context(datetime(2026, 1, 1, 23, 0))


def test_mode_phrases():
    p = Persona.load()
    assert p.detect_mode_command("Jarvis, be more direct please") == "logical"
    assert p.detect_mode_command("Can you be gentler?") == "supportive"
    assert p.detect_mode_command("back to normal") == "balanced"
    assert p.detect_mode_command("what does it mean to be more direct in an essay about leadership") is None
    assert p.detect_mode_command("open chrome") is None


# ---- app: empathy modes ----------------------------------------------------------

def make_voice_app(settings, pieces, delay=0.0):
    spoken = []
    engines = {}

    def factory(lang, s):
        engines[lang.code] = FakeEngine(lang.code, spoken)
        return engines[lang.code]

    router = TTSRouter(settings, style=VoiceStyle(enabled=False), factory=factory)
    backend = RecordingBackend()
    out = []
    sink = VoiceSink(settings, router, AudioPlayer(backend), out=lambda *a, **k: out.append("".join(map(str, a))))
    client = FakeClient(pieces)
    if delay:
        original = client.create

        async def slow_create(*a, **k):
            await asyncio.sleep(delay)
            return await original(*a, **k)
        client.chat.completions.create = slow_create
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", client)]), sink=sink, out=sink.out)
    return app, spoken, engines, client


async def test_mode_phrase_switches_style_and_still_answers(settings):
    app, spoken, engines, client = make_voice_app(settings, ["Sure, I'll keep it short."])
    reply = await app.handle_text("be more direct")
    assert app.state.empathy == "logical"
    assert reply == "Sure, I'll keep it short."               # the model acknowledges it itself
    assert "Emotional style (logical)" in client.last_messages[0]["content"]


async def test_supportive_mode_slows_the_voice(settings):
    app, spoken, engines, client = make_voice_app(settings, ["Take your time."])
    assert app.set_empathy("supportive", source="test")
    await app.handle_text("I'm tired of this bug")
    assert engines["en"].last_speed == app.persona.modes["supportive"].speed < 1.0


async def test_unknown_mode_is_rejected(settings):
    app, *_ = make_voice_app(settings, ["x"])
    assert not app.set_empathy("sarcastic", source="test")
    assert app.state.empathy == "balanced"


# ---- fillers ----------------------------------------------------------------------

async def test_filler_plays_when_reply_is_slow(settings):
    app, spoken, engines, client = make_voice_app(settings, ["Here's the answer."], delay=0.25)
    app.sink.filler_after_s = 0.05
    app.sink.prepare_fillers(app.lang.current)
    spoken.clear()                                            # forget the pre-rendering
    reply = await app.handle_text("what's the weather like")
    assert reply == "Here's the answer."
    assert spoken == [("en", "Here's the answer.")]           # the real reply was synthesized...
    assert len(app.sink.player.backend.played) == 2           # ...and a filler played before it


async def test_no_filler_when_reply_is_fast(settings):
    app, spoken, engines, client = make_voice_app(settings, ["Quick answer."])
    app.sink.filler_after_s = 0.5
    app.sink.prepare_fillers(app.lang.current)
    await app.handle_text("hi")
    assert len(app.sink.player.backend.played) == 1


async def test_fillers_do_not_repeat_back_to_back(settings):
    app, *_ = make_voice_app(settings, ["x"])
    sink = app.sink
    sink.prepare_fillers(app.lang.current)
    picks = []
    for _ in range(20):
        options = sink._fillers["en"]
        choices = [i for i in range(len(options)) if i != sink._last_filler.get("en")]
        i = sink._rng.choice(choices)
        sink._last_filler["en"] = i
        picks.append(i)
    assert all(a != b for a, b in zip(picks, picks[1:]))


async def test_muted_means_no_filler(settings):
    app, spoken, engines, client = make_voice_app(settings, ["Slow."], delay=0.2)
    app.sink.filler_after_s = 0.05
    app.sink.prepare_fillers(app.lang.current)
    app.sink.toggle_mute()
    await app.handle_text("hello")
    assert app.sink.player.backend.played == []
