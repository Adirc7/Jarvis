"""Weather: places, forecasts, the usual rain, GDACS alerts, the tools and the map, with a stand-in internet."""

import json
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from jarvis.knowledge.weather import (
    Place,
    Weather,
    forecast_for_the_model,
    parse_gdacs,
    season,
)
from jarvis.knowledge.weather_map import page
from jarvis.tools.info import InfoTools

NOW = datetime(2026, 10, 30, 6, 0, tzinfo=UTC)
TODAY = NOW.date()


def geo(*rows):
    return json.dumps({"results": [dict(zip(("name", "country", "latitude", "longitude", "admin1", "admin2",
                                              "feature_code"), r, strict=True)) for r in rows]})


FORECAST = json.dumps({
    "current": {"temperature_2m": 29.4, "apparent_temperature": 34.1, "relative_humidity_2m": 79,
                "precipitation": 0.0, "weather_code": 2, "cloud_cover": 55, "wind_speed_10m": 9.5,
                "wind_gusts_10m": 22.0},
    "hourly": {"time": [f"2026-10-30T{h:02d}:00" for h in range(11, 24)] + [f"2026-10-31T{h:02d}:00" for h in range(11)],
               "precipitation_probability": [10, 15, 30, 65, 80, 75, 55, 30, 20, 10] + [5] * 14,
               "precipitation": [0, 0, 0.2, 2.5, 6.0, 3.1, 0.8, 0.1, 0, 0] + [0] * 14},
    "daily": {"time": ["2026-10-30", "2026-10-31", "2026-11-01"], "weather_code": [95, 63, 2],
              "temperature_2m_max": [31.2, 29.8, 30.5], "temperature_2m_min": [24.1, 23.9, 24.4],
              "precipitation_sum": [12.7, 30.2, 1.1], "precipitation_probability_max": [80, 90, 25],
              "precipitation_hours": [4, 9, 1], "wind_speed_10m_max": [14, 18, 11],
              "wind_gusts_10m_max": [38, 47, 25], "uv_index_max": [9.1, 6.0, 10.2]}})


def archive(mm_per_day=2.0):
    days, values, d = [], [], date(2016, 1, 1)
    while d <= date(2025, 12, 31):
        days.append(d.isoformat())
        values.append(mm_per_day)
        d += timedelta(days=1)
    return json.dumps({"daily": {"time": days, "precipitation_sum": values}})


GDACS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:gdacs="http://www.gdacs.org" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#">
<channel><title>GDACS</title>
<item><title>Orange alert for tropical cyclone MONTHA</title><link>https://www.gdacs.org/report.aspx?eventid=1001</link>
<gdacs:eventtype>TC</gdacs:eventtype><gdacs:alertlevel>Orange</gdacs:alertlevel><gdacs:eventname>MONTHA-26</gdacs:eventname>
<gdacs:country>India, Sri Lanka</gdacs:country><gdacs:fromdate>Wed, 28 Oct 2026 00:00:00 GMT</gdacs:fromdate>
<gdacs:severity unit="km/h">Tropical Storm (maximum wind speed of 83 km/h)</gdacs:severity><gdacs:iscurrent>true</gdacs:iscurrent>
<geo:Point><geo:lat>13.0</geo:lat><geo:long>85.0</geo:long></geo:Point></item>
<item><title>Green earthquake in Japan</title><link>https://www.gdacs.org/report.aspx?eventid=1002</link>
<gdacs:eventtype>EQ</gdacs:eventtype><gdacs:alertlevel>Green</gdacs:alertlevel><gdacs:eventname>&lt;script&gt;x&lt;/script&gt;</gdacs:eventname>
<gdacs:country>Japan</gdacs:country><gdacs:iscurrent>true</gdacs:iscurrent>
<geo:Point><geo:lat>36.0</geo:lat><geo:long>140.0</geo:long></geo:Point></item>
<item><title>Old flood</title><gdacs:eventtype>FL</gdacs:eventtype><gdacs:alertlevel>Red</gdacs:alertlevel>
<gdacs:country>Sri Lanka</gdacs:country><gdacs:iscurrent>false</gdacs:iscurrent></item>
</channel></rss>"""


class Web:
    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def __call__(self, url):
        self.asked.append(url)
        for key, text in self.pages.items():
            if key in url:
                return text
        from jarvis.knowledge.fetch import FetchError
        raise FetchError("offline")


def web(**extra):
    return Web({"name=Malabe": geo(("Malabe", "Sri Lanka", 6.904, 79.958, "Western", "Colombo District", "PPL")),
                "name=Kelaniya": geo(("Kelaniya", "Brazil", -20.1, -44.9, "Minas Gerais", "", "PPL"),
                                     ("Kelaniya", "Sri Lanka", 6.955, 79.922, "Western", "Gampaha District", "PPL")),
                "name=Paris": geo(("Paris", "France", 48.85, 2.35, "Ile-de-France", "Paris", "PPLC"),
                                  ("Paris", "United States", 33.66, -95.55, "Texas", "Lamar", "PPLA2")),
                "name=India": geo(("India", "India", 22.0, 79.0, "", "", "PCLI")),
                "geocoding-api": "{}",                                 # no such place: no results
                "api.open-meteo.com/v1/forecast": FORECAST, "archive-api": archive(), "gdacs.org": GDACS, **extra})


def weather(w=None):
    return Weather(get=w or web(), today=lambda: TODAY)


def test_places_are_found_home_first():
    w = weather()
    assert w.find("Malabe").label() == "Malabe, Colombo District, Western, Sri Lanka"
    assert w.find("Kelaniya").country == "Sri Lanka"                  # a same-named place at home wins
    assert w.find("Paris").country == "France"                        # nothing at home: the best match
    assert w.find("Paris", "USA").country == "United States"          # the country asked for
    assert w.find("Kandy").country == "Sri Lanka"                      # Sri Lanka's main towns need no search
    assert w.find("Nowhere at all") is None and w.find("<>") is None


def test_the_forecast_reads_out_now_the_next_hours_and_the_days():
    w = weather()
    place = w.find("Malabe")
    fc = w.forecast(place, days=3)
    usual = w.usual_rain(place, fc.days)
    assert usual.years == 10 and usual.rain_mm == 6.0 and usual.wet_days == 3
    text = forecast_for_the_model(fc, usual, w.alerts(near=place), NOW)
    assert "Now: partly cloudy, 29 C (feels 34 C), humidity 79%" in text
    assert "Next 24 h: rain most likely 14:00-17:00 (up to 80% chance), about 12.7 mm in all." in text
    assert "Sat 31 Oct: rain, 24-30 C, rain 30.2 mm (90% chance, 9 h), wind up to 18 km/h, gusts 47 km/h" in text
    assert "Forecast total: 44 mm (7.3 times the usual)" in text
    assert "second inter-monsoon" in text                               # October in Sri Lanka
    assert "Orange alert: tropical cyclone MONTHA-26" in text and "km away" in text
    assert "Japan" not in text                                          # too far to matter


def test_alerts_are_current_worst_first_and_by_country():
    alerts = parse_gdacs(GDACS)
    assert [a.kind for a in alerts] == ["tropical cyclone", "earthquake"]   # the old flood is over
    w = weather()
    assert [a.name for a in w.alerts(country="Sri Lanka")] == ["MONTHA-26"]
    assert [a.level for a in w.alerts()] == ["Orange", "Green"]
    assert parse_gdacs("<html>no</html>") == []


def test_the_season_is_background_for_sri_lanka_only():
    lk, fr = Place("Colombo", 6.9, 79.9, "Sri Lanka"), Place("Paris", 48.9, 2.4, "France")
    assert season(lk, date(2026, 7, 1)).startswith("southwest monsoon")
    assert season(lk, date(2026, 1, 10)).startswith("northeast monsoon")
    assert season(fr, date(2026, 7, 1)) == ""


def test_the_weather_tools(tmp_path):
    opened = []
    info = InfoTools(tmp_path / "Jarvis", weather=weather(), opener=opened.append, now=lambda: NOW)
    out = info.call("get_weather", json.dumps({"places": ["Malabe", "Atlantis"], "days": 3}))
    data = out.result.data["for_model"]
    assert out.status == "claimed" and "Weather for Malabe" in data and "No place found called: Atlantis" in data
    assert info.call("get_weather", json.dumps({"places": ["a", "b", "c", "d", "e", "f", "g"]})).status == "refused"
    country = info.call("get_weather", '{"places": ["India"]}').result.data["for_model"]
    assert "one point near the middle of the country" in country
    out = info.call("show_weather_map", "{}")
    assert out.status == "done" and opened[0].startswith("file:") and "weather-map" in opened[0]
    assert "Wettest today" in out.result.data["for_model"]
    out = info.call("weather_alerts", '{"country": "Japan"}')
    assert "Green alert: earthquake" in out.result.data["for_model"]


def test_the_forecast_asks_for_what_it_needs():
    w = web()
    Weather(get=w, today=lambda: TODAY).forecast(Place("Colombo", 6.9271, 79.8612, "Sri Lanka"), days=40)
    q = parse_qs(urlsplit(w.asked[-1]).query)
    assert q["forecast_days"] == ["16"] and q["timezone"] == ["auto"] and "precipitation_sum" in q["daily"][0]


def test_offline_means_no_weather_not_made_up_weather(tmp_path):
    info = InfoTools(tmp_path / "Jarvis", weather=Weather(get=Web({}), today=lambda: TODAY), now=lambda: NOW)
    out = info.call("get_weather", '{"places": ["Malabe"]}')
    assert out.status == "failed" and "don't guess" in out.result.data["for_model"]


def test_the_weather_map_page_escapes_what_it_shows():
    w = weather()
    places = [w.find("Malabe"), w.find("Kelaniya")]
    forecasts = w.forecasts(places, 3)
    html = page(forecasts, parse_gdacs(GDACS), "Weather: <Sri Lanka>", NOW)
    assert "<script>x</script>" not in html and "&lt;Sri Lanka&gt;" in html
    data = json.loads(html.split("const DATA = ", 1)[1].split(";\nconst map", 1)[0])
    assert data["days"] == ["2026-10-30", "2026-10-31", "2026-11-01"] and data["places"][0]["days"][1]["rain"] == 30.2
    assert {a["kind"] for a in data["alerts"]} == {"tropical cyclone", "earthquake"}


async def test_jarvis_answers_from_the_forecast_with_its_view(settings, tmp_path):
    from test_knowledge import TwoStep

    from jarvis.agent.llm import FallbackLLM, Provider
    from jarvis.app import App
    from jarvis.telemetry import Telemetry
    info = InfoTools(tmp_path / "Jarvis", weather=weather(), opener=lambda u: None, now=lambda: NOW)
    model = TwoStep("get_weather", '{"places": ["Malabe"], "days": 3}',
                    ["Malabe: thunderstorms today, 13 mm likely. ", "My take: take an umbrella to SLIIT."])
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", model)]),
              out=lambda *a, **k: None, info=info)
    reply = await app.handle_text("will it rain in Malabe this week")
    assert reply.endswith("My take: take an umbrella to SLIIT.")
    system = model.requests[1]["messages"][0]["content"]
    assert "Weather for Malabe" in system and "Never invent a number" in system and "hotline 117" in system
    assert "tools" not in model.requests[1]


def test_a_storm_near_the_country_counts_not_only_one_filed_under_it(tmp_path):
    # 30 Oct, on the laptop: a Red-alert cyclone filed under India was in the Bay of Bengal,
    # and "any cyclones near Sri Lanka?" got "no current alerts ... none expected".
    arnab = GDACS.replace("</channel>", """<item><title>Red alert for tropical cyclone ARNAB</title>
<link>https://www.gdacs.org/report.aspx?eventid=1003</link><gdacs:eventtype>TC</gdacs:eventtype>
<gdacs:alertlevel>Red</gdacs:alertlevel><gdacs:eventname>ARNAB-26</gdacs:eventname><gdacs:country>India</gdacs:country>
<gdacs:iscurrent>true</gdacs:iscurrent><geo:Point><geo:lat>14.5</geo:lat><geo:long>84.5</geo:long></geo:Point></item>
</channel>""")
    info = InfoTools(tmp_path / "Jarvis", weather=weather(web(**{"gdacs.org": arnab})), now=lambda: NOW)
    text = info.call("weather_alerts", '{"country": "Sri Lanka"}').result.data["for_model"]
    assert text.index("Red alert: tropical cyclone ARNAB-26 (India") < text.index("Orange alert: tropical cyclone MONTHA")
    assert "say it first" in text and "never say none are expected" in text and "Japan" not in text
    near = info.call("weather_alerts", '{"place": "Malabe"}').result.data["for_model"]
    assert "ARNAB-26" in near and "within 1,200 km of Malabe" in near
