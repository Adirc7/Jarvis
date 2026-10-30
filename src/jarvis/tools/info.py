"""Tools that look things up for the model: news, weather, the maps, Wikipedia, papers, checked maths.

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

from ..knowledge.mathcheck import TASKS, MathError, check, sample
from ..knowledge.news import THEMES, NewsDesk, Story, for_the_model
from ..knowledge.news_map import save_map
from ..knowledge.places import countries_in, where
from ..knowledge.research import Research, page_for_the_model, papers_for_the_model
from ..knowledge.weather import (
    SRI_LANKA_TOWNS,
    Place,
    Weather,
    WeatherError,
    alerts_for_the_model,
    forecast_for_the_model,
)
from ..knowledge.weather_map import save_weather_map
from .gate import ActionLog, Gate
from .registry import Args, Registry, Result, Tier, Tool

MAP_OPEN = ("The map is open on the user's screen now (Jarvis opened it in his window): say so, and point "
            "out what stands out on it")


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


class InfoTools:
    def __init__(self, jarvis_folder: Path | str, log: ActionLog | None = None, *, news: NewsDesk | None = None,
                 research: Research | None = None, weather: Weather | None = None,
                 opener: Callable[[str], None] | None = None, now: Callable[[], datetime] = lambda: datetime.now(UTC),
                 screen: Callable[[str, dict], bool] | None = None):
        self.home = Path(jarvis_folder).expanduser()
        self.news = news or NewsDesk()
        self.research = research or Research()
        self.weather = weather or Weather()
        self.opener = opener or _open_in_browser
        self.now = now
        # The window (app.py): screen(kind, data) shows a map move or the board; True if a window shows it.
        self.screen = screen or (lambda kind, data: False)
        self.screen_given = screen is not None
        self.board: dict | None = None             # what the board shows now (the window asks for it)
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
                            "for_model": f"{MAP_OPEN}\n" + for_the_model(stories[:20], self.now(), title)})

    def _map_saved(self, args: Args, result: Result) -> bool:
        return Path(result.data["path"]).exists()

    # ---- weather ------------------------------------------------------------------------
    def _get_weather(self, args: Args) -> Result:
        names, country, days = args["places"], args.get("country", ""), int(args.get("days", 7))
        parts, found, missing = [], [], []
        try:
            for name in names:
                place = self.weather.find(name, country)
                if place is None:
                    missing.append(name)
                    continue
                fc = self.weather.forecast(place, days)
                usual = self.weather.usual_rain(place, fc.days)
                try:
                    alerts = self.weather.alerts(near=place)
                except WeatherError:
                    alerts = []
                parts.append(forecast_for_the_model(fc, usual, alerts, self.now()))
                found.append(place.label())
        except WeatherError as exc:
            return Result(False, "I couldn't get the weather.", data={"kind": "weather", "say": ("weather_none", {}),
                          "for_model": f"The weather service didn't answer ({exc}). Say so; don't guess."})
        if missing:
            parts.append(f"No place found called: {', '.join(missing)}. Say so and ask which place they mean.")
        if not found:
            return Result(False, "I couldn't find that place.", data={"kind": "weather", "for_model": "\n".join(parts),
                                                                       "say": ("weather_none", {})})
        return Result(True, f"Got the weather for {'; '.join(found)}.",
                      data={"kind": "weather", "for_model": "\n\n".join(parts)})

    def _weather_alerts(self, args: Args) -> Result:
        country, place_name = args.get("country", ""), args.get("place", "")
        try:
            place = self.weather.find(place_name, country) if place_name else None
            alerts = self.weather.alerts(country="" if place else country, near=place)
        except WeatherError as exc:
            return Result(False, "I couldn't reach GDACS.", data={"kind": "weather", "for_model": (
                f"GDACS didn't answer ({exc}). Say so; don't guess.")})
        where = (f"within 1,200 km of {place.label()}" if place else
                 f"in or within 1,500 km of {country}" if country else "worldwide")
        return Result(True, f"Found {len(alerts)} alerts.", data={"kind": "weather", "for_model": "\n".join(
            alerts_for_the_model(alerts, where))})

    def _show_weather_map(self, args: Args) -> Result:
        area = (args.get("area") or "Sri Lanka").strip()
        try:
            if area.lower() in ("sri lanka", "lanka", "srilanka"):
                places = [Place(n, lat, lon, "Sri Lanka", kind="PPL") for n, (lat, lon) in SRI_LANKA_TOWNS.items()]
                centre, zoom, alerts = (7.8, 80.7), 7, self.weather.alerts(near=places[0], radius_km=1500)
            elif area.lower() in ("world", "the world", "everywhere"):
                places, centre, zoom, alerts = [], (15.0, 30.0), 2, self.weather.alerts()
            else:
                place = self.weather.find(area)
                if place is None:
                    return Result(False, f"I couldn't find {area}.", data={"kind": "weather", "for_model": (
                        f"No place found called {area}. Say so and ask which place they mean.")})
                places = [place]
                centre, zoom = (place.lat, place.lon), 5 if place.kind.startswith("PCL") else 9
                alerts = self.weather.alerts(near=place, radius_km=1500)
            forecasts = self.weather.forecasts(places, 7)
        except WeatherError as exc:
            return Result(False, "I couldn't get the weather for the map.", data={"kind": "weather", "for_model": (
                f"The weather services didn't answer ({exc}). Say so.")})
        title = f"Weather: {area}"
        path = save_weather_map(forecasts, alerts, self.home / "weather", title, self.now(), centre, zoom)
        self.opener(path.as_uri())
        wettest = sorted(((fc.days[0].rain_mm or 0, fc.place.name) for fc in forecasts if fc.days), reverse=True)[:5]
        summary = "; ".join(f"{name} {mm:.1f} mm today" for mm, name in wettest)
        return Result(True, f"Opened the weather map: {len(forecasts)} places, {len(alerts)} alerts.",
                      data={"path": str(path), "kind": "weather", "say": ("weather_map", {"n": len(forecasts)}),
                            "for_model": (f"{MAP_OPEN} ({title}). Wettest today: {summary or 'n/a'}.\n"
                                          + "\n".join(alerts_for_the_model(alerts, "on the map")))})

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
        if done.latex:                                   # the checked result goes on the board too
            card = {"text": f"Checked by SymPy ({done.task})", "math": done.latex}
            board = self.board if self.board and self.board.get("from") == "check_maths" else {
                "title": "Worked and checked", "steps": [], "plots": [], "from": "check_maths"}
            board["steps"] = [*board["steps"], card][-8:]
            self._show_board(board)
        return Result(True, done.result, data={"for_model": done.for_the_model(), "kind": "maths"})

    # ---- the window: moving the map, the board ------------------------------------------------
    def _show_board(self, board: dict) -> bool:
        board["made"] = self.now().isoformat(timespec="seconds")
        self.board = board
        return self.screen("board", board)

    def _show_on_board(self, args: Args) -> Result:
        steps = [{"text": str(st.get("text", ""))[:400], "math": str(st.get("math", ""))[:400]}
                 for st in args.get("steps", []) if isinstance(st, dict)][:12]
        plots, problems = [], []
        for g in args.get("graphs", [])[:3]:
            try:
                points = sample(g["expression"], g.get("variable", "x"), float(g.get("from", -5)),
                                float(g.get("to", 5)))
                plots.append({"label": str(g.get("label") or g["expression"])[:60], "points": points})
            except (MathError, KeyError, ValueError) as exc:
                problems.append(f"couldn't draw {g.get('expression', '?')}: {exc}")
        shown = self._show_board({"title": str(args["title"])[:120], "steps": steps, "plots": plots,
                                  "from": "show_on_board"})
        where = "on the board in Jarvis's window" if shown else "on the board (the window isn't open; it shows when opened)"
        text = (f"Jarvis put this {where}: {args['title']} ({len(steps)} steps, {len(plots)} graphs). "
                + (" ".join(problems) + " " if problems else "")
                + "Now explain it in words, step by step, referring to what's on the board; don't read the "
                  "formulas out symbol by symbol.")
        return Result(True, f"Put {args['title'][:60]} on the board.", data={"kind": "maths", "for_model": text,
                      "say": ("board_shown", {})})

    def _map_view(self, args: Args) -> Result:
        action, place_name = args["action"], (args.get("place") or "").strip()
        data: dict = {"action": action}
        if action == "focus":
            if not place_name:
                return Result(False, "Which place should I show?")
            spot = where(countries_in(place_name)[0]) if countries_in(place_name) else None
            if spot is not None:
                data.update(lat=spot[0], lon=spot[1], zoom=7 if countries_in(place_name)[0] == "Sri Lanka" else 5,
                            label=countries_in(place_name)[0])
            else:
                try:
                    found = self.weather.find(place_name)
                except WeatherError:
                    found = None
                if found is None:
                    return Result(False, f"I couldn't find {place_name} to show it on the map.")
                data.update(lat=found.lat, lon=found.lon, zoom=5 if found.kind.startswith("PCL") else 11,
                            label=found.label())
        if not self.screen("map_cmd", data):
            return Result(False, "The map isn't open in my window; ask me for the news map or the weather map first.")
        said = {"focus": f"Showing {data.get('label', place_name)}.", "zoom_in": "Zooming in.",
                "zoom_out": "Zooming out.", "close": "Closed the map."}[action]
        return Result(True, said, data={"say": (f"map_{action}", {"place": data.get("label", place_name)})})

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
            Tool("get_weather", "Get the weather for one or more places (towns, cities; e.g. 'Kaduwela', "
                 "'Colombo', 'Chennai'): now, the next 24 hours of rain, and day by day up to 16 days (rain in mm "
                 "and its chance, temperature, wind, UV), the usual rain for those dates, and storm or flood alerts "
                 "nearby. For a country, pass its main cities. Use it for any weather question; never guess.",
                 _obj({"places": {"type": "array", "items": {**text, "maxLength": 60}, "minItems": 1, "maxItems": 6},
                       "country": {**text, "maxLength": 40},
                       "days": {"type": "integer", "minimum": 1, "maximum": 16}}, ["places"]),
                 Tier.JUST_DO, self._get_weather),
            Tool("weather_alerts", "Current storm and disaster alerts from GDACS (tropical cyclones, floods, "
                 "earthquakes, volcanoes, droughts, wildfires): worldwide, in or near a country, or near a place. "
                 "Not tornadoes.", _obj({"country": {**text, "maxLength": 40}, "place": {**text, "maxLength": 60}},
                                        []), Tier.JUST_DO, self._weather_alerts),
            Tool("show_weather_map", "Open a weather map in the browser: rain and temperature day by day for "
                 "Sri Lanka's towns (the default), a place, or 'world', with storm alerts and rain radar.",
                 _obj({"area": {**text, "maxLength": 60}}, []), Tier.JUST_DO, self._show_weather_map,
                 verify=self._map_saved),
            Tool("map_view", "Move the map open in Jarvis's window: focus on a place (it zooms there), zoom in or "
                 "out, or close it.", _obj({"action": {"type": "string", "enum": ["focus", "zoom_in", "zoom_out",
                                                                                 "close"]},
                                             "place": {**text, "maxLength": 60}}, ["action"]),
                 Tier.JUST_DO, self._map_view),
            Tool("show_on_board", "Put working on the board in Jarvis's window, so the user can see it while you "
                 "explain: a title, steps (each a line of text and/or a formula in LaTeX) and up to 3 graphs of "
                 "y = f(x) (maths like check_maths writes it, e.g. exp(-x^2/2)/sqrt(2 pi)). Use it whenever "
                 "formulas, derivations or graphs help.",
                 _obj({"title": {**text, "maxLength": 120},
                       "steps": {"type": "array", "maxItems": 12, "items": _obj(
                           {"text": {"type": "string", "maxLength": 400}, "math": {"type": "string", "maxLength": 400}},
                           [])},
                       "graphs": {"type": "array", "maxItems": 3, "items": _obj(
                           {"expression": {**text, "maxLength": 200}, "variable": {"type": "string",
                                                                                  "pattern": "^[A-Za-z]$"},
                            "from": {"type": "number", "minimum": -1e6, "maximum": 1e6},
                            "to": {"type": "number", "minimum": -1e6, "maximum": 1e6},
                            "label": {**text, "maxLength": 60}}, ["expression"])}},
                      ["title"]), Tier.JUST_DO, self._show_on_board),
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
