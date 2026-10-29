"""Tools that look things up for the model: news, the news map, Wikipedia, papers, checked maths.

All "just do it" (they only read, or write a map page into Jarvis's folder)
and all through the gate like every other tool. Each returns what it found as
data for the model (Result.data["for_model"]): Jarvis then asks the model a
second time, with that data marked as fetched and untrusted, and the model
answers from it, naming its sources (app.py, KNOWLEDGE_NOTES).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ..knowledge.mathcheck import TASKS, MathError, check
from ..knowledge.news import THEMES, NewsDesk, Story, for_the_model
from ..knowledge.news_map import save_map
from ..knowledge.research import Research, page_for_the_model, papers_for_the_model
from .gate import ActionLog, Gate
from .registry import Args, Registry, Result, Tier, Tool


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


class InfoTools:
    def __init__(self, jarvis_folder: Path | str, log: ActionLog | None = None, *, news: NewsDesk | None = None,
                 research: Research | None = None, opener: Callable[[str], None] | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self.home = Path(jarvis_folder).expanduser()
        self.news = news or NewsDesk()
        self.research = research or Research()
        self.opener = opener or _open_in_browser
        self.now = now
        self.last_stories: list[Story] = []
        self.registry = Registry(self._tools())
        self.gate = Gate(self.registry, [self.home], log)

    # ---- news ------------------------------------------------------------------------
    def _get_news(self, args: Args) -> Result:
        theme, country, topic = args.get("theme", ""), args.get("country", ""), args.get("topic", "")
        theme = "" if theme == "any" else theme
        stories = self.news.headlines(theme=theme, country=country, topic=topic, hours=int(args.get("hours", 24)))
        if stories:
            self.last_stories = stories
        asked = ", ".join(x for x in (topic, theme, country) if x) or "the world's top stories"
        return Result(True, f"Found {len(stories)} stories." if stories else "I couldn't get any news.",
                      data={"for_model": for_the_model(stories, self.now(), asked), "kind": "news",
                            "say": ("news_found" if stories else "news_none", {"n": len(stories)})})

    def _read_article(self, args: Args) -> Result:
        n = int(args["number"])
        if not 1 <= n <= len(self.last_stories):
            return Result(False, "There's no story with that number; ask for the news first.",
                          data={"for_model": "No such story number in the last news Jarvis fetched.", "kind": "news"})
        story = self.last_stories[n - 1]
        text = self.news.read(story)
        body = text or "(the site didn't let Jarvis read the article; only the headline is known)"
        return Result(True, f"Read story {n}.", data={"kind": "news", "for_model": (
            f"Story {n}: {story.title} ({story.source}, {story.url})\nArticle text (first part):\n{body}")})

    def _show_news_map(self, args: Args) -> Result:
        theme = args.get("theme", "all")
        stories = self.news.headlines(theme="" if theme == "all" else theme, topic=args.get("topic", ""),
                                      hours=24, limit=60)
        if not stories:
            return Result(False, "I couldn't get any news for the map.", data={"say": ("news_none", {})})
        self.last_stories = stories[:20]
        title = "World news" + ("" if theme == "all" else f": {theme}")
        path = save_map(stories, self.home / "news", title, self.now())
        self.opener(path.as_uri())
        places = sorted({p for s in stories for p in s.places})
        return Result(True, f"Opened the news map: {len(stories)} stories in {len(places)} countries.",
                      data={"path": str(path), "kind": "news",
                            "say": ("map_opened", {"n": len(stories), "countries": len(places)}),
                            "for_model": for_the_model(stories[:20], self.now(), title)})

    def _map_saved(self, args: Args, result: Result) -> bool:
        return Path(result.data["path"]).exists()

    # ---- research ------------------------------------------------------------------------
    def _look_up(self, args: Args) -> Result:
        page = self.research.wikipedia(args["query"], args.get("language", "en"))
        return Result(True, f"Looked up {args['query']}.",
                      data={"for_model": page_for_the_model(page, args["query"]), "kind": "research"})

    def _find_papers(self, args: Args) -> Result:
        papers = self.research.papers(args["query"], args.get("since_year"), int(args.get("limit", 5)))
        return Result(True, f"Found {len(papers)} papers.",
                      data={"for_model": papers_for_the_model(papers, args["query"]), "kind": "research"})

    # ---- maths ------------------------------------------------------------------------
    def _check_maths(self, args: Args) -> Result:
        try:
            done = check(args["task"], args["expression"], args.get("variable", "x"), args.get("lower", ""),
                         args.get("upper", ""), args.get("point", ""), int(args.get("order", 0)))
        except MathError as exc:
            return Result(True, "SymPy couldn't check that.", data={"kind": "maths", "for_model": (
                f"SymPy couldn't check {args['task']} of {args['expression']}: {exc}. Don't state an unchecked "
                "result as checked; say what you can and that it's unchecked.")})
        return Result(True, done.result, data={"for_model": done.for_the_model(), "kind": "maths"})

    def _tools(self) -> list[Tool]:
        text = {"type": "string", "maxLength": 120}
        return [
            Tool("get_news", "Get the latest news headlines (last 24 h by default) to brief the user: optionally "
                 "a theme, a country (e.g. 'Sri Lanka', 'Russia') or a topic. Use it for any question about "
                 "current events; never answer those from memory.",
                 _obj({"theme": {"type": "string", "enum": ["any", *THEMES]}, "country": {**text, "maxLength": 40},
                       "topic": {**text, "maxLength": 80}, "hours": {"type": "integer", "minimum": 1, "maximum": 72}},
                      []), Tier.JUST_DO, self._get_news),
            Tool("read_article", "Read the text of one of the stories Jarvis just listed (by its number), to "
                 "explain it in more depth.", _obj({"number": {"type": "integer", "minimum": 1, "maximum": 60}},
                                                   ["number"]), Tier.JUST_DO, self._read_article),
            Tool("show_news_map", "Open a world map of today's news in the browser, stories placed on the "
                 "countries they're about and coloured by theme.",
                 _obj({"theme": {"type": "string", "enum": ["all", "technology", "politics", "military", "space",
                                                            "business"]},
                       "topic": {**text, "maxLength": 80}}, []),
                 Tier.JUST_DO, self._show_news_map, verify=self._map_saved),
            Tool("look_up", "Look something up on Wikipedia (background on a person, place, idea or event).",
                 _obj({"query": text, "language": {"type": "string", "enum": ["en", "si", "ta"]}}, ["query"]),
                 Tier.JUST_DO, self._look_up),
            Tool("find_papers", "Find research papers on a topic (OpenAlex): authors, year, venue, DOI, citations "
                 "and abstract. Use it for literature, 'latest research', references.",
                 _obj({"query": {**text, "maxLength": 160}, "since_year": {"type": "integer", "minimum": 1900,
                                                                            "maximum": 2100},
                       "limit": {"type": "integer", "minimum": 1, "maximum": 8}}, ["query"]),
                 Tier.JUST_DO, self._find_papers),
            Tool("check_maths", "Work out or check maths with SymPy before stating any result: simplify, expand, "
                 "factor, solve (an equation with =), differentiate, integrate (give lower and upper for a "
                 "definite integral), limit (at point), series (about point, to order), evaluate (a number). "
                 "Write maths like x^2 sin(x), exp(-x^2), sqrt(2), pi, oo.",
                 _obj({"task": {"type": "string", "enum": list(TASKS)}, "expression": {**text, "maxLength": 300},
                       "variable": {"type": "string", "pattern": "^[A-Za-z][0-9]{0,2}$"},
                       "lower": {**text, "maxLength": 40}, "upper": {**text, "maxLength": 40},
                       "point": {**text, "maxLength": 40}, "order": {"type": "integer", "minimum": 1, "maximum": 12}},
                      ["task", "expression"]), Tier.JUST_DO, self._check_maths),
        ]

    def call(self, name: str, arguments: str = "{}", *, untrusted: bool = False, remote: bool = False):
        return self.gate.call(name, arguments, untrusted=untrusted, remote=remote)

    def names(self) -> set[str]:
        return set(self.registry.names())


def _open_in_browser(url: str) -> None:
    import webbrowser
    webbrowser.open(url)
