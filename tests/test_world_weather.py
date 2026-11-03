"""The world weather map: every capital and the seas, Open-Meteo asked in chunks and kept for an hour,
the page, and the tools (world, continent and country maps; switching a layer by voice)."""

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from jarvis.knowledge.weather import Weather, WeatherError, parse_gdacs
from jarvis.knowledge.world_weather import (
    CHUNK,
    NEAR_KM,
    WorldWeather,
    _km,
    countries,
    samples,
    world_for_the_model,
)
from jarvis.knowledge.world_weather_map import page, save_world_map
from jarvis.tools.info import InfoTools

NOW = datetime(2026, 11, 3, 9, 30, tzinfo=UTC)
GDACS = """<?xml version="1.0"?><rss xmlns:gdacs="http://www.gdacs.org" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#">
<channel><item><link>https://www.gdacs.org/report.aspx?eventid=1</link><gdacs:eventtype>TC</gdacs:eventtype>
<gdacs:alertlevel>Orange</gdacs:alertlevel><gdacs:eventname>&lt;script&gt;x&lt;/script&gt;</gdacs:eventname>
<gdacs:country>India</gdacs:country><gdacs:iscurrent>true</gdacs:iscurrent>
<geo:Point><geo:lat>13.0</geo:lat><geo:long>86.0</geo:long></geo:Point></item></channel></rss>"""


def answer(url: str) -> str:
    """Open-Meteo for many places: warm near the equator, cold near the poles, windy at 50 degrees."""
    q = parse_qs(urlsplit(url).query)
    lats = [float(x) for x in q["latitude"][0].split(",")]
    lons = [float(x) for x in q["longitude"][0].split(",")]
    hours = int(q["forecast_hours"][0])
    start = NOW.replace(minute=0)
    times = [(start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(hours)]
    out = []
    for lat, lon in zip(lats, lons, strict=True):
        wind = 10 + 30 * math.exp(-((abs(lat) - 50) ** 2) / 50)
        out.append({"latitude": lat, "longitude": lon, "hourly": {
            "time": times, "temperature_2m": [30 - 0.6 * abs(lat) + h * 0.01 for h in range(hours)],
            "relative_humidity_2m": [70] * hours, "precipitation": [2.5 if abs(lon - 80) < 5 else 0] * hours,
            "weather_code": [63 if abs(lon - 80) < 5 else 1] * hours, "cloud_cover": [40] * hours,
            "pressure_msl": [1010.04] * hours, "wind_speed_10m": [wind] * hours,
            "wind_direction_10m": [270] * hours, "wind_gusts_10m": [wind * 1.6] * hours}})
    return json.dumps(out)


class Web:
    def __init__(self, world=answer):
        self.asked, self.world = [], world

    def __call__(self, url):
        self.asked.append(url)
        if "gdacs.org" in url:
            return GDACS
        if "hourly=temperature_2m" in url:
            return self.world(url)
        if "api.open-meteo.com" in url:           # Sri Lanka's towns map: one day of each town
            n = len(parse_qs(urlsplit(url).query)["latitude"][0].split(","))
            return json.dumps([{"daily": {"time": ["2026-11-03"], "weather_code": [2], "temperature_2m_max": [31],
                                          "temperature_2m_min": [24], "precipitation_sum": [1.0]}}] * n)
        if "geocoding-api" in url:
            return json.dumps({"results": [{"name": "Kaduwela", "country": "Sri Lanka", "latitude": 6.93,
                                            "longitude": 79.98, "feature_code": "PPL"}]})
        from jarvis.knowledge.fetch import FetchError
        raise FetchError("offline")


def test_every_country_and_the_seas_within_a_minutes_free_calls():
    caps, pts = countries(), samples()
    names = {c.country for c in caps}
    assert len(caps) > 230 and {"Sri Lanka", "India", "Brazil", "Iceland", "Fiji"} <= names
    assert len(pts) < 600                                          # Open-Meteo's free calls in a minute
    sea = [p for p in pts if not p.country]
    assert len(sea) > 100 and all(_km((s.lat, s.lon), (c.lat, c.lon)) > NEAR_KM for s in sea[:40] for c in caps)


def test_the_world_is_asked_in_chunks_every_three_hours_and_kept_for_an_hour(tmp_path):
    web, clock = Web(), [NOW]
    ww = WorldWeather(get=web, cache_dir=tmp_path, now=lambda: clock[0])
    world = ww.get_world()
    asked = [u for u in web.asked if "hourly=" in u]
    assert len(asked) == math.ceil(len(samples()) / CHUNK)
    q = parse_qs(urlsplit(asked[0]).query)
    assert q["forecast_hours"] == ["49"] and "wind_direction_10m" in q["hourly"][0]
    assert len(q["latitude"][0].split(",")) == CHUNK
    assert world.times[:2] == ["2026-11-03T09:00", "2026-11-03T12:00"] and len(world.times) == 17
    lk = world.country("sri lanka")
    assert world.samples[lk].capital == "Colombo" and world.value("rain", lk) == 2.5 and world.value("p", lk) == 1010.0
    assert world.country("LK") == lk and world.country("Atlantis") is None
    clock[0] = NOW + timedelta(minutes=50)
    again = ww.get_world()                                        # from the disk: no new requests
    assert len([u for u in web.asked if "hourly=" in u]) == len(asked) and again.values == world.values
    clock[0] = NOW + timedelta(minutes=61)
    ww.get_world()
    assert len([u for u in web.asked if "hourly=" in u]) == 2 * len(asked)


def test_a_refusal_or_a_short_answer_is_an_error_not_a_made_up_world(tmp_path):
    with pytest.raises(WeatherError, match="limit"):
        WorldWeather(get=Web(lambda u: json.dumps({"error": True, "reason": "Daily API request limit exceeded"})),
                     now=lambda: NOW).get_world()
    with pytest.raises(WeatherError, match="asked for"):
        WorldWeather(get=Web(lambda u: json.dumps(json.loads(answer(u))[:3])), now=lambda: NOW).get_world()


def test_the_model_hears_the_country_asked_about_and_the_extremes():
    world = WorldWeather(get=Web(), now=lambda: NOW).get_world()
    lines = world_for_the_model(world, focus="India")
    text = "\n".join(lines)
    assert "Asked about: India (New Delhi):" in text and "wind" in text and "from the west" in text
    assert "Hottest:" in text and "Coldest:" in text and "Raining hardest:" in text and "capital" in text


def test_the_page_carries_the_numbers_and_escapes_what_it_shows(tmp_path):
    world = WorldWeather(get=Web(), now=lambda: NOW).get_world()
    html = page(world, parse_gdacs(GDACS), "Weather: <India>", NOW, focus=world.country("India"), layer="wind")
    assert "<script>x</script>" not in html and "&lt;India&gt;" in html
    data = json.loads(html.split("const DATA = ", 1)[1].split(";\n", 1)[0])
    assert data["layer"] == "wind" and data["focus"] == world.country("India") and len(data["times"]) == 17
    assert len(data["samples"]) == len(world.samples) and data["alerts"][0]["kind"] == "tropical cyclone"
    assert "window.jarvisLayer" in html and "gibs.earthdata.nasa.gov/wms/epsg3857" in html
    assert "m.action === 'layer'" in html                         # the window's voice moves reach it
    assert "panelToggle(map);" in html and "main.full" in html      # the side panel hides for a bigger map
    path = save_world_map(world, [], tmp_path, now=NOW)
    assert path.name.startswith("weather-map ") and path.name.endswith(" world.html")   # Jarvis's window finds it


def test_world_continent_and_country_maps_and_the_towns_map_for_sri_lanka(tmp_path):
    opened, shown = [], []
    info = InfoTools(tmp_path / "Jarvis", opener=opened.append, now=lambda: NOW,
                     screen=lambda kind, data: shown.append((kind, data)) or True,
                     weather=Weather(get=Web()))
    out = info.call("show_weather_map", '{"area": "world"}')
    assert out.status == "done" and opened[-1].endswith("world.html")
    text = out.result.data["for_model"]
    assert "World weather from Open-Meteo" in text and "Orange alert" in text and "clouds, rain, wind" in text
    out = info.call("show_weather_map", '{"area": "USA", "layer": "wind"}')
    page_text = Path(out.result.data["path"]).read_text(encoding="utf-8")
    assert '"layer":"wind"' in page_text and "Asked about: United States (Washington)" in out.result.data["for_model"]
    assert info.call("show_weather_map", '{"area": "Asia"}').status == "done"
    before = len(opened)
    out = info.call("show_weather_map", '{"area": "Sri Lanka"}')
    assert out.status == "done" and not opened[before].endswith("world.html") and "Wettest today" in out.result.data["for_model"]
    out = info.call("map_view", '{"action": "layer", "layer": "wind"}')
    assert out.result.summary == "Showing the wind." and shown[-1] == ("map_cmd", {"action": "layer", "layer": "wind"})
    assert info.call("map_view", '{"action": "layer"}').status == "failed"


def test_offline_the_world_map_says_so(tmp_path):
    from jarvis.knowledge.fetch import FetchError

    def offline(url):
        raise FetchError("offline")
    info = InfoTools(tmp_path / "Jarvis", opener=lambda u: None, now=lambda: NOW, weather=Weather(get=offline))
    out = info.call("show_weather_map", '{"area": "world"}')
    assert out.status == "failed" and "don't guess" in out.result.data["for_model"]


def test_the_window_and_the_explorer_can_hide_their_side_columns():
    from jarvis.ui.server import EXPLORE_JS, PAGE
    window = PAGE.read_text(encoding="utf-8")
    assert 'id="widePanel"' in window and 'id="wideTop"' in window and "body.wide main > aside" in window
    assert 'id="panelCap"' in window                                # the latest line shows under a wide panel
    assert "jarvisExploreFull" in EXPLORE_JS.read_text(encoding="utf-8")
