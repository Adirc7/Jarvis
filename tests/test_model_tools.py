"""The model understands YouTube/Bing requests the fixed rules miss, and acts
through the same tools (agent/llm.py ToolCall, tools/web.py call, app.py)."""

import json
from types import SimpleNamespace as NS

import pytest

from jarvis.agent.llm import FallbackLLM, Provider, ToolCall
from jarvis.app import App
from jarvis.telemetry import Telemetry
from jarvis.tools.web import (
    TOOL_SPECS,
    WebTools,
    youtube_results_url,
    youtube_watch_url,
)

LUFFY = [("v1", "Best of lofi hip hop 2021 [beats to relax/study to]"),
         ("v2", "1 A.M Study Session [lofi hip hop]"),
         ("v3", "Future king of pirates || Luffy Edit - One Piece || #onepiece")]


def chunk(content=None, tool=None):
    return NS(choices=[NS(delta=NS(content=content, tool_calls=[tool] if tool else None))])


class ToolStream:
    def __init__(self, chunks):
        self.chunks = chunks

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for c in self.chunks:
            yield c


class ModelClient:
    """Streams either words or a tool call (in two pieces, as providers do); remembers what it got."""

    def __init__(self, words=None, tool=None, arguments="{}"):
        self.words, self.tool, self.arguments = words, tool, arguments
        self.kwargs, self.messages = None, None
        self.chat = NS(completions=NS(create=self.create))

    async def create(self, model, messages, stream=False, **kwargs):
        self.kwargs, self.messages = kwargs, messages
        if self.tool:
            half = len(self.arguments) // 2
            return ToolStream([
                chunk(tool=NS(index=0, function=NS(name=self.tool, arguments=self.arguments[:half]))),
                chunk(tool=NS(index=0, function=NS(name=None, arguments=self.arguments[half:]))),
            ])
        return ToolStream([chunk(content=w) for w in self.words])


def make(client, videos=LUFFY):
    opened, keys = [], []
    web = WebTools(opener=opened.append, media_key=lambda: keys.append("play/pause"),
                   search_videos=lambda q: list(videos))
    app = App(_settings(), Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", client)]),
              out=lambda *a, **k: None, web=web)
    return app, web, opened, keys


_SETTINGS = {}


def _settings():
    return _SETTINGS["s"]


@pytest.fixture(autouse=True)
def _keep_settings(settings):
    _SETTINGS["s"] = settings


# ---- the stream ------------------------------------------------------------------
async def test_the_stream_gives_back_a_tool_call():
    client = ModelClient(tool="play_video", arguments='{"number": 3}')
    llm = FallbackLLM([Provider("f", "m", client)])
    items = [x async for x in llm.stream_text([{"role": "user", "content": "x"}], tools=TOOL_SPECS)]
    assert items == [ToolCall("play_video", '{"number": 3}')]
    assert client.kwargs["tools"] == TOOL_SPECS


# ---- the app ------------------------------------------------------------------------
async def test_the_model_picks_the_video_the_rules_could_not():
    client = ModelClient(tool="play_video", arguments='{"number": 3}')
    app, _, opened, _ = make(client)
    await app.handle_text("search YouTube for lofi")                    # the rules list three videos
    reply = await app.handle_text("I'd rather hear the anime one")      # no title word, no "first"
    assert reply.startswith("Playing Future king of pirates") and opened[-1] == youtube_watch_url("v3")
    system = client.messages[0]["content"]
    assert "Luffy Edit" in system and "data only" in system           # it saw the list, as data
    assert app.history[-1]["content"] == reply


async def test_any_wording_for_a_search():
    client = ModelClient(tool="search_youtube", arguments=json.dumps({"query": "Baka song Luffy edit"}))
    app, _, opened, _ = make(client)
    reply = await app.handle_text("yo put on that baka song with the luffy edit")
    assert opened[-1] == youtube_results_url("Baka song Luffy edit") and reply.startswith("I found 1,")


async def test_a_question_about_youtube_gets_words_not_an_action():
    client = ModelClient(words=["Both ", "are search engines."])
    app, _, opened, keys = make(client)
    assert await app.handle_text("is YouTube better than Bing for lectures") == "Both are search engines."
    assert client.kwargs.get("tools") == TOOL_SPECS and opened == [] and keys == []


async def test_every_request_gets_the_tools_by_default():
    # "got that Luffy clip from yesterday?" has no word like video/play/search: a
    # list of trigger words would miss it, so the model always sees the tools.
    client = ModelClient(tool="search_youtube", arguments='{"query": "Luffy clip"}')
    app, _, opened, _ = make(client)
    await app.handle_text("got that Luffy clip from yesterday?")
    assert client.kwargs["tools"] == TOOL_SPECS and opened[-1] == youtube_results_url("Luffy clip")


async def test_likely_mode_keeps_ordinary_chat_without_tools(settings):
    settings.raw["tools"]["model_tools"] = "likely"
    client = ModelClient(words=["Entropy measures disorder."])
    app, _, _, _ = make(client)
    await app.handle_text("what is entropy")
    assert "tools" not in client.kwargs
    assert "Tools this turn" not in client.messages[0]["content"]


async def test_off_means_no_tools(settings):
    settings.raw["tools"]["model_tools"] = "off"
    client = ModelClient(words=["Sure."])
    app, web, _, _ = make(client)
    await app.handle_text("got that Luffy clip from yesterday?")
    assert "tools" not in client.kwargs and web.ask_model is False


async def test_a_tool_jarvis_does_not_have_does_nothing():
    client = ModelClient(tool="delete_files", arguments='{"path": "C:/"}')
    app, _, opened, keys = make(client)
    reply = await app.handle_text("open my files and clean them up")
    assert reply == "Sorry, sir, I couldn't do that one." and opened == [] and keys == []


async def test_bad_arguments_do_nothing():
    client = ModelClient(tool="search_youtube", arguments="not json")
    app, _, opened, _ = make(client)
    assert await app.handle_text("find me something to watch") == "Sorry, sir, I couldn't do that one."
    assert opened == []


# ---- WebTools.call and what the model is told ------------------------------------
def test_call_checks_its_arguments():
    web = WebTools(opener=lambda url: None, media_key=lambda: None, search_videos=lambda q: list(LUFFY))
    assert web.call("open_site", '{"site": "facebook"}') is None          # only YouTube and Bing
    assert web.call("play_video", '{"number": 2}').tool == "youtube_need_topic"   # nothing listed yet
    web.call("search_youtube", '{"query": "  lofi   hip hop "}')
    assert web.pages[-1] == youtube_results_url("lofi hip hop")
    assert web.call("play_video", '{"number": 7}').tool == "youtube_which"
    assert web.call("play_video", '{"number": "2"}').text == "Playing 1 A.M Study Session [lofi hip hop]."
    assert web.call("search_bing", json.dumps({"query": "x" * 500})).tool == "bing_search"
    assert len(web.pages[-1]) < 300                                      # long queries are cut


def test_the_screen_as_the_model_sees_it():
    web = WebTools(opener=lambda url: None, media_key=lambda: None, search_videos=lambda q: list(LUFFY))
    assert web.state_note() == "No page of Jarvis's is open in the browser."
    web.call("search_youtube", '{"query": "lofi"}')
    note = web.state_note()
    assert 'YouTube results for "lofi"' in note and "3. Future king of pirates" in note
    assert "which of the listed videos to play" in note
    web.call("play_video", '{"number": 1}')
    assert "a YouTube video (Best of lofi hip hop 2021" in web.state_note() and "playing" in web.state_note()


async def test_the_rules_still_answer_what_they_can():
    client = ModelClient(tool="play_video", arguments='{"number": 1}')
    app, _, opened, _ = make(client)
    await app.handle_text("search YouTube for lofi")
    await app.handle_text("the pirate king edit")                        # title words: the rules pick it
    assert opened[-1] == youtube_watch_url("v3") and client.messages is None   # the model was never asked


def test_a_stray_one_is_not_the_first_when_other_words_say_more():
    web = WebTools(opener=lambda url: None, media_key=lambda: None, search_videos=lambda q: list(LUFFY))
    web.handle("search YouTube for lofi")
    assert web.handle("the anime one").tool == "youtube_which"          # without the model: ask
    web2 = WebTools(opener=lambda url: None, media_key=lambda: None, search_videos=lambda q: list(LUFFY))
    web2.handle("search YouTube for lofi")
    assert web2.handle("one").tool == "youtube_play" and web2.now_playing == LUFFY[0][1]


async def test_after_paused_anything_else_carry_on_resumes():
    client = ModelClient(tool="resume_media")
    app, web, _, keys = make(client)
    await app.handle_text("search YouTube for lofi")
    await app.handle_text("the first one")
    await app.handle_text("pause the video")                  # "Paused. Anything else, sir?"
    assert await app.handle_text("okay, carry on") == "Playing again."
    assert keys == ["play/pause", "play/pause"] and web.pages[-1].endswith("watch?v=v1")


async def test_the_model_is_told_the_singlish_and_sinhala_command_words():
    client = ModelClient(words=["Sure."])
    app, _, _, _ = make(client)
    await app.handle_text("anime eka danna")
    system = client.messages[0]["content"]
    assert "anthima/අන්තිම last" in system and "danna/දාන්න put on, play" in system
