"""The latest news: worldwide by theme (GDELT), Sri Lanka (local RSS feeds), and world headlines (BBC).

    desk = NewsDesk()
    stories = desk.headlines(theme="space")             # the last 24 h, newest first
    stories = desk.headlines(country="Sri Lanka")
    text = desk.read(stories[0])                        # the article's own words, for "tell me more"

Only headlines, short descriptions and, on request, an article's text are
fetched; Jarvis summarises them and names the source of each. GDELT
(api.gdeltproject.org, free, no key) searches news sites worldwide; it asks
for one request every 5 seconds (knowledge/fetch.py keeps to that).
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from .fetch import FetchError, Get, get_text, url_with
from .places import countries_in

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
SRI_LANKA_FEEDS = {
    "Ada Derana": "https://www.adaderana.lk/rss.php",
    "EconomyNext": "https://economynext.com/feed/",
    "Daily News": "https://www.dailynews.lk/feed/",
}
WORLD_FEED = ("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml")

# Words that put a headline under a theme (whole words, lower case), and the
# search GDELT gets for it (terms of 3+ letters; OR needs the parentheses).
THEMES: dict[str, tuple[tuple[str, ...], str]] = {
    "technology": (("tech", "technology", "ai", "artificial intelligence", "software", "chip", "chips",
                    "semiconductor", "cyber", "cyberattack", "hack", "hackers", "smartphone", "internet",
                    "openai", "google", "microsoft", "apple", "nvidia", "robot", "robots", "quantum", "startup"),
                   '(technology OR "artificial intelligence" OR semiconductor OR cybersecurity OR software)'),
    "politics": (("election", "elections", "vote", "voters", "parliament", "president", "prime minister",
                  "minister", "government", "opposition", "party", "senate", "congress", "cabinet", "policy",
                  "protest", "protests", "sanctions", "diplomacy", "summit", "budget"),
                 '(election OR parliament OR president OR "prime minister" OR government OR diplomacy)'),
    "military": (("war", "military", "army", "troops", "soldiers", "missile", "missiles", "drone", "drones",
                  "strike", "strikes", "airstrike", "attack", "attacks", "navy", "ceasefire", "defence", "defense",
                  "conflict", "rebels", "shelling", "weapons", "invasion", "nuclear"),
                 '(military OR war OR troops OR missile OR ceasefire OR defence)'),
    "space": (("space", "nasa", "isro", "esa", "spacex", "rocket", "satellite", "satellites", "moon", "lunar",
               "mars", "orbit", "astronaut", "astronauts", "telescope", "asteroid", "spacecraft", "launch"),
              '(space OR NASA OR ISRO OR SpaceX OR rocket OR satellite OR astronaut OR telescope)'),
    "business": (("economy", "economic", "inflation", "market", "markets", "stocks", "shares", "bank", "rupee",
                  "dollar", "trade", "tariff", "tariffs", "imf", "exports", "imports", "gdp", "investment"),
                 '(economy OR inflation OR markets OR trade OR investment)'),
    "sport": (("cricket", "football", "match", "cup", "olympic", "olympics", "tennis", "rugby", "tournament",
               "league", "squad", "wicket", "goal"),
              '(cricket OR football OR tournament OR olympics)'),
}
_THEME_RE = {name: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in words) + r")(?!\w)")
             for name, (words, _) in THEMES.items()}


@dataclass
class Story:
    title: str
    url: str
    source: str                          # the site or feed ("Ada Derana", "reuters.com")
    when: datetime | None = None         # UTC
    summary: str = ""                    # the feed's short description, if any
    theme: str = "other"
    places: list[str] = field(default_factory=list)   # countries the headline is about

    def age(self, now: datetime) -> str:
        if self.when is None:
            return "time unknown"
        minutes = max(0, int((now - self.when).total_seconds() // 60))
        if minutes < 60:
            return f"{minutes} min ago"
        if minutes < 48 * 60:
            return f"{minutes // 60} h ago"
        return f"{minutes // 1440} days ago"


def theme_of(title: str) -> str:
    low = title.lower()
    hits = {name: len(rx.findall(low)) for name, rx in _THEME_RE.items()}
    best = max(hits, key=lambda k: hits[k])
    return best if hits[best] else "other"


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _gdelt_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def parse_gdelt(text: str) -> list[Story]:
    """GDELT's ArtList JSON; a plain-text answer (a rate-limit note, a query error) gives nothing."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    stories = []
    for a in (data.get("articles") or []) if isinstance(data, dict) else []:
        title = clean(a.get("title", ""))
        if title and a.get("url"):
            stories.append(Story(title, a["url"], a.get("domain") or urlsplit(a["url"]).hostname or "",
                                 _gdelt_time(a.get("seendate", ""))))
    return stories


def parse_rss(text: str, source: str) -> list[Story]:
    try:
        root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError:
        return []
    stories = []
    for item in root.iter("item"):
        title = clean(item.findtext("title", ""))
        link = (item.findtext("link") or "").strip()
        when = None
        if item.findtext("pubDate"):
            try:
                when = parsedate_to_datetime(item.findtext("pubDate")).astimezone(UTC)
            except (TypeError, ValueError, IndexError):
                when = None
        if title and link.startswith("http"):
            stories.append(Story(title, link, source, when, clean(item.findtext("description", ""))[:300]))
    return stories


def _same(a: str, b: str) -> bool:
    wa, wb = set(re.findall(r"\w{4,}", a.lower())), set(re.findall(r"\w{4,}", b.lower()))
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= 0.7


class NewsDesk:
    def __init__(self, get: Get = get_text, now=lambda: datetime.now(UTC)):
        self.get, self.now = get, now

    def _fetch(self, url: str) -> str | None:
        try:
            return self.get(url)
        except FetchError:
            return None

    def _gdelt(self, query: str, hours: int, limit: int) -> list[Story]:
        text = self._fetch(url_with(GDELT, {"query": f"{query} sourcelang:english", "mode": "ArtList",
                                            "format": "json", "maxrecords": limit, "sort": "datedesc",
                                            "timespan": f"{hours}h"}))
        return parse_gdelt(text) if text else []

    def _feed(self, source: str, url: str) -> list[Story]:
        text = self._fetch(url)
        return parse_rss(text, source) if text else []

    def headlines(self, theme: str = "", country: str = "", topic: str = "", hours: int = 24,
                  limit: int = 8) -> list[Story]:
        """Newest first, one story per event, each with its theme and the countries it mentions."""
        theme = theme if theme in THEMES else ""
        topic = re.sub(r"[^\w\s\-'\"]", " ", topic or "").strip()[:80]
        country = (country or "").strip()[:40]
        local = country.lower() in ("sri lanka", "lanka", "srilanka")
        stories: list[Story] = []
        if local:
            for source, url in SRI_LANKA_FEEDS.items():
                stories += self._feed(source, url)
        if theme or topic or (country and not local):
            words = [w for w in (f'"{topic}"' if " " in topic else topic,
                                 f'"{country}"' if country and " " in country else country,
                                 THEMES[theme][1] if theme else "") if w]
            stories += self._gdelt(" ".join(words), hours, 40)
        if not stories:
            stories = self._feed(*WORLD_FEED)
        now = self.now()
        cutoff = now - timedelta(hours=max(hours, 24) * 2)
        stories = [s for s in stories if s.when is None or s.when >= cutoff]
        for s in stories:
            s.theme = theme_of(s.title)
            s.places = countries_in(s.title) or (["Sri Lanka"] if s.source in SRI_LANKA_FEEDS else [])
        if local and (theme or topic):
            keep = [s for s in stories if (not theme or s.theme == theme)
                    and (not topic or topic.lower() in (s.title + " " + s.summary).lower())]
            stories = keep or stories
        stories.sort(key=lambda s: s.when or datetime.min.replace(tzinfo=UTC), reverse=True)
        unique: list[Story] = []
        for s in stories:
            if not any(_same(s.title, u.title) for u in unique):
                unique.append(s)
        return unique[:limit]

    def read(self, story: Story, max_chars: int = 3000) -> str:
        """The article's paragraphs (for "tell me more"), or "" when the site won't give them."""
        page = self._fetch(story.url)
        if not page:
            return ""
        page = re.sub(r"(?is)<(script|style|noscript|header|footer|nav|aside)[^>]*>.*?</\1>", " ", page)
        paragraphs = [clean(p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", page)]
        text = " ".join(p for p in paragraphs if len(p) > 60)
        return text[:max_chars]


def for_the_model(stories: list[Story], now: datetime, asked: str) -> str:
    """The stories as numbered data for the model to brief from."""
    if not stories:
        return f"No news found for: {asked}. Say so plainly; don't make any up."
    lines = [f"Latest news for: {asked} (fetched {now:%Y-%m-%d %H:%M} UTC; headlines and short descriptions only):"]
    for i, s in enumerate(stories, 1):
        where = f"; about {', '.join(s.places)}" if s.places else ""
        lines.append(f"{i}. {s.title} ({s.source}, {s.age(now)}; {s.theme}{where})")
        if s.summary and not _same(s.summary, s.title):
            lines.append(f"   {s.summary[:240]}")
    return "\n".join(lines)
