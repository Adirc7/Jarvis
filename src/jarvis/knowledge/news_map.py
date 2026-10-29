"""The world news map: the latest stories on the countries they're about, coloured by theme.

    path = save_map(stories, folder)     # an HTML page in Jarvis's folder; open it in the browser

Colours and look follow Adhi's UI concept (UI/jarvis-future-complete-ui.html).
The page draws with Leaflet and OpenStreetMap tiles, so it needs the internet
like the news itself. Every headline links to its source. Stories that name
no country are listed beside the map.
"""

from __future__ import annotations

import html
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from .news import Story
from .places import where

THEME_COLOURS = {"technology": "#4de1ff", "politics": "#ffb43b", "military": "#ff766f", "space": "#b48cff",
                 "business": "#64efb7", "sport": "#8fa7ba", "other": "#eaf5ff"}


def map_data(stories: list[Story], now: datetime) -> tuple[list[dict], list[dict]]:
    """Markers (one per country, with its stories) and the stories that name no country."""
    by_country: dict[str, list[dict]] = defaultdict(list)
    loose = []
    for s in stories:
        item = {"title": s.title, "url": s.url, "source": s.source, "age": s.age(now), "theme": s.theme}
        placed = [p for p in s.places if where(p)]
        for p in placed:
            by_country[p].append(item)
        if not placed:
            loose.append(item)
    markers = []
    for country, items in sorted(by_country.items(), key=lambda kv: -len(kv[1])):
        lat, lon = where(country)
        themes = defaultdict(int)
        for it in items:
            themes[it["theme"]] += 1
        main = max(themes, key=lambda t: themes[t])
        markers.append({"country": country, "lat": lat, "lon": lon, "count": len(items),
                        "colour": THEME_COLOURS.get(main, THEME_COLOURS["other"]), "stories": items})
    return markers, loose


def page(stories: list[Story], title: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    markers, loose = map_data(stories, now)
    data = json.dumps({"markers": markers, "loose": loose, "colours": THEME_COLOURS},
                      ensure_ascii=False).replace("</", "<\\/")
    heading = html.escape(title)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{heading}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root {{ --bg:#03070d; --panel:#091522; --text:#eaf5ff; --muted:#8fa7ba; --cyan:#4de1ff; --amber:#ffb43b; }}
html, body {{ margin:0; height:100%; background:var(--bg); color:var(--text); font-family:"Segoe UI", system-ui, sans-serif; }}
main {{ display:grid; grid-template-columns:minmax(0,1fr) 340px; height:100vh; }}
#map {{ height:100%; background:#02060b; }}
aside {{ background:var(--panel); padding:16px; overflow:auto; border-left:1px solid #12314a; }}
h1 {{ font-size:18px; font-weight:500; margin:0 0 4px; color:var(--cyan); }}
.when {{ color:var(--muted); font-size:12px; margin-bottom:12px; }}
.legend span {{ display:inline-flex; align-items:center; gap:6px; margin:0 10px 6px 0; font-size:12px; color:var(--muted); }}
.dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
.story {{ margin:10px 0; font-size:13px; line-height:1.4; }}
.story a {{ color:var(--text); text-decoration:none; }} .story a:hover {{ color:var(--cyan); }}
.meta {{ color:var(--muted); font-size:11px; }}
.leaflet-popup-content-wrapper, .leaflet-popup-tip {{ background:var(--panel); color:var(--text); }}
.leaflet-popup-content a {{ color:var(--cyan); }}
@media (max-width: 800px) {{ main {{ grid-template-columns:1fr; grid-template-rows:60vh auto; }} }}
</style></head>
<body><main><div id="map"></div>
<aside><h1>{heading}</h1><div class="when">Jarvis, {now:%Y-%m-%d %H:%M} UTC. Headlines link to their sources.</div>
<div class="legend" id="legend"></div><div id="list"></div></aside></main>
<script>
const DATA = {data};
const map = L.map('map', {{ worldCopyJump: true }}).setView([20, 30], 2);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '&copy; OpenStreetMap contributors &copy; CARTO', maxZoom: 8 }}).addTo(map);
const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const storyHtml = s => `<div class="story"><span class="dot" style="background:${{DATA.colours[s.theme] || '#eaf5ff'}}"></span>
  <a href="${{esc(s.url)}}" target="_blank" rel="noopener">${{esc(s.title)}}</a>
  <div class="meta">${{esc(s.source)}} · ${{esc(s.age)}} · ${{esc(s.theme)}}</div></div>`;
for (const m of DATA.markers) {{
  L.circleMarker([m.lat, m.lon], {{ radius: 6 + Math.min(14, m.count * 3), color: m.colour, fillColor: m.colour,
    fillOpacity: 0.45, weight: 2 }}).addTo(map)
   .bindPopup(`<b>${{esc(m.country)}}</b> (${{m.count}})` + m.stories.map(storyHtml).join(''), {{ maxWidth: 320 }});
}}
document.getElementById('legend').innerHTML = Object.entries(DATA.colours)
  .map(([t, c]) => `<span><span class="dot" style="background:${{c}}"></span>${{esc(t)}}</span>`).join('');
const list = document.getElementById('list');
list.innerHTML = DATA.markers.map(m => `<div class="meta" style="margin-top:12px">${{esc(m.country)}}</div>` +
  m.stories.map(storyHtml).join('')).join('') +
  (DATA.loose.length ? '<div class="meta" style="margin-top:12px">No country named</div>' +
   DATA.loose.map(storyHtml).join('') : '');
</script></body></html>
"""


def save_map(stories: list[Story], folder: Path, title: str = "World news", now: datetime | None = None) -> Path:
    now = now or datetime.now(UTC)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"news-map {now:%Y-%m-%d %H%M}.html"
    path.write_text(page(stories, title, now), encoding="utf-8")
    return path
