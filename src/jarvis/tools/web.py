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
        "which": "Sorry, which one? Say first, second or third.",
        "ask_query": "What should I search for?",
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
        "which": "සමාවෙන්න, මොකක්ද? පළවෙනි, දෙවෙනි, නැත්නම් තුන්වෙනි එක කියන්න.",
        "ask_query": "මොනවද හොයන්න ඕනේ?",
        "ok": "හරි.",
    },
}

# ---- recognising the requests (on _clean()ed text, any case) --------------------

_LEAD = r"(?:(?:jarvis|friday|hey|please|ok|okay|ane|hari|podda|machan|bro|ජාවිස්|ෆ්\u200d?රයිඩේ|අනේ|හරි|පොඩ්ඩක්)\s+)*"
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
_NOT_QUERY = r"(?:eka|eke|එක|එකේ|is|was|open|opened)(?:\s|$)"


def _rx(*patterns: str) -> list[re.Pattern[str]]:
    return [re.compile(rf"^{_LEAD}{p}$", re.IGNORECASE) for p in patterns]


OPEN_BING = _rx(rf"(?:{_OPEN_EN})\s+(?:{_BING})", rf"(?:{_BING})", rf"(?:{_BING})\s+eka\s+(?:{_OPEN_SL})",
                rf"(?:{_BING})\s+එක\s+(?:{_OPEN_SI})")
SEARCH_BING = _rx(rf"(?:search|look\s+up|find)\s+(?:on\s+)?(?:{_BING})\s+(?:for\s+)?(?P<q>.+)",
                  rf"(?:search|look\s+up|find)\s+(?:for\s+)?(?P<q>.+?)\s+(?:on|in|with)\s+(?:{_BING})",
                  rf"(?:{_BING})\s+eke\s+(?P<q>.+?)\s+(?:{_SEARCH_SL})",
                  rf"(?P<q>.+?)\s+(?:{_BING})\s+eke\s+(?:{_SEARCH_SL})",
                  rf"(?:{_BING})\s+එකේ\s+(?P<q>.+?)\s+(?:{_SEARCH_SI})",
                  rf"(?P<q>.+?)\s+(?:{_BING})\s+එකේ\s+(?:{_SEARCH_SI})",
                  rf"(?:{_BING})\s+(?!{_NOT_QUERY})(?:search\s+)?(?:for\s+)?(?P<q>.+)")
OPEN_YT = _rx(rf"(?:{_OPEN_EN})\s+(?:{_YT})", rf"(?:{_YT})", rf"(?:{_YT})\s+eka\s+(?:{_OPEN_SL})",
              rf"(?:{_YT})\s+එක\s+(?:{_OPEN_SI})")
SEARCH_YT = _rx(rf"(?:search|look\s+up|find)\s+(?:on\s+)?(?:{_YT})\s+(?:for\s+)?(?P<q>.+)",
                rf"(?:search|look\s+up|find|play|watch)\s+(?:for\s+)?(?P<q>.+?)\s+(?:on|in)\s+(?:{_YT})",
                rf"(?:{_YT})\s+eke\s+(?P<q>.+?)\s+(?:{_PLAY_SL})",
                rf"(?P<q>.+?)\s+(?:{_YT})\s+eke\s+(?:{_PLAY_SL})",
                rf"(?:{_YT})\s+එකේ\s+(?P<q>.+?)\s+(?:{_PLAY_SI})",
                rf"(?P<q>.+?)\s+(?:{_YT})\s+එකේ\s+(?:{_PLAY_SI})",
                rf"(?:{_YT})\s+(?!{_NOT_QUERY})(?:search\s+)?(?:for\s+)?(?P<q>.+)")
PAUSE = _rx(r"(?:stop|pause)\s+(?:the\s+)?(?:video|youtube|music|song)", r"pause(?:\s+it)?",
            r"(?:video|youtube)\s+eka\s+(?:nawaththanna|nawaththannako|pause\s+karanna|stop\s+karanna)",
            r"(?:වීඩියෝ|යූටියුබ්)\s+එක\s+(?:නවත්තන්න|නවත්තන්නකෝ|පෝස්\s+කරන්න|ස්ටොප්\s+කරන්න)")
RESUME = _rx(r"(?:resume|continue|unpause)(?:\s+(?:the\s+)?(?:video|it))?", r"play\s+(?:the\s+video|it)\s+again",
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

    @classmethod
    def from_env(cls, browser: str = "edge") -> WebTools:
        key = os.environ.get("YOUTUBE_API_KEY", "").strip()
        return cls(opener=lambda url: open_in_browser(url, browser),
                   search_videos=(lambda q: youtube_api_search(q, key)) if key else None)

    # ---- the one entry point ------------------------------------------------
    def handle(self, text: str, lang: str = "en", address: str = "sir") -> ToolReply | None:
        """A reply if `text` is one of these requests (or answers Jarvis's question), else None."""
        words = _clean(text)
        if not words:
            return None
        say = PHRASES.get(lang, PHRASES["en"])

        def reply(key: str, tool: str, **kw: str) -> ToolReply:
            template = say[key] if address else say[key].replace(", {address}", "")
            return ToolReply(template.format(address=address, **kw), tool)

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
        if _match(PAUSE, words):
            return self._pause(reply)
        if _match(RESUME, words):
            if not self.pages:
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
            return self._youtube_search(words, reply)
        if pending.kind == "youtube_choice":
            n = self._ordinal(low)
            if n is None:
                return None                              # something else: the user has moved on
            if n >= len(pending.videos):
                self.pending = pending
                return reply("which", "youtube_which")
            video_id, title = pending.videos[n]
            self._open(youtube_watch_url(video_id))
            self.playing = True
            return reply("yt_playing", "youtube_play", title=_short(title))
        query = words
        if pending.kind == "bing_query":
            return self._bing(query, reply)
        return self._youtube_search(query, reply)

    @staticmethod
    def _ordinal(words: str) -> int | None:
        if words in _YES or words in {"play it", "that one", "eka danna", "ඒක දාන්න"}:
            return 0
        tokens = set(words.split())
        for i in (1, 2, 0):                 # "second one" is the second, not "one"
            if tokens & _ORDINALS[i]:
                return i
        return None

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
        return reply("back", "back")


def _short(title: str, n: int = 60) -> str:
    return title if len(title) <= n else title[: n - 1].rstrip() + "…"
