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


@pytest.mark.parametrize("text, tool", [
    ("Can you open YouTube?", "youtube_open"),                     # the laptop, 24 Oct: the model answered this
    ("Could you please open YouTube for me", "youtube_open"),
    ("Jarvis, can you open up Bing please", "bing_open"),
    ("I want to watch YouTube", "youtube_open"),
    ("youtube eka balanna one", "youtube_open"),
    ("Can you find me Fourier series videos on YouTube?", "youtube_search"),
    ("could you search Bing for the Doppler effect", "bing_search"),
    ("Now I mean pause the video.", "media_pause"),                # the laptop, 24 Oct: the model answered this
    ("um, just stop the video", "media_pause"),
])
def test_polite_and_natural_requests(text, tool):
    tools, opened, keys, _ = make()
    assert tools.handle(text).tool == tool
    assert len(opened) + len(keys) == 1                  # one page opened, or the play/pause key pressed


@pytest.mark.parametrize("text", ["can you explain entropy", "what can you do", "can you open the door"])
def test_polite_questions_that_are_not_tools(text):
    tools, opened, _, _ = make()
    assert tools.handle(text) is None and opened == []


def test_the_model_knows_jarvis_can_open_youtube():
    from jarvis.persona import Persona
    prompt = Persona.load().system_prompt(language_instruction="Reply in English.", spoken=True, mode="balanced")
    assert "open Bing and YouTube" in prompt and "never say you can't do it" in prompt
    assert '"pause the video"' in prompt


# ---- the laptop, 25 Oct: these reached the model, which only repeated the command words ----
@pytest.mark.parametrize("text, tool", [
    ("Open the YouTube.", "youtube_open"),
    ("Jarvis, open up the YouTube website", "youtube_open"),
    ("go to the Bing home page", "bing_open"),
])
def test_open_with_the(text, tool):
    tools, opened, _, _ = make()
    assert tools.handle(text).tool == tool and len(opened) == 1


def test_open_youtube_then_play_the_first_one_asks_for_a_topic():
    tools, opened, _, _ = make()
    r = tools.handle("Open YouTube. Then play the first one.")
    assert r.tool == "youtube_need_topic" and r.text.startswith("Which video, sir?")
    assert opened == ["https://www.youtube.com"]
    assert tools.handle("Fourier series").tool == "youtube_search"        # the question is still open


def test_and_play_the_first_video_after_opening_youtube():
    tools, _, _, _ = make()
    tools.handle("Open the YouTube.")
    assert tools.handle("And play the first video.").tool == "youtube_need_topic"


@pytest.mark.parametrize("text", ["open YouTube and play lofi music", "Open YouTube. Then play lofi music.",
                                  "open YouTube, then search for lofi music"])
def test_open_youtube_and_play_something(text):
    tools, opened, _, _ = make()
    r = tools.handle(text)
    assert r.tool == "youtube_search" and opened[-1] == youtube_results_url("lofi music")


def test_a_search_with_and_in_it_is_not_split():
    tools, opened, _, _ = make()
    tools.handle("search Bing for cats and dogs")
    assert opened == [bing_url("cats and dogs")]
    tools.handle("play Romeo and Juliet on YouTube")
    assert opened[-1] == youtube_results_url("Romeo and Juliet")


def test_play_the_video_resumes_a_video_you_opened_yourself():
    tools, _, keys, _ = make()
    assert tools.handle("Jarvis, stop the video.").text == "Paused."          # a video Jarvis didn't open
    assert tools.handle("Jarvis, play the video.").tool == "media_resume" and keys == ["play/pause"] * 2


def test_a_bare_continue_is_not_a_video_command():
    tools, _, keys, _ = make()
    assert tools.handle("continue") is None and keys == []


def test_questions_with_and_still_go_to_the_model():
    tools, opened, keys, _ = make()
    for text in ["what is entropy and why does it increase", "explain Fourier series. Then give an example."]:
        assert tools.handle(text) is None
    assert opened == [] and keys == []


def test_the_model_never_answers_with_only_the_command_words():
    from jarvis.persona import Persona
    prompt = Persona.load().system_prompt(language_instruction="Reply in English.", spoken=True, mode="balanced")
    assert "never reply with only the command words" in prompt


# ---- the laptop, 25 Oct (second run): a misheard choice dropped the list ----
LUFFY = [("v1", "Best of lofi hip hop 2021 [beats to relax/study to]"),
         ("v2", "1 A.M Study Session [lofi hip hop]"),
         ("v3", "Future king of pirates || Luffy Edit - One Piece || #onepiece")]


@pytest.mark.parametrize("answer", ["the Luffy edit", "Can you play the Baka song, Luffy edit one piece?",
                                    "the one piece video"])
def test_choose_a_video_by_words_from_its_title(answer):
    tools, opened, _, _ = make(videos=LUFFY)
    tools.handle("Open YouTube and play lofi music.")
    r = tools.handle(answer)
    assert r.tool == "youtube_play" and opened[-1] == youtube_watch_url("v3")


def test_a_misheard_choice_is_asked_again_not_dropped():
    tools, opened, _, _ = make(videos=LUFFY)
    tools.handle("Open YouTube and play lofi music.")
    r = tools.handle("Play Festival.")                                   # Whisper, for "play the first one"
    assert r.tool == "youtube_which" and "which one" in r.text.lower()
    r = tools.handle("The first one that you mentioned.")
    assert r.tool == "youtube_play" and opened[-1] == youtube_watch_url("v1")


def test_asked_once_then_let_go():
    tools, opened, _, _ = make(videos=LUFFY)
    tools.handle("search YouTube for lofi")
    assert tools.handle("play festival").tool == "youtube_which"
    assert tools.handle("what is entropy") is None and tools.pending is None
    tools.handle("search YouTube for lofi")
    tools.handle("play festival")
    r = tools.handle("play carnival")                      # asked once already: a new search on YouTube
    assert r.tool == "youtube_search" and opened[-1] == youtube_results_url("carnival")


def test_play_something_while_youtube_is_open_searches_youtube():
    tools, opened, _, _ = make(videos=LUFFY)
    tools.handle("open YouTube")
    tools.handle("never mind")
    r = tools.handle("Can you play the Baka song?")
    assert r.tool == "youtube_search" and opened[-1] == youtube_results_url("Baka song")


def test_play_something_without_youtube_open_is_left_to_the_model():
    tools, opened, _, _ = make()
    assert tools.handle("play the Baka song") is None and opened == []


def test_the_model_never_invents_results():
    from jarvis.persona import Persona
    prompt = Persona.load().system_prompt(language_instruction="Reply in English.", spoken=True, mode="balanced")
    assert "never invent search results, video titles" in prompt


@pytest.mark.parametrize("text, url", [
    ("youtube ekata yanna", "https://www.youtube.com"),
    ("යූටියුබ් එකට යන්න", "https://www.youtube.com"),
    ("bing eken black holes gana hoyanna", "https://www.bing.com/search?q=black+holes"),
])
def test_singlish_case_words_are_not_searched_for(text, url):
    # command_check, 25 Oct: these searched for "ekata yanna" and "eken black holes gana
    # hoyanna". Now "ekata yanna" (go to) opens the site and "gana" (about) is dropped.
    tools, opened, _, _ = make()
    tools.handle(text)
    assert opened == [url]


# ---- command_check, 25 Oct: word families for English, Singlish and Sinhala ----
@pytest.mark.parametrize("text, site", [
    ("pull up YouTube", "youtube"), ("take me to YouTube", "youtube"), ("could you get YouTube going for me", "youtube"),
    ("I wanna use Bing", "bing"), ("bring up Bing please", "bing"), ("open up Bing for a sec", "bing"),
    ("youtube eka on karanna", "youtube"), ("youtube eka arinnako machan", "youtube"), ("bing eka denna", "bing"),
    ("bing ekata yamu", "bing"), ("බිං එක දාන්න", "bing"), ("යූටියුබ් එක අරින්නකෝ", "youtube"),
])
def test_ways_to_open_a_site(text, site):
    tools, _, _, _ = make()
    assert tools.handle(text).tool == f"{site}_open"


@pytest.mark.parametrize("text, query", [
    ("put on some lofi beats", "lofi beats"),
    ("I feel like listening to some Sinhala songs", "Sinhala songs"),
    ("can you find a video explaining Fourier series", "Fourier series"),
    ("find me Naruto openings", "Naruto openings"),
    ("anything on YouTube about black holes?", "black holes"),
    ("luffy edit eka youtube eken danna", "luffy edit"),
    ("fourier series gana video ekak hoyala denna", "fourier series"),
    ("sinhala sindu tikak danna", "sinhala sindu"),
    ("lofi tikak play karanna", "lofi"),
    ("සින්දු ටිකක් දාන්න", "සින්දු"),
    ("කළු කුහර ගැන වීඩියෝ එකක් පෙන්නන්න", "කළු කුහර"),
])
def test_ways_to_ask_for_a_video(text, query):
    tools, opened, _, _ = make()
    assert tools.handle(text).tool == "youtube_search" and opened[-1] == youtube_results_url(query)


@pytest.mark.parametrize("text, query", [
    ("google the RC time constant", "the RC time constant"),
    ("search the web for cheap flights to Colombo", "cheap flights to Colombo"),
    ("web eke train timetable hoyanna", "train timetable"),
    ("colombo weather eka internet eke balanna", "colombo weather"),
    ("අන්තර්ජාලයේ කළු කුහර ගැන හොයන්න", "කළු කුහර"),
])
def test_ways_to_search_the_web(text, query):
    tools, opened, _, _ = make()
    assert tools.handle(text).tool == "bing_search" and opened[-1] == bing_url(query)


@pytest.mark.parametrize("answer, number", [
    ("the last one you said", 3), ("go with the middle one", 2), ("anthima eka danna", 3),
    ("අන්තිම එක දාන්න", 3), ("deweniya", 2), ("the pirate one", 3), ("the hip hop one from 2021", 1),
])
def test_ways_to_choose(answer, number):
    luffy = [("v1", "Best of lofi hip hop 2021 [beats to relax/study to]"), ("v2", "1 A.M Study Session [lofi hip hop]"),
             ("v3", "Future king of pirates || Luffy Edit - One Piece || #onepiece")]
    tools, opened, _, _ = make(videos=luffy)
    tools.handle("search YouTube for lofi")
    assert tools.handle(answer).tool == "youtube_play" and opened[-1] == youtube_watch_url(luffy[number - 1][0])


@pytest.mark.parametrize("text", ["hold on, stop that for a sec", "freeze the video", "wait wait, stop it",
                                  "nawaththanna", "video eka podi welawakata nawaththanna", "ඒක නවත්තන්න"])
def test_ways_to_pause_while_jarvis_video_plays(text):
    tools, _, keys, _ = make()
    tools.handle("search YouTube for lofi")
    tools.handle("first")
    assert tools.handle(text).tool == "media_pause" and keys == ["play/pause"]


@pytest.mark.parametrize("text", ["okay, carry on", "keep playing", "aye danna", "aye play karanna", "ආයේ දාන්න",
                                  "දිගටම දාන්න"])
def test_ways_to_carry_on_after_pausing(text):
    tools, _, keys, _ = make()
    tools.handle("search YouTube for lofi")
    tools.handle("first")
    tools.handle("pause the video")                       # "Paused. Anything else?"
    assert tools.handle(text).tool == "media_resume" and keys == ["play/pause"] * 2


@pytest.mark.parametrize("text", ["stop it", "hold on", "carry on", "take me back", "nawaththanna"])
def test_short_phrases_do_nothing_without_jarvis_video(text):
    tools, opened, keys, _ = make()
    assert tools.handle(text) is None and opened == [] and keys == []


@pytest.mark.parametrize("text", ["can you stop talking so fast", "I paused my studies last year",
                                  "I want to see my notes", "my friend opened a shop near campus"])
def test_these_are_not_commands(text):
    tools, _, keys, _ = make()
    tools.handle("search YouTube for lofi")
    tools.handle("first")                                 # even with a video playing
    assert tools.handle(text) is None and keys == []


@pytest.mark.parametrize("text", ["shh, quiet for a moment", "quiet please", "shhh"])
def test_shh_pauses_jarvis_video(text):
    # The real model (25 Oct) took "shh, quiet for a moment" as "Jarvis, be quiet"
    # while a video played. With Jarvis's video playing, it pauses the video.
    tools, _, keys, _ = make()
    tools.handle("search YouTube for lofi")
    tools.handle("first")
    assert tools.handle(text).tool == "media_pause" and keys == ["play/pause"]
    assert make()[0].handle(text) is None              # with nothing playing: not a command
