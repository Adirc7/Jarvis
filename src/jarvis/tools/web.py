"""Voice tools for the web: Bing search and YouTube (open, search, choose, pause, go back).

The first tools Jarvis has. They are low-risk (they only open pages on two
sites and press the media play/pause key), so they run without asking, but
they are still narrow on purpose:

- fixed rules decide them, before the LLM (like language switching): the
  model never chooses to open anything;
- only addresses Jarvis builds itself, on bing.com and youtube.com, with the
  search words encoded (so Sinhala works);
- one short follow-up question at a time ("What should I search for?"),
  answered by the next thing you say, for 60 seconds or until "cancel".

YouTube titles come from the official YouTube Data API (a free key in .env as
YOUTUBE_API_KEY, about 100 searches a day). Without a key, Jarvis opens the
results page instead and can't read titles aloud.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field

BING = "https://www.bing.com"
YOUTUBE = "https://www.youtube.com"
ALLOWED_HOSTS = {"www.bing.com", "www.youtube.com"}
WAIT_S = 60.0

# What Jarvis says, per language. {address} becomes "sir" (persona.toml).
PHRASES = {
    "en": {
        "bing_ask": "Bing is open, {address}. What should I search for?",
        "bing_results": "Here are the results for {q}, {address}.",
        "yt_ask": "Which video would you like to watch, {address}?",
        "yt_found": "I found {list}. Which one should I play?",
        "yt_playing": "Playing {title}.",
        "yt_page": "Here are the YouTube results for {q}, {address}.",
        "yt_none": "I couldn't find any videos for {q}.",
        "paused": "Paused. Would you like to search for anything else, {address}?",
        "paused_only": "Paused.",
        "resumed": "Playing again.",
        "not_playing": "Nothing is playing right now.",
        "back": "Going back.",
        "no_back": "There's no page to go back to.",
        "which": "Sorry, which one? Say first, second or third, or a word from the title.",
        "ask_query": "What should I search for?",
        "yt_need_topic": "Which video, {address}? Tell me a topic or a title and I'll find it.",
        "couldnt": "Sorry, {address}, I couldn't do that one.",
        "ok": "Alright.",
    },
    "si": {
        "bing_ask": "බිං එක ඕපන් කළා. මොනවද හොයන්න ඕනේ?",
        "bing_results": "{q} ගැන ප්‍රතිඵල මෙන්න.",
        "yt_ask": "මොන වීඩියෝ එකද බලන්න ඕනේ?",
        "yt_found": "මට හම්බුණා: {list}. මොකක්ද දාන්න ඕනේ?",
        "yt_playing": "{title} දැම්මා.",
        "yt_page": "යූටියුබ් එකේ {q} ප්‍රතිඵල මෙන්න.",
        "yt_none": "{q} ගැන වීඩියෝ හම්බුණේ නෑ.",
        "paused": "නැවැත්තුවා. තව මොනවා හරි හොයන්න ඕනෙද?",
        "paused_only": "නැවැත්තුවා.",
        "resumed": "ආයේ දැම්මා.",
        "not_playing": "දැන් මුකුත් ප්ලේ වෙන්නේ නෑ.",
        "back": "ආපහු ගියා.",
        "no_back": "ආපහු යන්න පිටුවක් නෑ.",
        "which": "සමාවෙන්න, මොකක්ද? පළවෙනි, දෙවෙනි, තුන්වෙනි, නැත්නම් නමේ වචනයක් කියන්න.",
        "ask_query": "මොනවද හොයන්න ඕනේ?",
        "yt_need_topic": "මොන වීඩියෝ එකද? මාතෘකාවක් හරි නමක් හරි කියන්න, මම හොයලා දෙන්නම්.",
        "couldnt": "සමාවෙන්න, ඒක කරන්න බැරි වුණා.",
        "ok": "හරි.",
    },
}

# ---- recognising the requests (on _clean()ed text, any case) --------------------

# Wake words and polite openers ("Jarvis, can you please ..."), and polite
# endings ("... for me, please"): Whisper writes what people really say.
_LEAD = (r"(?:(?:jarvis|friday|hey|hi|please|ok|okay|so|now|ane|hari|podda|machan|bro|ජාවිස්|ෆ්\u200d?රයිඩේ"
         r"|අනේ|හරි|පොඩ්ඩක්|can\s+you|could\s+you|would\s+you|will\s+you|can\s+u|could\s+u"
         r"|i\s+want\s+you\s+to|i\s+need\s+you\s+to|i\s+mean|i\s+said|just|actually|um|uh|and|then|no"
         r"|sorry|wait)\s+)*")
_TAIL = r"(?:\s+(?:please|for\s+me|now|right\s+now|sir|jarvis|friday|thanks|thank\s+you))*"
_BING = r"(?:microsoft\s+)?bing|බිං|බින්ග්"
_YT = r"youtube|you\s+tube|යූටියුබ්"
_OPEN_EN = r"open|launch|start|go\s+to|show\s+me"
_OPEN_SL = r"(?:open|arinna|arin)(?:\s+(?:karanna|karannako|karala\s+denna|karanna\s+puluwanda))?"
_OPEN_SI = r"(?:ඕපන්|විවෘත)\s+(?:කරන්න|කරන්නකෝ|කරලා\s+දෙන්න|කරන්න\s+පුළුවන්ද)|අරින්න|අරින්නකෝ|අරලා\s+දෙන්න"
_SEARCH_SL = r"hoyanna|hoyala\s+denna|search\s+karanna|search\s+karala\s+denna"
_SEARCH_SI = r"හොයන්න|හොයන්නකෝ|හොයලා\s+දෙන්න|සර්ච්\s+කරන්න|සර්ච්\s+කරලා\s+දෙන්න"
_PLAY_SL = r"danna|dannako|play\s+karanna|play\s+karala\s+denna|" + _SEARCH_SL
_PLAY_SI = r"දාන්න|දාන්නකෝ|දාලා\s+දෙන්න|ප්ලේ\s+කරන්න|ප්ලේ\s+කරලා\s+දෙන්න|" + _SEARCH_SI


# "bing eka ..." / "youtube එක ..." is Singlish/Sinhala for "the Bing", not a search for "eka".
_NOT_QUERY = (r"(?:eka|eke|ekata|eken|ekenma|ekath|එක|එකේ|එකට|එකෙන්|එකත්|is|was|open|opened|app|website)"
              r"(?:\s|$)")


def _rx(*patterns: str) -> list[re.Pattern[str]]:
    return [re.compile(rf"^{_LEAD}{p}{_TAIL}$", re.IGNORECASE) for p in patterns]


_SITE = r"(?:\s+(?:app|website|site|page|home\s+page))?"
OPEN_BING = _rx(rf"(?:{_OPEN_EN})\s+(?:up\s+)?(?:the\s+)?(?:{_BING}){_SITE}", rf"(?:{_BING})", rf"(?:{_BING})\s+eka\s+(?:{_OPEN_SL})",
                rf"(?:{_BING})\s+එක\s+(?:{_OPEN_SI})",
                rf"(?:i\s+want\s+to|i\s+would\s+like\s+to|i'd\s+like\s+to|let's|lets)\s+"
                rf"(?:use\s+|open\s+|go\s+to\s+|search\s+(?:on\s+|with\s+)?)(?:{_BING})")
SEARCH_BING = _rx(rf"(?:search|look\s+up|find)(?:\s+me)?\s+(?:on\s+)?(?:{_BING})\s+(?:for\s+)?(?P<q>.+)",
                  rf"(?:search|look\s+up|find)\s+(?:for\s+)?(?P<q>.+?)\s+(?:on|in|with)\s+(?:{_BING})",
                  rf"(?:{_BING})\s+eke\s+(?P<q>.+?)\s+(?:{_SEARCH_SL})",
                  rf"(?P<q>.+?)\s+(?:{_BING})\s+eke\s+(?:{_SEARCH_SL})",
                  rf"(?:{_BING})\s+එකේ\s+(?P<q>.+?)\s+(?:{_SEARCH_SI})",
                  rf"(?P<q>.+?)\s+(?:{_BING})\s+එකේ\s+(?:{_SEARCH_SI})",
                  rf"(?:{_BING})\s+(?!{_NOT_QUERY})(?:search\s+)?(?:for\s+)?(?P<q>.+)")
OPEN_YT = _rx(rf"(?:{_OPEN_EN})\s+(?:up\s+)?(?:the\s+)?(?:{_YT}){_SITE}", rf"(?:{_YT})", rf"(?:{_YT})\s+eka\s+(?:{_OPEN_SL})",
              rf"(?:{_YT})\s+එක\s+(?:{_OPEN_SI})",
              rf"(?:i\s+want\s+to|i\s+would\s+like\s+to|i'd\s+like\s+to|let's|lets)\s+"
              rf"(?:watch\s+(?:something\s+on\s+)?|use\s+|open\s+|go\s+to\s+|go\s+on\s+)(?:{_YT})",
              rf"(?:{_YT})\s+(?:eka\s+)?(?:balanna|බලන්න)\s+(?:one|ඕනේ)")
SEARCH_YT = _rx(rf"(?:search|look\s+up|find)(?:\s+me)?\s+(?:on\s+)?(?:{_YT})\s+(?:for\s+)?(?P<q>.+)",
                rf"(?:search|look\s+up|find|play|watch|show)(?:\s+me)?\s+(?:for\s+)?(?P<q>.+?)\s+(?:on|in|from)\s+"
                rf"(?:{_YT})",
                rf"(?:{_YT})\s+eke\s+(?P<q>.+?)\s+(?:{_PLAY_SL})",
                rf"(?P<q>.+?)\s+(?:{_YT})\s+eke\s+(?:{_PLAY_SL})",
                rf"(?:{_YT})\s+එකේ\s+(?P<q>.+?)\s+(?:{_PLAY_SI})",
                rf"(?P<q>.+?)\s+(?:{_YT})\s+එකේ\s+(?:{_PLAY_SI})",
                rf"(?:{_YT})\s+(?!{_NOT_QUERY})(?:search\s+)?(?:for\s+)?(?P<q>.+)")
PAUSE = _rx(r"(?:stop|pause)\s+(?:the\s+)?(?:video|youtube|music|song)", r"pause(?:\s+it)?",
            r"(?:video|youtube)\s+eka\s+(?:nawaththanna|nawaththannako|pause\s+karanna|stop\s+karanna)",
            r"(?:වීඩියෝ|යූටියුබ්)\s+එක\s+(?:නවත්තන්න|නවත්තන්නකෝ|පෝස්\s+කරන්න|ස්ටොප්\s+කරන්න)")
# "play X" with no site named: only while a YouTube page Jarvis opened is in front.
PLAY_HERE = _rx(r"(?:play|put\s+on|find)\s+(?:me\s+)?(?!(?:the\s+)?(?:video|music|song|it|first|second|third)\b)"
                r"(?:the\s+)?(?P<q>.+)")
RESUME = _rx(r"(?:resume|continue|unpause)(?:\s+(?:the\s+)?(?:video|it|music|song))?",
             r"play\s+(?:the\s+video|it)\s+again", r"play\s+(?:the\s+)?(?:video|music|song)",
             r"(?:video|youtube)\s+eka\s+(?:aye|ayeth)\s+(?:danna|play\s+karanna)",
             r"(?:වීඩියෝ|යූටියුබ්)\s+එක\s+ආයේ\s+(?:දාන්න|ප්ලේ\s+කරන්න)")
BACK = _rx(r"(?:go\s+)?back", r"go\s+to\s+the\s+previous\s+page", r"previous\s+page",
           r"(?:aapahu|apahu)\s+(?:yanna|yannako)", r"(?:ආපහු|ආපසු)\s+(?:යන්න|යන්නකෝ)")

_COMMANDS = (OPEN_YT, OPEN_BING, SEARCH_YT, SEARCH_BING, PAUSE, RESUME, BACK)
_CANCEL = {"cancel", "no", "nothing", "never mind", "no thanks", "stop", "epa", "nathi", "na",
           "එපා", "නෑ", "කමක් නෑ", "අවලංගු කරන්න"}
_YES = {"yes", "yeah", "yep", "ok", "okay", "sure", "ow", "ou", "ඔව්", "හරි"}
_ORDINALS = [
    {"first", "1", "one", "1st", "palaweni", "පළවෙනි", "පළමු"},
    {"second", "2", "two", "2nd", "deweni", "දෙවෙනි", "දෙවැනි"},
    {"third", "3", "three", "3rd", "thunweni", "තුන්වෙනි", "තුන්වැනි"},
]


# Two requests in one breath: "Open YouTube. Then play lofi music." / "open
# YouTube and play lofi music". Split only where a sentence ends or at "and" /
# "then", and only if the first part is a command on its own.
_SPLIT = re.compile(r"\s*[.!?]+\s+|\s*,?\s+(?:and\s+then|then|and)\s+", re.IGNORECASE)
# Words to drop from the front of an answer: "then play lofi music" -> "lofi music".
_QUERY_LEAD = re.compile(r"^(?:(?:and|then|so|now|ok|okay|please|jarvis|friday)\s+)*"
                         r"(?:(?:play|search\s+for|search|find|look\s+up|watch|show\s+me)\s+)?", re.IGNORECASE)
_FILLER = {"then", "and", "play", "the", "a", "video", "videos", "one", "please", "jarvis", "friday", "now",
           "watch", "on", "youtube", "danna", "eka", "දාන්න", "එක"}


# Words that say nothing about which video: ignored when matching a title.
_NOT_TITLE = {"the", "a", "an", "one", "that", "this", "you", "your", "mentioned", "said", "play", "can",
              "could", "please", "video", "song", "music", "jarvis", "friday", "and", "of", "it", "me", "i",
              "want", "watch", "with", "on", "youtube", "danna", "eka", "දාන්න", "එක"}
# The answer sounds like a choice even if it didn't name one ("play festival").
_CHOICE_HINT = re.compile(r"^(?:play|that|the|this|number)\b|\bone\b|\bmentioned\b|දාන්න|එක", re.IGNORECASE)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[^\W_]+", text.lower()) if len(w) > 1} - _NOT_TITLE


def _title_choice(answer: str, videos: list[tuple[str, str]], minimum: int = 1) -> int | None:
    """"the Luffy edit" -> the video whose title shares the most words, if exactly one does."""
    said = _words(answer)
    if not said:
        return None
    scores = [len(said & _words(title)) for _, title in videos]
    best = max(scores, default=0)
    return scores.index(best) if best >= minimum and scores.count(best) == 1 else None


def _only_ordinal(low: str) -> bool:
    """"play the first video" with nothing to choose from yet."""
    rest = set(low.split()) - _FILLER
    return bool(rest) and rest <= set().union(*_ORDINALS)


def _clean(text: str) -> str:
    """Drop sentence punctuation only: the search words keep their capitals and
    symbols ("C++", "RC"), and Sinhala keeps its joiners (ප්‍ර)."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[.,!?;:\"“”‘’()\[\]]+|(?<!\w)'|'(?!\w)", " ", text)
    return " ".join(text.split())


def _match(patterns: list[re.Pattern[str]], text: str) -> re.Match[str] | None:
    return next((m for p in patterns if (m := p.match(text))), None)


def bing_url(query: str | None = None) -> str:
    return f"{BING}/search?q={urllib.parse.quote_plus(query)}" if query else BING


def youtube_results_url(query: str) -> str:
    return f"{YOUTUBE}/results?search_query={urllib.parse.quote_plus(query)}"


def youtube_watch_url(video_id: str) -> str:
    return f"{YOUTUBE}/watch?v={urllib.parse.quote(video_id)}"


def open_in_browser(url: str, browser: str = "edge") -> None:
    """Open an allowed address: in Edge on Windows (the microsoft-edge: link), else the default browser."""
    if urllib.parse.urlsplit(url).hostname not in ALLOWED_HOSTS:
        raise ValueError(f"not an allowed site: {url}")
    if browser == "edge" and sys.platform == "win32":
        os.startfile(f"microsoft-edge:{url}")      # a fixed scheme and an allowed site
        return
    import webbrowser
    webbrowser.open(url)


def press_media_play_pause() -> None:
    """The keyboard's play/pause key: Edge and Chrome pause YouTube with it even in the background."""
    from pynput.keyboard import Controller, Key
    keys = Controller()
    keys.press(Key.media_play_pause)
    keys.release(Key.media_play_pause)


def youtube_api_search(query: str, key: str, n: int = 3, timeout_s: float = 6.0) -> list[tuple[str, str]]:
    """(video id, title) of the top videos, from the YouTube Data API v3."""
    params = urllib.parse.urlencode({"part": "snippet", "type": "video", "maxResults": n, "q": query, "key": key})
    with urllib.request.urlopen(f"https://www.googleapis.com/youtube/v3/search?{params}",
                                timeout=timeout_s) as resp:
        data = json.load(resp)
    return [(item["id"]["videoId"], html.unescape(item["snippet"]["title"]))
            for item in data.get("items", []) if item.get("id", {}).get("videoId")]


@dataclass
class Pending:
    kind: str                     # bing_query | youtube_query | youtube_choice | anything_else
    until: float
    videos: list[tuple[str, str]] = field(default_factory=list)
    asked_again: bool = False     # "Sorry, which one?" is asked once, then Jarvis lets it go


# The same actions as tools for the language model (OpenAI-style function
# definitions). The model chooses one when it understands a request the fixed
# rules missed; WebTools.call checks the arguments and does it.
TOOL_SPECS: list[dict] = [
    {"type": "function", "function": {
        "name": "open_site", "description": "Open YouTube or Bing in the browser, with nothing searched yet.",
        "parameters": {"type": "object", "properties": {"site": {"type": "string", "enum": ["youtube", "bing"]}},
                       "required": ["site"]}}},
    {"type": "function", "function": {
        "name": "search_youtube",
        "description": "Find videos or music on YouTube and read out the top three, when the user wants to watch "
                       "or listen to something. The query is the topic or title only, in the user's words.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "search_bing", "description": "Search the web with Bing and show the results page.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "play_video",
        "description": "Play one of the videos Jarvis read out, by its number in that list (1 to 3). Use the "
                       "titles to work out which one the user means (\"the Luffy one\", \"the last one\").",
        "parameters": {"type": "object", "properties": {"number": {"type": "integer", "minimum": 1, "maximum": 3}},
                       "required": ["number"]}}},
    {"type": "function", "function": {
        "name": "pause_media", "description": "Pause the video or music that is playing.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "resume_media", "description": "Play the paused video or music again.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "go_back", "description": "Go back to the previous page Jarvis opened.",
        "parameters": {"type": "object", "properties": {}}}},
]


@dataclass
class ToolReply:
    text: str                     # what Jarvis says
    tool: str                     # for the logs: bing_open, youtube_search, media_pause, ...


@dataclass
class WebTools:
    opener: Callable[[str], None] = open_in_browser
    media_key: Callable[[], None] = press_media_play_pause
    search_videos: Callable[[str], list[tuple[str, str]]] | None = None
    clock: Callable[[], float] = time.monotonic
    pending: Pending | None = None
    pages: list[str] = field(default_factory=list)      # what Jarvis opened, for "go back"
    playing: bool = False
    listed: list[tuple[str, str]] = field(default_factory=list)   # the videos Jarvis last read out
    # True when the language model can take over (app.py): a choice the rules
    # can't place ("the anime one") goes to the model, which sees the list.
    ask_model: bool = False
    now_playing: str | None = None                                  # the title Jarvis put on

    @classmethod
    def from_env(cls, browser: str = "edge") -> WebTools:
        key = os.environ.get("YOUTUBE_API_KEY", "").strip()
        return cls(opener=lambda url: open_in_browser(url, browser),
                   search_videos=(lambda q: youtube_api_search(q, key)) if key else None)

    # ---- the one entry point ------------------------------------------------
    def handle(self, text: str, lang: str = "en", address: str = "sir") -> ToolReply | None:
        """A reply if `text` is one of these requests (or answers Jarvis's question), else None.

        "Open YouTube. Then play lofi music." is two requests: each part is
        handled in turn, and Jarvis says the last reply.
        """
        words = _clean(text)
        if words and not any(_match(group, words) for group in _COMMANDS):
            parts = [part for part in _SPLIT.split(text) if _clean(part)]
            if len(parts) > 1 and any(_match(group, _clean(parts[0])) for group in _COMMANDS):
                replies = [r for part in parts if (r := self._handle_one(part, lang, address))]
                return replies[-1] if replies else None
        return self._handle_one(text, lang, address)

    @staticmethod
    def _replier(lang: str, address: str):
        say = PHRASES.get(lang, PHRASES["en"])

        def reply(key: str, tool: str, **kw: str) -> ToolReply:
            template = say[key] if address else say[key].replace(", {address}", "")
            return ToolReply(template.format(address=address, **kw), tool)
        return reply

    def _handle_one(self, text: str, lang: str, address: str) -> ToolReply | None:
        words = _clean(text)
        if not words:
            return None
        reply = self._replier(lang, address)

        if self.pending is not None and self.clock() > self.pending.until:
            self.pending = None                         # the question has expired
        if self.pending is not None:
            answer = self._answer(words, text, reply)
            if answer is not None:
                return answer

        if _match(OPEN_YT, words):
            self._open(YOUTUBE)
            self.pending = Pending("youtube_query", self.clock() + WAIT_S)
            return reply("yt_ask", "youtube_open")
        if _match(OPEN_BING, words):
            self._open(BING)
            self.pending = Pending("bing_query", self.clock() + WAIT_S)
            return reply("bing_ask", "bing_open")
        if m := _match(SEARCH_YT, words):
            return self._youtube_search(m.group("q"), reply)
        if m := _match(SEARCH_BING, words):
            return self._bing(m.group("q"), reply)
        if self.pages and self.pages[-1].startswith(YOUTUBE) and (m := _match(PLAY_HERE, words)):
            return self._youtube_search(m.group("q"), reply)    # YouTube is open: "play X" means there
        if _match(PAUSE, words):
            return self._pause(reply)
        if _match(RESUME, words):
            # With no page of Jarvis's open, only "play/resume the video" (not a
            # bare "continue", which may mean "go on with your explanation").
            if not self.pages and not re.search(r"video|music|song|youtube|වීඩියෝ|යූටියුබ්", words, re.IGNORECASE):
                return None
            self.media_key()
            self.playing = True
            return reply("resumed", "media_resume")
        if _match(BACK, words):
            return self._back(reply)
        return None

    # ---- pieces -------------------------------------------------------------------
    def _answer(self, words: str, text: str, reply) -> ToolReply | None:
        pending, self.pending = self.pending, None
        low = words.lower().replace("\u200d", "")
        if low in _CANCEL:
            return reply("ok", "cancel")
        if any(_match(group, words) for group in _COMMANDS):
            return None                                  # a new command, not an answer
        if pending.kind == "youtube_choice" and _match(RESUME, words):
            return None
        if pending.kind == "anything_else":
            if low in _YES:
                self.pending = Pending("youtube_query", self.clock() + WAIT_S)
                return reply("ask_query", "ask_query")
            if self.ask_model:
                # "okay, carry on" or a topic? The model decides, knowing what Jarvis asked.
                self.pending = pending
                return None
            return self._youtube_search(words, reply)
        if pending.kind == "youtube_choice":
            # Two or more title words first ("Luffy edit One Piece"), then
            # first/second/third, then one title word, then a bare "one".
            n = _title_choice(words, pending.videos, minimum=2)
            if n is None:
                n = self._ordinal(low, bare_one=False)
            if n is None:
                n = _title_choice(words, pending.videos)
            if n is None and not _words(words):
                n = self._ordinal(low)                 # just "one" / "play one": the first
            if n is None and self.ask_model:
                self.pending = pending                 # the model decides, seeing the list
                return None
            if n is None:
                if _CHOICE_HINT.search(low) and not pending.asked_again:
                    # Sounds like a choice but isn't one Jarvis knows (Whisper heard
                    # "play festival"): ask once, keeping the list, as a person would.
                    pending.asked_again = True
                    pending.until = self.clock() + WAIT_S
                    self.pending = pending
                    return reply("which", "youtube_which")
                return None                              # something else: the user has moved on
            if n >= len(pending.videos):
                self.pending = pending
                return reply("which", "youtube_which")
            return self._play(pending.videos, n, reply)
        if pending.kind == "youtube_query" and _only_ordinal(low):
            self.pending = Pending("youtube_query", self.clock() + WAIT_S)   # nothing to choose from yet
            return reply("yt_need_topic", "youtube_need_topic")
        query = _QUERY_LEAD.sub("", words).strip() or words
        if pending.kind == "bing_query":
            return self._bing(query, reply)
        return self._youtube_search(query, reply)

    @staticmethod
    def _ordinal(words: str, bare_one: bool = True) -> int | None:
        """first / second / third (and 1, 2, 3, palaweni, ...). A bare "one" counts
        as the first only when `bare_one` (it may be part of a title: "One Piece")."""
        if words in _YES or words in {"play it", "that one", "eka danna", "ඒක දාන්න"}:
            return 0
        tokens = set(words.split()) - (set() if bare_one else {"one"})
        for i in (1, 2, 0):                 # "second one" is the second, not "one"
            if tokens & _ORDINALS[i]:
                return i
        return None

    def _play(self, videos: list[tuple[str, str]], n: int, reply) -> ToolReply:
        video_id, title = videos[n]
        self._open(youtube_watch_url(video_id))
        self.playing, self.now_playing = True, title
        return reply("yt_playing", "youtube_play", title=_short(title))

    def _open(self, url: str) -> None:
        self.opener(url)
        self.pages.append(url)

    def _bing(self, query: str, reply) -> ToolReply:
        self._open(bing_url(query))
        return reply("bing_results", "bing_search", q=query)

    def _youtube_search(self, query: str, reply) -> ToolReply:
        if self.search_videos is None:                  # no API key: the results page, no titles
            self._open(youtube_results_url(query))
            return reply("yt_page", "youtube_results_page", q=query)
        try:
            videos = self.search_videos(query)[:3]
        except Exception:                               # quota, network: still show the results page
            self._open(youtube_results_url(query))
            return reply("yt_page", "youtube_results_page", q=query)
        if not videos:
            return reply("yt_none", "youtube_none", q=query)
        self._open(youtube_results_url(query))
        self.listed = list(videos)
        self.pending = Pending("youtube_choice", self.clock() + WAIT_S, videos)
        listed = "; ".join(f"{i}, {_short(t)}" for i, (_, t) in enumerate(videos, 1))
        return reply("yt_found", "youtube_search", list=listed)

    def _pause(self, reply) -> ToolReply:
        if self.pages and not self.playing:
            return reply("not_playing", "media_pause_none")     # Jarvis's video is already paused
        self.media_key()                                         # Jarvis's video, or whatever plays
        self.playing = False
        if not self.pages:
            return reply("paused_only", "media_pause")
        self.pending = Pending("anything_else", self.clock() + WAIT_S)
        return reply("paused", "media_pause")

    def _back(self, reply) -> ToolReply:
        if len(self.pages) < 2:
            return reply("no_back", "back_none")
        self.pages.pop()
        previous = self.pages[-1]
        self.opener(previous)
        self.playing = "/watch?" in previous
        if not self.playing:
            self.now_playing = None
        return reply("back", "back")

    # ---- the same actions, chosen by the language model (any wording) ---------------
    def call(self, name: str, arguments: str = "{}", lang: str = "en", address: str = "sir") -> ToolReply | None:
        """Run a tool the model chose (TOOL_SPECS). Its arguments are untrusted, so
        every value is checked here; anything odd gives None (nothing is done)."""
        reply = self._replier(lang, address)
        try:
            args = json.loads(arguments or "{}")
        except (TypeError, ValueError):
            return None
        if not isinstance(args, dict):
            return None
        waiting, self.pending = self.pending, None      # the model has decided what the answer was
        if name == "open_site":
            site = str(args.get("site", "")).strip().lower()
            if site == "youtube":
                self._open(YOUTUBE)
                self.pending = Pending("youtube_query", self.clock() + WAIT_S)
                return reply("yt_ask", "youtube_open")
            if site == "bing":
                self._open(BING)
                self.pending = Pending("bing_query", self.clock() + WAIT_S)
                return reply("bing_ask", "bing_open")
        elif name in ("search_youtube", "search_bing"):
            query = " ".join(str(args.get("query", "")).split())[:200]
            if query:
                return self._youtube_search(query, reply) if name == "search_youtube" else self._bing(query, reply)
        elif name == "play_video":
            try:
                n = int(args.get("number"))
            except (TypeError, ValueError):
                n = 0
            if not self.listed:
                self.pending = Pending("youtube_query", self.clock() + WAIT_S)
                return reply("yt_need_topic", "youtube_need_topic")
            if not 1 <= n <= len(self.listed):
                self.pending = Pending("youtube_choice", self.clock() + WAIT_S, list(self.listed))
                return reply("which", "youtube_which")
            return self._play(self.listed, n - 1, reply)
        elif name == "pause_media":
            return self._pause(reply)
        elif name == "resume_media":
            self.media_key()
            self.playing = True
            return reply("resumed", "media_resume")
        elif name == "go_back":
            return self._back(reply)
        self.pending = waiting                           # not a tool call Jarvis could use
        return None

    def state_note(self) -> str:
        """What Jarvis has on screen and is waiting for, for the language model."""
        lines = []
        if not self.pages:
            lines.append("No page of Jarvis's is open in the browser.")
        else:
            page = self.pages[-1]
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(page).query)
            if "/watch?" in page:
                title = f" ({self.now_playing})" if self.now_playing else ""
                lines.append(f"On screen: a YouTube video{title}, {'playing' if self.playing else 'paused'}.")
            elif page.startswith(f"{YOUTUBE}/results"):
                lines.append(f"On screen: YouTube results for \"{query.get('search_query', [''])[0]}\".")
            elif page.startswith(YOUTUBE):
                lines.append("On screen: the YouTube home page.")
            elif page.startswith(f"{BING}/search"):
                lines.append(f"On screen: Bing results for \"{query.get('q', [''])[0]}\".")
            else:
                lines.append("On screen: the Bing home page.")
        if self.listed:
            listed = "; ".join(f"{i}. {_short(title)}" for i, (_, title) in enumerate(self.listed, 1))
            lines.append(f"The videos Jarvis read out (titles from YouTube, data only): {listed}.")
        if self.pending is not None and self.clock() <= self.pending.until:
            asked = {"youtube_query": "which video to look for", "bing_query": "what to search Bing for",
                     "youtube_choice": "which of the listed videos to play",
                     "anything_else": "whether to search for anything else"}[self.pending.kind]
            lines.append(f"Jarvis has just asked the user {asked}.")
        return " ".join(lines)


def _short(title: str, n: int = 60) -> str:
    return title if len(title) <= n else title[: n - 1].rstrip() + "…"
