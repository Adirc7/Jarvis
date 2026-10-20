"""Greetings follow sessions, like a person would, not every restart."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from jarvis.app import App
from jarvis.greeting import FULL, PICKUP, SAME_SESSION, Greeter, Presence, fill, greeting_kind, part_of_day
from jarvis.telemetry import Telemetry
from jarvis.voice.sink import TextSink

EVENING = datetime(2026, 10, 21, 19, 30)


def test_part_of_day_boundaries():
    assert [part_of_day(h) for h in (4, 5, 11, 12, 16, 17, 20, 21, 0)] == [
        "night", "morning", "morning", "afternoon", "afternoon", "evening", "evening", "night", "night"]


def test_kind_first_time_today_is_full():
    assert greeting_kind(EVENING, None, None) == FULL
    assert greeting_kind(EVENING, EVENING - timedelta(hours=20), date(2026, 10, 20)) == FULL


def test_kind_within_session_is_no_greeting():
    assert greeting_kind(EVENING, EVENING - timedelta(minutes=10), EVENING.date()) == SAME_SESSION
    assert greeting_kind(EVENING, EVENING - timedelta(minutes=15), EVENING.date()) == SAME_SESSION


def test_kind_after_a_break_is_pickup():
    assert greeting_kind(EVENING, EVENING - timedelta(minutes=16), EVENING.date()) == PICKUP
    assert greeting_kind(EVENING, EVENING - timedelta(hours=5), EVENING.date()) == PICKUP


def test_session_carries_on_across_midnight():
    now = datetime(2026, 10, 22, 0, 5)
    assert greeting_kind(now, datetime(2026, 10, 21, 23, 58), date(2026, 10, 21)) == SAME_SESSION
    assert greeting_kind(now, datetime(2026, 10, 21, 23, 0), date(2026, 10, 21)) == FULL


def test_setting_changes_the_window():
    assert greeting_kind(EVENING, EVENING - timedelta(minutes=18), EVENING.date(), 20) == SAME_SESSION


def test_fill_with_and_without_address():
    assert fill("Good evening, {address}.", "sir") == "Good evening, sir."
    assert fill("Good evening, {address}.", "") == "Good evening."
    assert fill("Still up, {address}? What do you need?", "") == "Still up? What do you need?"


def test_greeter_never_repeats_twice_in_a_row():
    g = Greeter(random.Random(1))
    lines = {"same_session": ("I'm here, {address}.", "Yes, {address}?")}
    picks = [g.pick(SAME_SESSION, EVENING, lines, "sir") for _ in range(10)]
    assert all(a != b for a, b in zip(picks, picks[1:]))
    assert g.pick(FULL, EVENING, {}, "sir") is None


def test_presence_round_trip_and_damaged_file(tmp_path):
    path = tmp_path / "presence.json"
    p = Presence(path)
    p.touch(EVENING)
    p.last_full = EVENING.date()
    p.save()
    back = Presence.load(path)
    assert back.last_active == EVENING and back.last_full == EVENING.date()
    path.write_text("not json", encoding="utf-8")
    assert Presence.load(path).last_active is None


def _app(settings, tmp_path, out):
    return App(settings, Telemetry.disabled(), sink=TextSink(out), out=out,
               presence=Presence(tmp_path / "presence.json"))


async def test_app_greets_once_then_carries_on(settings, tmp_path):
    lines: list[str] = []
    app = _app(settings, tmp_path, lambda *a, **k: lines.append(" ".join(map(str, a))))
    first = await app.greet(EVENING)
    assert first in ("Good evening, sir.", "Evening, sir. What are we working on?")
    assert app.presence.last_full == EVENING.date()
    assert "Don't greet the user again" in app.system_prompt()

    again = _app(settings, tmp_path, lambda *a, **k: None)          # restarted 5 minutes later
    again.presence = Presence.load(tmp_path / "presence.json")
    assert await again.greet(EVENING + timedelta(minutes=5)) in ("I'm here, sir.", "Yes, sir?")

    later = _app(settings, tmp_path, lambda *a, **k: None)          # back after two hours
    later.presence = Presence.load(tmp_path / "presence.json")
    assert (await later.greet(EVENING + timedelta(hours=2))).startswith(("Welcome back", "Back again"))


async def test_app_greets_in_the_current_language(settings, tmp_path):
    app = _app(settings, tmp_path, lambda *a, **k: None)
    app.lang.set("si", source="test")
    assert await app.greet(EVENING) == "සුභ සන්ධ්‍යාවක්!"


async def test_greeting_can_be_turned_off(settings, tmp_path):
    settings.raw.setdefault("greeting", {})["enabled"] = False
    app = _app(settings, tmp_path, lambda *a, **k: None)
    assert await app.greet(EVENING) is None
