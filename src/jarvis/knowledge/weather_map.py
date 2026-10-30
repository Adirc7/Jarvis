"""The weather map: rain and temperature day by day for many places, current storm alerts, and rain radar.

    path = save_weather_map(forecasts, alerts, folder, "Sri Lanka weather")   # open it in the browser

Each place is a circle coloured by that day's rain (mm) and sized by its
chance; a slider moves through the days, so a monsoon's rain can be seen
moving across the island. GDACS alerts (cyclones, floods, earthquakes...) are
marked by alert level, linked to their reports. The radar layer is
RainViewer's latest frame, loaded by the page itself, where there is radar
coverage (not all of Sri Lanka has it). Same look as the news map.
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path

from . import map_tiles
from .weather import Alert, Forecast

RAIN_COLOURS = ((1, "#516476", "under 1 mm"), (5, "#4de1ff", "1-5 mm"), (20, "#3a8bff", "5-20 mm"),
                (50, "#b48cff", "20-50 mm"), (10_000, "#ff766f", "50 mm or more"))
LEVEL_COLOURS = {"red": "#ff4d4d", "orange": "#ffb43b", "green": "#64efb7"}


def map_data(forecasts: list[Forecast], alerts: list[Alert]) -> dict:
    days = [d.date.isoformat() for d in forecasts[0].days] if forecasts else []
    places = []
    for fc in forecasts:
        places.append({"name": fc.place.name, "lat": fc.place.lat, "lon": fc.place.lon, "days": [
            {"sky": d.sky(), "max": d.t_max, "min": d.t_min, "rain": d.rain_mm, "chance": d.rain_chance,
             "gust": d.gust_max} for d in fc.days]})
    marks = [{"kind": a.kind, "name": a.name, "level": a.level, "country": a.country, "lat": a.lat, "lon": a.lon,
              "since": a.since, "severity": a.severity, "url": a.url if a.url.startswith(("http://", "https://")) else ""}
             for a in alerts if a.lat is not None and a.lon is not None]
    return {"days": days, "places": places, "alerts": marks,
            "rain": [[limit, colour, label] for limit, colour, label in RAIN_COLOURS], "levels": LEVEL_COLOURS}


def page(forecasts: list[Forecast], alerts: list[Alert], title: str, now: datetime | None = None,
         centre: tuple[float, float] = (7.8, 80.7), zoom: int = 7) -> str:
    now = now or datetime.now(UTC)
    data = json.dumps(map_data(forecasts, alerts), ensure_ascii=False).replace("</", "<\\/")
    heading = html.escape(title)
    tiles_js, tiles_css = map_tiles.JS, map_tiles.CSS
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
h2 {{ font-size:12px; font-weight:500; letter-spacing:2px; color:var(--cyan); text-transform:uppercase; margin:16px 0 6px; }}
.when, .meta {{ color:var(--muted); font-size:12px; }}
.row {{ display:flex; justify-content:space-between; gap:8px; font-size:13px; padding:4px 0; border-bottom:1px solid #0e2235; }}
.legend span {{ display:inline-flex; align-items:center; gap:6px; margin:0 10px 6px 0; font-size:12px; color:var(--muted); }}
.dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
#day {{ width:100%; accent-color:var(--cyan); }} #dayName {{ font-size:15px; margin:6px 0; }}
button {{ background:#12314a; color:var(--text); border:1px solid #1c4766; border-radius:6px; padding:5px 10px; cursor:pointer; }}
.alert a {{ color:var(--text); text-decoration:none; }} .alert a:hover {{ color:var(--cyan); }}
.leaflet-popup-content-wrapper, .leaflet-popup-tip {{ background:var(--panel); color:var(--text); }}
.leaflet-popup-content a {{ color:var(--cyan); }}
.leaflet-tooltip.temp {{ background:transparent; border:0; box-shadow:none; padding:0 0 0 4px; color:var(--text);
                         font-size:11px; text-shadow:0 0 3px #000, 0 0 2px #000; }}
.leaflet-tooltip.temp:before {{ display:none; }}
.alert {{ cursor:pointer; }}
{tiles_css}@media (max-width: 800px) {{ main {{ grid-template-columns:1fr; grid-template-rows:60vh auto; }} }}
</style></head>
<body><main><div id="map"></div>
<aside><h1>{heading}</h1><div class="when">Jarvis, {now:%Y-%m-%d %H:%M} UTC. Open-Meteo forecast; alerts from GDACS.</div>
<div id="dayName"></div><input id="day" type="range" min="0" value="0" step="1">
<div class="legend" id="legend"></div>
<button id="radar">Show rain radar</button> <span class="meta" id="radarNote"></span>
<h2>Rain this day</h2><div id="list"></div>
<h2>Storm and disaster alerts</h2><div id="alerts"></div>
<p class="meta">Official warnings: Department of Meteorology (meteo.gov.lk) and the Disaster Management Centre (117).</p>
</aside></main>
<script>{tiles_js}
const DATA = {data};
const map = L.map('map').setView([{centre[0]}, {centre[1]}], {zoom});
addBaseLayers(map);
followJarvis(map);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const num = (v, u, d = 0) => v === null || v === undefined ? '?' : Number(v).toFixed(d) + u;
const rainColour = mm => (DATA.rain.find(([limit]) => (mm ?? 0) < limit) || DATA.rain[DATA.rain.length - 1])[1];
document.getElementById('legend').innerHTML = DATA.rain.map(([, c, label]) =>
  `<span><span class="dot" style="background:${{c}}"></span>${{esc(label)}}</span>`).join('');
const layer = L.layerGroup().addTo(map);
const slider = document.getElementById('day');
slider.max = Math.max(0, DATA.days.length - 1);
function show(i) {{
  layer.clearLayers();
  const day = DATA.days[i];
  document.getElementById('dayName').textContent = day ? new Date(day + 'T12:00:00').toDateString() : 'No forecast';
  const rows = [];
  for (const p of DATA.places) {{
    const d = p.days[i]; if (!d) continue;
    const c = rainColour(d.rain);
    L.circleMarker([p.lat, p.lon], {{ radius: 6 + (d.chance || 0) / 8, color: c, fillColor: c, fillOpacity: 0.55, weight: 2 }})
      .bindPopup(`<b>${{esc(p.name)}}</b><br>${{esc(d.sky)}}<br>${{num(d.min, '')}}-${{num(d.max, ' °C')}}<br>` +
                 `rain ${{num(d.rain, ' mm', 1)}} (${{num(d.chance, '%')}})<br>gusts ${{num(d.gust, ' km/h')}}`)
      .bindTooltip(`${{esc(p.name)}} ${{num(d.max, '°')}}`, {{ permanent: DATA.places.length <= 20, direction: 'right', className: 'temp' }})
      .addTo(layer);
    rows.push([d.rain ?? 0, `<div class="row"><span><span class="dot" style="background:${{c}}"></span> ${{esc(p.name)}}</span>` +
               `<span>${{num(d.rain, ' mm', 1)}} · ${{num(d.chance, '%')}} · ${{num(d.max, '°')}}</span></div>`]);
  }}
  document.getElementById('list').innerHTML = rows.sort((a, b) => b[0] - a[0]).map(r => r[1]).join('') ||
    '<div class="meta">No places.</div>';
}}
slider.addEventListener('input', () => show(Number(slider.value)));
show(0);
if (DATA.places.length > 1) map.fitBounds(DATA.places.map(p => [p.lat, p.lon]), {{ padding: [40, 40] }});
for (const a of DATA.alerts) {{
  const c = DATA.levels[String(a.level).toLowerCase()] || '#eaf5ff';
  L.circleMarker([a.lat, a.lon], {{ radius: 11, color: c, fillColor: c, fillOpacity: 0.25, weight: 3, dashArray: '4 3' }})
    .bindPopup(`<b>${{esc(a.level)}} alert: ${{esc(a.kind)}}</b><br>${{esc(a.name)}}<br>${{esc(a.country)}}<br>${{esc(a.severity)}}` +
               (a.url ? `<br><a href="${{esc(a.url)}}" target="_blank" rel="noopener">GDACS report</a>` : '')).addTo(map);
}}
const alertBox = document.getElementById('alerts');
alertBox.innerHTML = DATA.alerts.map((a, i) => `<div class="row alert" data-i="${{i}}"><span>` +
  (a.url ? `<a href="${{esc(a.url)}}" target="_blank" rel="noopener">${{esc(a.kind)}}: ${{esc(a.name)}}</a>` : `${{esc(a.kind)}}: ${{esc(a.name)}}`) +
  `<div class="meta">${{esc(a.country || 'at sea')}}${{a.since ? ' · since ' + esc(a.since) : ''}}</div></span>` +
  `<span style="color:${{DATA.levels[String(a.level).toLowerCase()] || '#eaf5ff'}}">${{esc(a.level)}}</span></div>`).join('') ||
  '<div class="meta">No current alerts in this area.</div>';
alertBox.addEventListener('click', e => {{                 // a row (not its link) shows the alert on the map
  const row = e.target.closest('.row'); if (!row || e.target.closest('a')) return;
  const a = DATA.alerts[Number(row.dataset.i)]; map.flyTo([a.lat, a.lon], 5);
}});
let radar = null;
document.getElementById('radar').addEventListener('click', async () => {{
  const note = document.getElementById('radarNote');
  if (radar) {{ map.removeLayer(radar); radar = null; note.textContent = ''; return; }}
  try {{
    const info = await (await fetch('https://api.rainviewer.com/public/weather-maps.json')).json();
    const frame = info.radar.past[info.radar.past.length - 1];
    radar = L.tileLayer(info.host + frame.path + '/256/{{z}}/{{x}}/{{y}}/2/1_1.png',
      {{ opacity: 0.65, maxNativeZoom: 7, maxZoom: 12, attribution: 'Radar &copy; RainViewer' }}).addTo(map);
    note.textContent = 'radar ' + new Date(frame.time * 1000).toLocaleTimeString() + ', where there is coverage';
  }} catch (err) {{ note.textContent = "the radar couldn't be loaded"; }}
}});
</script></body></html>
"""


def save_weather_map(forecasts: list[Forecast], alerts: list[Alert], folder: Path, title: str = "Weather",
                     now: datetime | None = None, centre: tuple[float, float] = (7.8, 80.7), zoom: int = 7) -> Path:
    now = now or datetime.now(UTC)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"weather-map {now:%Y-%m-%d %H%M}.html"
    path.write_text(page(forecasts, alerts, title, now, centre, zoom), encoding="utf-8")
    return path
