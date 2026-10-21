"""Jarvis's light memory between sessions (jarvis/memory)."""

from datetime import datetime, timedelta

import pytest

from conftest import FakeClient
from jarvis.agent.llm import FallbackLLM, Provider
from jarvis.app import App
from jarvis.memory import Memory, detect_fact, detect_name
from jarvis.telemetry import Telemetry


@pytest.mark.parametrize("text, name", [
    ("My name is Adithya", "Adithya"),
    ("my name is adithya bandara.", "Adithya Bandara"),
    ("Jarvis, call me Adhi.", "Adhi"),
    ("call me Adhi please", "Adhi"),
    ("මගේ නම අදිත්‍ය", "අදිත්‍ය"),
    ("මගේ නම අදිත්‍යයි.", "අදිත්‍ය"),
])
def test_names_are_recognised(text, name):
    assert detect_name(text) == name


@pytest.mark.parametrize("text", ["call me later", "Can you call me tomorrow?", "what's my name?", "name the file"])
def test_not_names(text):
    assert detect_name(text) is None


@pytest.mark.parametrize("text, fact", [
    ("Remember that my exam is on Friday.", "my exam is on Friday"),
    ("Jarvis, remember I study physical science", "I study physical science"),
    ("මම ෆිසික්ස් කරන්නේ කියලා මතක තියාගන්න", "මම ෆිසික්ස් කරන්නේ"),
])
def test_facts_are_recognised(text, fact):
    assert detect_fact(text) == fact


@pytest.mark.parametrize("text", ["Remember to submit the report", "Do you remember what I said?", "hello"])
def test_not_facts(text):
    assert detect_fact(text) is None


def test_save_load_and_forget(tmp_path):
    path = tmp_path / "memory.json"
    m = Memory(path)
    m.set_name("Adhi")
    assert m.remember("my exam is on Friday") and not m.remember("My exam is on Friday")   # no duplicates
    m.set_recent([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello, sir."}])
    m.save()
    back = Memory.load(path)
    assert back.name == "Adhi" and back.facts[0]["text"] == "my exam is on Friday" and len(back.recent) == 2
    back.forget()
    back.save()
    assert Memory.load(path).describe().startswith("name: (not set)")


def test_damaged_file_means_nothing_remembered(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("{not json", encoding="utf-8")
    assert Memory.load(path).name == ""


def test_old_conversation_is_not_continued(tmp_path):
    m = Memory(tmp_path / "m.json")
    m.set_recent([{"role": "user", "content": "hi"}], now=datetime(2026, 10, 21, 8, 0))
    assert m.recent_if_fresh(12, now=datetime(2026, 10, 21, 18, 0)) != []
    assert m.recent_if_fresh(12, now=datetime(2026, 10, 21, 8, 0) + timedelta(hours=13)) == []


def _app(settings, pieces=("Noted, Adhi.",)):
    client = FakeClient(list(pieces))
    out = []
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", client)]),
              out=lambda *a, **k: out.append("".join(map(str, a))))
    return app, client, out


async def test_name_survives_a_restart(settings):
    # 21 Oct on the laptop: Adhi gave his name, restarted Jarvis, and it had forgotten.
    app, _, out = _app(settings)
    await app.handle_text("My name is Adhi")
    assert any("remember your name: Adhi" in line for line in out)

    app2, client2, _ = _app(settings, ["Your name is Adhi, sir."])
    await app2.handle_text("What's my name?")
    system = client2.last_messages[0]["content"]
    assert "The user's name is Adhi" in system
    assert any(m["content"] == "My name is Adhi" for m in client2.last_messages)   # the conversation carried on


async def test_facts_reach_the_prompt(settings):
    app, client, _ = _app(settings, ["Noted."])
    await app.handle_text("Remember that my exam is on Friday")
    await app.handle_text("When is my exam?")
    assert "- my exam is on Friday" in client.last_messages[0]["content"]


async def test_forget_command_clears_everything(settings):
    app, _, out = _app(settings)
    await app.handle_text("Call me Adhi")
    await app._command("/forget")
    app2, client2, _ = _app(settings, ["Hello."])
    await app2.handle_text("hello")
    assert "Adhi" not in client2.last_messages[0]["content"]
    assert len(client2.last_messages) == 2                    # system + this message: no old conversation


async def test_memory_can_be_switched_off(settings):
    settings.raw["memory"] = {"enabled": False}
    app, _, _ = _app(settings)
    await app.handle_text("My name is Adhi")
    app2, client2, _ = _app(settings, ["Hello."])
    await app2.handle_text("hi")
    assert "Adhi" not in client2.last_messages[0]["content"]


def test_misheard_sinhala_still_switches(settings):
    from jarvis.language import LanguageManager
    lm = LanguageManager(settings.languages, "en")
    assert lm.detect_switch("Can we speak in singular language?") == "si"     # Whisper's "Sinhala", 21 Oct
    assert lm.detect_switch("Is data a singular or plural noun in English grammar?") is None
