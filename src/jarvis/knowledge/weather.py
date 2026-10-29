"""Weather: forecasts for any place, the usual rain for these dates, and storm and flood alerts.

    w = Weather()
    place = w.find("Kaduwela")                      # Open-Meteo's place search (GeoNames), Sri Lanka first
    fc = w.forecast(place, days=7)                  # now, the next 24 h of rain, and day by day
    usual = w.usual_rain(place, fc.days)            # the same dates over the last 10 years (ERA5)
    alerts = w.alerts(near=place)                   # GDACS: cyclones, floods, earthquakes... nearby

Open-Meteo (open-meteo.com, free, no key) blends national weather services'
models; its archive gives the last decades from the ERA5 reanalysis, which is
how Jarvis can say "about twice the usual rain for this week". GDACS
(gdacs.org, the UN and EU's alert system) lists current cyclones, floods,
earthquakes, volcanoes, droughts and wildfires worldwide, not tornadoes.
Jarvis reads the numbers out and gives his view of what they mean; official
warnings stay with the Department of Meteorology and the DMC.
"""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from .fetch import FetchError, Get, get_text, url_with
from .places import countries_in

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
GDACS_RSS = "https://www.gdacs.org/xml/rss.xml"

DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
         "precipitation_hours,wind_speed_10m_max,wind_gusts_10m_max,uv_index_max")
CURRENT = ("temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,cloud_cover,"
           "wind_speed_10m,wind_gusts_10m")
HOURLY = "precipitation_probability,precipitation"

# WMO weather codes (Open-Meteo's weather_code).
CODES = {0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
         51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
         61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
         71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light showers", 81: "showers",
         82: "violent showers", 85: "snow showers", 86: "heavy snow showers", 95: "thunderstorms",
         96: "thunderstorms with hail", 99: "thunderstorms with heavy hail"}
EVENT_TYPES = {"TC": "tropical cyclone", "FL": "flood", "EQ": "earthquake", "VO": "volcano", "DR": "drought",
               "WF": "wildfire"}
LEVELS = {"red": 3, "orange": 2, "green": 1}

# Sri Lanka's four seasons (Department of Meteorology), as background for Jarvis's view.
SRI_LANKA_SEASONS = (
    ((12, 1, 2), ("northeast monsoon (December to February): the rain falls mainly on the north, the east and the "
                  "eastern slopes of the hills; the west and south are drier")),
    ((3, 4), ("first inter-monsoon (March and April): hot, with afternoon and evening thunderstorms, mostly in the "
              "southwest and the hills")),
    ((5, 6, 7, 8, 9), ("southwest monsoon (May to September): rain on the western and southern coasts and the "
                       "western slopes of the hills (Colombo, Ratnapura, Galle); the north and east stay dry and "
                       "windy")),
    ((10, 11), ("second inter-monsoon (October and November): thunderstorms across the island, mostly afternoons "
                "and evenings; depressions and cyclones can form in the Bay of Bengal; the main flood and "
                "landslide season")),
)
# Points for the Sri Lanka weather map: the main towns of each part of the island.
SRI_LANKA_TOWNS = {
    "Colombo": (6.9271, 79.8612), "Kaduwela": (6.9333, 79.9833), "Kandy": (7.2906, 80.6337),
    "Galle": (6.0535, 80.2210), "Jaffna": (9.6615, 80.0255), "Trincomalee": (8.5874, 81.2152),
    "Batticaloa": (7.7310, 81.6747), "Anuradhapura": (8.3114, 80.4037), "Kurunegala": (7.4863, 80.3647),
    "Ratnapura": (6.6828, 80.3992), "Nuwara Eliya": (6.9497, 80.7891), "Badulla": (6.9934, 81.0550),
    "Hambantota": (6.1241, 81.1185), "Puttalam": (8.0362, 79.8283), "Mannar": (8.9810, 79.9044),
    "Vavuniya": (8.7514, 80.4971),
}


class WeatherError(Exception):
    """The weather service couldn't be reached or didn't answer sensibly."""


@dataclass
class Place:
    name: str
    lat: float
    lon: float
    country: str = ""
    region: str = ""                     # province / state, district
    kind: str = ""                       # GeoNames feature code: PPL (a town), PCLI (a country), ...

    def label(self) -> str:
        parts = [self.name] + [p for p in (self.region, self.country) if p and p != self.name]
        return ", ".join(dict.fromkeys(parts))


@dataclass
class Day:
    date: date
    code: int
    t_max: float | None
    t_min: float | None
    rain_mm: float | None
    rain_chance: int | None
    rain_hours: float | None
    wind_max: float | None
    gust_max: float | None
    uv: float | None

    def sky(self) -> str:
        return CODES.get(self.code, "unknown")


@dataclass
class Forecast:
    place: Place
    now: dict = field(default_factory=dict)              # Open-Meteo's "current" block
    days: list[Day] = field(default_factory=list)
    next_hours: list[tuple[str, int, float]] = field(default_factory=list)   # (HH:MM, chance %, mm)


@dataclass
class Usual:
    years: int
    rain_mm: float                       # the mean total for these dates
    wet_days: float                      # mean days with at least 1 mm
    driest: float
    wettest: float


@dataclass
class Alert:
    kind: str                            # "tropical cyclone", "flood", ...
    name: str
    level: str                           # Green, Orange, Red
    country: str
    lat: float | None
    lon: float | None
    since: str
    severity: str
    url: str
    km_away: float | None = None

    def rank(self) -> int:
        return LEVELS.get(self.level.lower(), 0)


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def season(place: Place, when: date) -> str:
    """Sri Lanka's monsoon season at this date, as background (other countries: "")."""
    if place.country != "Sri Lanka" and "Sri Lanka" not in countries_in(place.label()):
        return ""
    return next(text for months, text in SRI_LANKA_SEASONS if when.month in months)


def _days(daily: dict) -> list[Day]:
    def col(name, i):
        values = daily.get(name) or []
        return values[i] if i < len(values) else None
    out = []
    for i, day in enumerate(daily.get("time") or []):
        try:
            when = date.fromisoformat(day)
        except (TypeError, ValueError):
            continue
        out.append(Day(when, int(col("weather_code", i) or 0), col("temperature_2m_max", i),
                       col("temperature_2m_min", i), col("precipitation_sum", i),
                       col("precipitation_probability_max", i), col("precipitation_hours", i),
                       col("wind_speed_10m_max", i), col("wind_gusts_10m_max", i), col("uv_index_max", i)))
    return out


def parse_forecast(data: dict, place: Place) -> Forecast:
    fc = Forecast(place, data.get("current") or {}, _days(data.get("daily") or {}))
    hourly = data.get("hourly") or {}
    for t, chance, mm in zip(hourly.get("time") or [], hourly.get("precipitation_probability") or [],
                             hourly.get("precipitation") or [], strict=False):
        fc.next_hours.append((str(t)[-5:], int(chance or 0), float(mm or 0)))
    return fc


def parse_gdacs(text: str) -> list[Alert]:
    """GDACS's RSS: each item's fields by their local names (gdacs:eventtype, geo:lat, ...)."""
    try:
        root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError:
        return []
    alerts = []
    for item in root.iter("item"):
        f: dict[str, str] = {}
        for el in item.iter():
            name = el.tag.rsplit("}", 1)[-1].lower()
            if name not in f and (el.text or "").strip():
                f[name] = el.text.strip()
        if f.get("iscurrent", "true").lower() == "false":
            continue
        lat = lon = None
        try:
            if "lat" in f and "long" in f:
                lat, lon = float(f["lat"]), float(f["long"])
            elif "point" in f:
                lat, lon = (float(x) for x in f["point"].split()[:2])
        except ValueError:
            lat = lon = None
        kind = EVENT_TYPES.get(f.get("eventtype", "").upper(), f.get("eventtype", "event").lower())
        alerts.append(Alert(kind, f.get("eventname") or f.get("title", ""), f.get("alertlevel", ""),
                            f.get("country", ""), lat, lon, f.get("fromdate", ""),
                            re.sub(r"\s+", " ", f.get("severity", ""))[:160], f.get("link", "")))
    return alerts


class Weather:
    def __init__(self, get: Get = get_text, home_country: str = "Sri Lanka", today=lambda: datetime.now(UTC).date()):
        self.get, self.home, self.today = get, home_country, today
        self._usual: dict[tuple, Usual | None] = {}

    def _json(self, url: str):
        try:
            return json.loads(self.get(url))
        except (FetchError, ValueError) as exc:
            raise WeatherError(str(exc)[:160]) from None

    # ---- places ----------------------------------------------------------------------
    def find(self, name: str, country: str = "") -> Place | None:
        """The place the user means: in `country` if given; else a same-named place at home first."""
        name = re.sub(r"[^\w\s\-'.,]", " ", name or "").strip()[:60]
        if not name:
            return None
        if name.lower() in (t.lower() for t in SRI_LANKA_TOWNS) and country in ("", self.home):
            town = next(t for t in SRI_LANKA_TOWNS if t.lower() == name.lower())
            return Place(town, *SRI_LANKA_TOWNS[town], "Sri Lanka", kind="PPL")
        data = self._json(url_with(GEOCODE, {"name": name.split(",")[0].strip(), "count": 10, "language": "en",
                                             "format": "json"}))
        results = (data.get("results") or []) if isinstance(data, dict) else []
        if not results:
            return None
        wanted = countries_in(country)[0] if country and countries_in(country) else country

        def in_country(r, c):
            return bool(c) and (c in countries_in(r.get("country", "")) or c.lower() == r.get("country", "").lower())
        pick = next((r for r in results if in_country(r, wanted)), None) if wanted else None
        if pick is None and not wanted:
            pick = next((r for r in results if in_country(r, self.home)
                         and r.get("name", "").lower() == name.split(",")[0].strip().lower()), results[0])
        if pick is None:
            return None
        region = ", ".join(x for x in (pick.get("admin2"), pick.get("admin1")) if x)
        return Place(pick.get("name", name), float(pick["latitude"]), float(pick["longitude"]),
                     pick.get("country", ""), region, pick.get("feature_code", ""))

    # ---- forecasts -------------------------------------------------------------------
    def forecast(self, place: Place, days: int = 7) -> Forecast:
        data = self._json(url_with(FORECAST, {
            "latitude": f"{place.lat:.4f}", "longitude": f"{place.lon:.4f}", "current": CURRENT, "daily": DAILY,
            "hourly": HOURLY, "forecast_hours": 24, "forecast_days": max(1, min(int(days), 16)),
            "timezone": "auto"}))
        if not isinstance(data, dict) or "daily" not in data:
            raise WeatherError("no forecast in the answer")
        return parse_forecast(data, place)

    def forecasts(self, places: list[Place], days: int = 7) -> list[Forecast]:
        """Day-by-day forecasts for several places in one request (the map)."""
        if not places:
            return []
        data = self._json(url_with(FORECAST, {
            "latitude": ",".join(f"{p.lat:.4f}" for p in places),
            "longitude": ",".join(f"{p.lon:.4f}" for p in places), "daily": DAILY,
            "forecast_days": max(1, min(int(days), 16)), "timezone": "auto"}))
        items = data if isinstance(data, list) else [data]
        return [parse_forecast(d, p) for d, p in zip(items, places, strict=False) if isinstance(d, dict)]

    def usual_rain(self, place: Place, days: list[Day], years: int = 10) -> Usual | None:
        """The rain these same dates had in each of the last `years` years (ERA5), or None."""
        if not days:
            return None
        first, last = days[0].date, days[-1].date
        key = (round(place.lat, 2), round(place.lon, 2), first.strftime("%m%d"), last.strftime("%m%d"), years)
        if key in self._usual:
            return self._usual[key]
        end_year = self.today().year - 1
        try:
            data = self._json(url_with(ARCHIVE, {
                "latitude": f"{place.lat:.4f}", "longitude": f"{place.lon:.4f}", "daily": "precipitation_sum",
                "start_date": f"{end_year - years + 1}-01-01", "end_date": f"{end_year}-12-31",
                "timezone": "auto"}))
        except WeatherError:
            return None
        daily = (data.get("daily") or {}) if isinstance(data, dict) else {}
        by_day = dict(zip(daily.get("time") or [], daily.get("precipitation_sum") or [], strict=False))
        totals, wets = [], []
        for year in range(end_year - years + 1, end_year + 1):
            try:
                start = first.replace(year=year)
            except ValueError:                        # 29 February
                start = first.replace(year=year, day=28)
            span = [start + timedelta(days=i) for i in range((last - first).days + 1)]
            values = [by_day.get(d.isoformat()) for d in span]
            if values and all(v is not None for v in values):
                totals.append(sum(values))
                wets.append(sum(v >= 1 for v in values))
        result = Usual(len(totals), sum(totals) / len(totals), sum(wets) / len(wets), min(totals),
                       max(totals)) if totals else None
        self._usual[key] = result
        return result

    # ---- alerts ----------------------------------------------------------------------
    def alerts(self, country: str = "", near: Place | None = None, radius_km: float = 1200) -> list[Alert]:
        """Current GDACS events: in a country, near a place, or everywhere (worst first)."""
        try:
            found = parse_gdacs(self.get(GDACS_RSS))
        except FetchError as exc:
            raise WeatherError(str(exc)[:160]) from None
        wanted = countries_in(country)[0] if country and countries_in(country) else country
        keep = []
        for a in found:
            if near is not None and a.lat is not None:
                a.km_away = round(_km((near.lat, near.lon), (a.lat, a.lon)))
            if wanted and not (wanted in countries_in(a.country) or wanted.lower() in a.country.lower()):
                continue
            if near is not None and not wanted and (a.km_away is None or a.km_away > radius_km):
                continue
            keep.append(a)
        return sorted(keep, key=lambda a: (-a.rank(), a.km_away or 0))


# ---- for the model -----------------------------------------------------------------------
def _n(value, unit: str = "", digits: int = 0) -> str:
    return "?" if value is None else f"{value:.{digits}f}{unit}"


def forecast_for_the_model(fc: Forecast, usual: Usual | None, alerts: list[Alert], fetched: datetime) -> str:
    p = fc.place
    lines = [(f"Weather for {p.label()} ({p.lat:.2f}, {p.lon:.2f}), Open-Meteo forecast fetched "
              f"{fetched:%Y-%m-%d %H:%M} UTC (local dates):")]
    if p.kind.startswith("PCL"):
        lines.append("NOTE: this is one point near the middle of the country; weather differs across it. Say so, "
                     "and offer cities.")
    n = fc.now
    if n:
        lines.append(f"Now: {CODES.get(int(n.get('weather_code') or 0), 'unknown')}, "
                     f"{_n(n.get('temperature_2m'), ' C')} (feels {_n(n.get('apparent_temperature'), ' C')}), "
                     f"humidity {_n(n.get('relative_humidity_2m'), '%')}, cloud {_n(n.get('cloud_cover'), '%')}, "
                     f"wind {_n(n.get('wind_speed_10m'), ' km/h')} gusting {_n(n.get('wind_gusts_10m'), ' km/h')}, "
                     f"rain in the last hour {_n(n.get('precipitation'), ' mm', 1)}.")
    if fc.next_hours:
        wet = [h for h in fc.next_hours if h[1] >= 50 or h[2] >= 0.5]
        total = sum(h[2] for h in fc.next_hours)
        if wet:
            lines.append(f"Next 24 h: rain most likely {wet[0][0]}-{wet[-1][0]} (up to "
                         f"{max(h[1] for h in wet)}% chance), about {total:.1f} mm in all.")
        else:
            lines.append(f"Next 24 h: little rain expected (highest chance {max(h[1] for h in fc.next_hours)}%, "
                         f"{total:.1f} mm in all).")
    for d in fc.days:
        lines.append(f"{d.date:%a %d %b}: {d.sky()}, {_n(d.t_min)}-{_n(d.t_max, ' C')}, rain "
                     f"{_n(d.rain_mm, ' mm', 1)} ({_n(d.rain_chance, '%')} chance, {_n(d.rain_hours, ' h')}), "
                     f"wind up to {_n(d.wind_max, ' km/h')}, gusts {_n(d.gust_max, ' km/h')}, UV {_n(d.uv, '', 1)}")
    if usual is not None and fc.days:
        coming = sum(d.rain_mm or 0 for d in fc.days)
        ratio = f"{coming / usual.rain_mm:.1f} times" if usual.rain_mm >= 1 else "n/a"
        lines.append(f"Usual for these {len(fc.days)} dates (ERA5 reanalysis, last {usual.years} years): "
                     f"{usual.rain_mm:.0f} mm on average ({usual.driest:.0f}-{usual.wettest:.0f} mm), "
                     f"{usual.wet_days:.1f} wet days. Forecast total: {coming:.0f} mm ({ratio} the usual).")
    background = season(p, fc.days[0].date if fc.days else fetched.date())
    if background:
        lines.append(f"Season (background, not from the forecast): Sri Lanka's {background}.")
    lines += alerts_for_the_model(alerts, f"within about 1,200 km of {p.name}", header=False)
    return "\n".join(lines)


def alerts_for_the_model(alerts: list[Alert], where: str, header: bool = True) -> list[str]:
    lines = [f"GDACS alerts {where} (current events):"] if header else []
    if not alerts:
        lines.append(f"No current GDACS alerts {where} (cyclones, floods, earthquakes, volcanoes, droughts, "
                     "wildfires; GDACS doesn't track tornadoes or local thunderstorms).")
        return lines
    if not header:
        lines.append(f"GDACS alerts {where}:")
    for a in alerts[:6]:
        away = f", {a.km_away:,.0f} km away" if a.km_away is not None else ""
        lines.append(f"- {a.level or '?'} alert: {a.kind} {a.name} ({a.country or 'at sea'}{away}; since "
                     f"{a.since or '?'}){': ' + a.severity if a.severity else ''}")
    return lines
