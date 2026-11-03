"""The whole world's weather, now and for the next two days: every country's capital, and the seas between.

    ww = WorldWeather(cache=folder)
    world = ww.get()                         # every 3 hours from this hour, for 48 hours
    lines = world_for_the_model(world, focus="India")

Open-Meteo (open-meteo.com, free, no key) answers for many places in one request. Each place costs one
of the free calls (10,000 a day, 600 a minute), so the world is kept to about 450: the capitals of all
244 countries and territories (world_countries.json, from GeoNames), and a 15-degree grid over the seas
and empty land (points more than 600 km from any capital). An answer is kept on disk for an hour, so
opening the map again costs nothing. The map (world_weather_map.py) fills in between the points.
"""

from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

from .fetch import FetchError, Get, get_text, url_with
from .weather import CODES, FORECAST, WeatherError

COUNTRIES_FILE = Path(__file__).with_name("world_countries.json")
# Open-Meteo's names, and the short names the map uses
VARIABLES = {"temperature_2m": "t", "relative_humidity_2m": "rh", "precipitation": "rain", "weather_code": "code",
             "cloud_cover": "cloud", "pressure_msl": "p", "wind_speed_10m": "wind", "wind_direction_10m": "dir",
             "wind_gusts_10m": "gust"}
STEP_H, HOURS = 3, 48                    # a picture every 3 hours, for 48 hours: 17 of them
GRID_DEG, NEAR_KM = 15, 600              # the seas' grid, and how far from a capital a grid point must be
CHUNK = 100                              # places per request (the address stays short)
MAX_AGE_S = 3600
CONTINENTS = {"AF": "Africa", "AS": "Asia", "EU": "Europe", "NA": "North America", "SA": "South America",
              "OC": "Oceania", "AN": "Antarctica"}
COMPASS = ("north", "north-northeast", "northeast", "east-northeast", "east", "east-southeast", "southeast",
           "south-southeast", "south", "south-southwest", "southwest", "west-southwest", "west",
           "west-northwest", "northwest", "north-northwest")


@dataclass(frozen=True)
class Sample:
    lat: float
    lon: float
    country: str = ""                    # "" for a point of the seas' grid
    iso: str = ""
    capital: str = ""
    continent: str = ""
    population: int = 0


@dataclass
class World:
    fetched: datetime
    times: list[str]                     # UTC, "2026-11-03T09:00"
    samples: list[Sample]
    values: dict[str, list[list[float | None]]]   # short name ("t", "wind"...) -> each sample's values in time

    def value(self, name: str, i: int, step: int = 0) -> float | None:
        row = self.values.get(name, [])
        return row[i][step] if i < len(row) and step < len(row[i]) else None

    def country(self, name: str) -> int | None:
        """The index of a country's capital, by the country's name (any case) or its two-letter code."""
        key = name.strip().lower()
        return next((i for i, s in enumerate(self.samples) if s.country and
                     key in (s.country.lower(), s.iso.lower())), None)


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(min(1.0, math.sqrt(h)))


@cache
def countries() -> tuple[Sample, ...]:
    rows = json.loads(COUNTRIES_FILE.read_text(encoding="utf-8"))["rows"]
    return tuple(Sample(lat, lon, name, iso, capital, cont, pop) for name, iso, capital, lat, lon, cont, pop in rows)


@cache
def samples() -> tuple[Sample, ...]:
    """The capitals, then the grid points that are far from all of them."""
    caps = countries()
    grid = [Sample(float(lat), float(lon)) for lat in range(-60, 76, GRID_DEG) for lon in range(-180, 180, GRID_DEG)]
    far = [g for g in grid if all(_km((g.lat, g.lon), (c.lat, c.lon)) > NEAR_KM for c in caps)]
    return caps + tuple(far)


def compass(degrees: float | None) -> str:
    return "" if degrees is None else COMPASS[round(degrees / 22.5) % 16]


class WorldWeather:
    def __init__(self, get: Get = get_text, cache_dir: Path | None = None,
                 now=lambda: datetime.now(UTC), max_age_s: float = MAX_AGE_S):
        self.get, self.cache_dir, self.now, self.max_age_s = get, cache_dir, now, max_age_s

    def get_world(self) -> World:
        cached = self._cached()
        if cached is not None:
            return cached
        points = list(samples())
        chunks = [points[i:i + CHUNK] for i in range(0, len(points), CHUNK)]
        with ThreadPoolExecutor(max_workers=3) as pool:
            answers = list(pool.map(self._ask, chunks))
        items = [item for answer in answers for item in answer]
        if len(items) != len(points):
            raise WeatherError(f"asked for {len(points)} places, got {len(items)}")
        world = parse_world(items, points, self.now())
        self._save(world)
        return world

    def _ask(self, chunk: list[Sample]) -> list[dict]:
        url = url_with(FORECAST, {
            "latitude": ",".join(f"{s.lat:.2f}" for s in chunk), "longitude": ",".join(f"{s.lon:.2f}" for s in chunk),
            "hourly": ",".join(VARIABLES), "forecast_hours": HOURS + 1, "wind_speed_unit": "kmh"})
        try:
            data = json.loads(self.get(url))
        except (FetchError, ValueError) as exc:
            raise WeatherError(str(exc)[:160]) from None
        if isinstance(data, dict) and data.get("error"):
            raise WeatherError(str(data.get("reason", "Open-Meteo said no"))[:160])
        return data if isinstance(data, list) else [data]

    # ---- the hour's copy on disk ------------------------------------------------------------------
    def _path(self) -> Path | None:
        return self.cache_dir / "world-weather.json" if self.cache_dir else None

    def _cached(self) -> World | None:
        path = self._path()
        if path is None or not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(raw["fetched"])
            if not 0 <= (self.now() - fetched).total_seconds() <= self.max_age_s or raw["n"] != len(samples()):
                return None
            return World(fetched, raw["times"], list(samples()), raw["values"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _save(self, world: World) -> None:
        path = self._path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"fetched": world.fetched.isoformat(), "n": len(world.samples),
                                        "times": world.times, "values": world.values}), encoding="utf-8")
        except OSError:
            pass                                          # only a copy: the map works without it


def parse_world(items: list[dict], points: list[Sample], fetched: datetime) -> World:
    """Open-Meteo's answers (one per place, in order), every STEP_H hours."""
    first = (items[0].get("hourly") or {}).get("time") or [] if items else []
    times = first[::STEP_H][:HOURS // STEP_H + 1]
    values: dict[str, list[list[float | None]]] = {short: [] for short in VARIABLES.values()}
    for item in items:
        hourly = item.get("hourly") or {}
        at = {t: k for k, t in enumerate(hourly.get("time") or [])}
        for name, short in VARIABLES.items():
            col = hourly.get(name) or []
            row = []
            for t in times:
                k = at.get(t)
                v = col[k] if k is not None and k < len(col) else None
                row.append(None if v is None else (round(float(v), 1) if short in ("t", "rain", "p") else round(float(v))))
            values[short].append(row)
    return World(fetched, times, list(points), values)


# ---- for the language model ----------------------------------------------------------------------
def _line(world: World, i: int, step: int = 0) -> str:
    s = world.samples[i]
    v = {k: world.value(k, i, step) for k in VARIABLES.values()}
    bits = [f"{v['t']:.0f} °C" if v["t"] is not None else "?", CODES.get(int(v["code"] or 0), "")]
    if v["cloud"] is not None:
        bits.append(f"cloud {v['cloud']:.0f}%")
    if v["rain"]:
        bits.append(f"rain {v['rain']:.1f} mm in the hour")
    if v["wind"] is not None:
        bits.append(f"wind {v['wind']:.0f} km/h from the {compass(v['dir'])}, gusts {v['gust'] or 0:.0f}")
    if v["rh"] is not None:
        bits.append(f"humidity {v['rh']:.0f}%")
    if v["p"] is not None:
        bits.append(f"pressure {v['p']:.0f} hPa")
    return f"{s.country} ({s.capital}): " + ", ".join(b for b in bits if b)


def _top(world: World, name: str, n: int = 5, low: bool = False, at_least: float | None = None) -> list[int]:
    caps = [i for i, s in enumerate(world.samples) if s.country and world.value(name, i) is not None]
    if at_least is not None:
        caps = [i for i in caps if world.value(name, i) >= at_least]
    return sorted(caps, key=lambda i: world.value(name, i), reverse=not low)[:n]


def world_for_the_model(world: World, focus: str = "") -> list[str]:
    when = world.times[0].replace("T", " ") + " UTC" if world.times else "now"
    out = [(f"World weather from Open-Meteo for {when}, measured at each country's capital (the map shows the "
            "rest, and the next 48 hours):")]
    i = world.country(focus) if focus else None
    if i is not None:
        out.append("Asked about: " + _line(world, i))
        temps = [t for t in world.values["t"][i] if t is not None]
        rain = sum(r or 0 for r in world.values["rain"][i]) * STEP_H    # 3-hourly samples of hourly rain
        if temps:
            out.append(f"  Next 48 hours there: {min(temps):.0f} to {max(temps):.0f} °C, about {rain:.0f} mm "
                       "of rain in all (rough: from 3-hourly samples).")
    sections = (("Hottest", "t", False, None), ("Coldest", "t", True, None),
                ("Raining hardest", "rain", False, 0.5), ("Strongest gusts", "gust", False, None))
    for title, name, low, at_least in sections:
        picked = _top(world, name, low=low, at_least=at_least)
        if picked:
            out.append(f"{title}: " + "; ".join(_line(world, k).split(":")[0] + " " + _short(world, name, k)
                                                 for k in picked))
    out.append("Each country is one point at its capital, so say 'in the capital'; the country's other parts "
               "can differ. Official warnings stay with each country's weather service.")
    return out


def _short(world: World, name: str, i: int) -> str:
    v = world.value(name, i)
    return {"t": f"{v:.0f} °C", "rain": f"{v:.1f} mm/h", "gust": f"{v:.0f} km/h"}.get(name, str(v))


__all__ = ["CONTINENTS", "Sample", "World", "WorldWeather", "compass", "countries", "parse_world", "samples",
           "world_for_the_model"]
