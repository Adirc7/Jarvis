"""Bing and YouTube by voice (tools/web.py)."""

import io
import json

import pytest
from conftest import FakeClient

from jarvis.agent.llm import FallbackLLM, Provider
from jarvis.app import App
from jarvis.telemetry import Telemetry
from jarvis.tools import web
from jarvis.tools.web import WebTools, bing_url, youtube_results_url, youtube_watch_url

VIDEOS = [("a1", "Fourier Series Explained"), ("b2", "MIT 18.03 Lecture 15"), ("c3", "Fourier in 10 minutes")]


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(videos=VIDEOS, error=None):
    opened, keys, clock = [], [], Clock()

    def search(q):
        if error:
            raise error
        return list(videos)

    tools = WebTools(opener=opened.append, media_key=lambda: keys.append("play/pause"),
                     search_videos=search if videos is not None else None, clock=clock)
    return tools, opened, keys, clock


def test_urls_encode_english_and_sinhala():
    assert bing_url() == "https://www.bing.com"
    assert bing_url("C++ tutorials") == "https://www.bing.com/search?q=C%2B%2B+tutorials"
    assert bing_url("ප්‍රක්ෂිප්ත චලිතය").startswith("https://www.bing.com/search?q=%E0%B6%B4")
    assert youtube_results_url("lofi music") == "https://www.youtube.com/results?search_query=lofi+music"
    assert youtube_watch_url("a1") == "https://www.youtube.com/watch?v=a1"


def test_only_bing_and_youtube_can_be_opened():
    with pytest.raises(ValueError):
        web.open_in_browser("https://example.com/login", browser="default")


def test_open_bing_then_say_what_to_search():
    tools, opened, _, _ = make()
    r = tools.handle("Jarvis, open Bing.")
    assert r.tool == "bing_open" and r.text == "Bing is open, sir. What should I search for?"
    r = tools.handle("Fourier series examples")
    assert r.text == "Here are the results for Fourier series examples, sir."
    assert opened == ["https://www.bing.com", "https://www.bing.com/search?q=Fourier+series+examples"]
    assert tools.handle("Fourier series examples") is None          # the question was answered once


@pytest.mark.parametrize("text, query", [
    ("search Bing for the RC time constant", "the RC time constant"),
    ("look up Maxwell's equations on Bing", "Maxwell's equations"),
    ("bing eke fourier series hoyanna", "fourier series"),
    ("fourier series bing eke search karala denna", "fourier series"),
    ("ප්‍රක්ෂිප්ත චලිතය බිං එකේ හොයන්න", "ප්‍රක්ෂිප්ත චලිතය"),
    ("බිං එකේ ලැප්ටොප් මිල ගණන් හොයලා දෙන්න", "ලැප්ටොප් මිල ගණන්"),
])
def test_search_bing_in_one_go(text, query):
    tools, opened, _, _ = make()
    r = tools.handle(text)
    assert r.tool == "bing_search" and opened == [bing_url(query)]


@pytest.mark.parametrize("text", ["bing eka open karanna", "බිං එක ඕපන් කරන්න", "Friday, open Bing", "bing"])
def test_open_bing_in_every_language(text):
    tools, opened, _, _ = make()
    assert tools.handle(text).tool == "bing_open" and opened == ["https://www.bing.com"]


def test_cancel_and_expiry():
    tools, opened, _, clock = make()
    tools.handle("open Bing")
    assert tools.handle("never mind").text == "Alright."
    assert tools.handle("something") is None
    tools.handle("open Bing")
    clock.now += 61                                                 # the question expired
    assert tools.handle("something") is None and len(opened) == 2


def test_youtube_search_choose_pause_back():
    tools, opened, keys, _ = make()
    assert tools.handle("open YouTube").text == "Which video would you like to watch, sir?"
    r = tools.handle("Fourier series lecture")
    assert r.tool == "youtube_search"
    assert r.text == ("I found 1, Fourier Series Explained; 2, MIT 18.03 Lecture 15; 3, Fourier in 10 minutes. "
                      "Which one should I play?")
    r = tools.handle("play the second one")
    assert r.text == "Playing MIT 18.03 Lecture 15." and opened[-1] == youtube_watch_url("b2")
    r = tools.handle("stop the video")
    assert r.text == "Paused. Would you like to search for anything else, sir?" and keys == ["play/pause"]
    assert tools.handle("no").text == "Alright."
    assert tools.handle("go back").text == "Going back."
    assert opened[-1] == youtube_results_url("Fourier series lecture")
    tools.handle("go back")
    assert opened[-1] == "https://www.youtube.com"
    assert tools.handle("go back").text == "There's no page to go back to."


def test_after_pausing_yes_asks_and_a_topic_searches():
    tools, opened, keys, _ = make()
    tools.handle("youtube eke lofi music danna")
    tools.handle("palaweni eka")
    tools.handle("video eka nawaththanna")
    assert tools.handle("yes").text == "What should I search for?"
    assert tools.handle("thermodynamics lecture").tool == "youtube_search"
    tools.handle("first")
    tools.handle("pause")
    assert tools.handle("calculus revision").tool == "youtube_search"   # answers "anything else?" directly


def test_resume_and_double_pause():
    tools, _, keys, _ = make()
    tools.handle("play fourier series on YouTube")
    tools.handle("first")
    tools.handle("pause the video")
    tools.handle("no")
    assert tools.handle("pause").text == "Nothing is playing right now." and keys == ["play/pause"]
    assert tools.handle("resume the video").text == "Playing again." and keys == ["play/pause"] * 2


def test_without_an_api_key_youtube_opens_the_results_page():
    tools, opened, _, _ = make(videos=None)
    r = tools.handle("search YouTube for the Doppler effect")
    assert r.tool == "youtube_results_page" and opened == [youtube_results_url("the Doppler effect")]


def test_a_failing_search_still_opens_the_results_page():
    tools, opened, _, _ = make(error=OSError("quota exceeded"))
    assert tools.handle("search YouTube for optics").tool == "youtube_results_page"
    assert opened == [youtube_results_url("optics")]


def test_moving_on_during_a_choice_is_not_an_error():
    tools, opened, _, _ = make()
    tools.handle("search YouTube for optics")
    assert tools.handle("what is entropy") is None                 # the model answers it normally
    assert tools.pending is None


def test_a_command_while_jarvis_waits_is_a_command():
    tools, opened, _, _ = make()
    tools.handle("open YouTube")
    assert tools.handle("Friday, open Bing").tool == "bing_open"
    assert opened == ["https://www.youtube.com", "https://www.bing.com"]


@pytest.mark.parametrize("text", [
    "what is entropy", "open Chrome", "play some music", "stop", "explain the Fourier transform",
    "I watched a YouTube video about this", "is Bing better than Google", "back to the lecture notes",
])
def test_nothing_else_opens_a_page(text):
    tools, opened, keys, _ = make()
    assert tools.handle(text) is None and opened == [] and keys == []


def test_friday_speaks_sinhala():
    tools, _, _, _ = make()
    assert tools.handle("යූටියුබ් එක ඕපන් කරන්න", "si").text == "මොන වීඩියෝ එකද බලන්න ඕනේ?"
    assert tools.handle("open Bing", "si").text == "බිං එක ඕපන් කළා. මොනවද හොයන්න ඕනේ?"


def test_youtube_api_search_reads_titles(monkeypatch):
    payload = {"items": [{"id": {"videoId": "x1"}, "snippet": {"title": "Ohm&#39;s law &amp; circuits"}},
                         {"id": {"kind": "channel"}, "snippet": {"title": "a channel"}}]}
    monkeypatch.setattr(web.urllib.request, "urlopen",
                        lambda url, timeout: io.BytesIO(json.dumps(payload).encode()))
    assert web.youtube_api_search("ohms law", "KEY") == [("x1", "Ohm's law & circuits")]


async def test_jarvis_uses_the_tools_before_the_model(settings):
    tools, opened, keys, _ = make()
    client = FakeClient(["From the model."])
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", client)]), web=tools,
              out=lambda *a, **k: None)
    assert await app.handle_text("open YouTube") == "Which video would you like to watch, sir?"
    assert await app.handle_text("Fourier series") == (
        "I found 1, Fourier Series Explained; 2, MIT 18.03 Lecture 15; 3, Fourier in 10 minutes. "
        "Which one should I play?")
    assert await app.handle_text("what is entropy") == "From the model."
    assert client.calls == 1
    assert [m["content"] for m in app.history][:2] == ["open YouTube", "Which video would you like to watch, sir?"]


async def test_the_kill_switch_forgets_the_question(settings):
    import asyncio

    from jarvis.events import KillSwitchPressed
    tools, opened, _, _ = make()
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", FakeClient(["Ok."]))]),
              web=tools, out=lambda *a, **k: None)
    app.bus.bind()
    task = asyncio.create_task(app._control_task())
    await app.handle_text("open Bing")
    await asyncio.sleep(0)
    app.bus.publish(KillSwitchPressed(source="test"))
    await asyncio.sleep(0.01)
    task.cancel()
    assert tools.pending is None
    assert await app.handle_text("Fourier series") == "Ok."                # not taken as the search
