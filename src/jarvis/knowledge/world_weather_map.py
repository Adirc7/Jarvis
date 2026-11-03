"""The world weather map: temperature, clouds, rain, wind, humidity and pressure over the whole world,
every country's numbers at its capital, the next 48 hours, satellite clouds and storm alerts.

    path = save_world_map(world, alerts, folder, "World weather", centre=(20, 20), zoom=2)

What it shows (world_weather.py gets the numbers):

- a colour field for the chosen layer, filled in between the ~430 points by modified Shepard
  interpolation (each spot from its 8 nearest points, weights falling smoothly to zero, so no seams);
- the wind as moving streaks (like earth.nullschool.net), from the same points;
- each country's capital with its value; click it for everything and a 48-hour sparkline; click
  anywhere else for the interpolated values there;
- a slider (and a play button) through the next 48 hours, every 3 hours;
- satellite clouds from NASA GIBS: live infrared from GOES-West, GOES-East and Himawari (every 10
  minutes; they don't see Europe and Africa), and yesterday's true-colour photo of the whole world;
- RainViewer's rain radar, and GDACS's storm and disaster alerts.

Jarvis can change the layer by voice (map_view, action "layer"), like he moves the map.
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path

from . import map_tiles
from .weather import CODES, Alert
from .weather_map import LEVEL_COLOURS
from .world_weather import World

LAYERS = ("temperature", "clouds", "rain", "wind", "humidity", "pressure")


def map_data(world: World, alerts: list[Alert], focus: int | None = None, layer: str = "temperature") -> dict:
    return {
        "times": world.times, "fetched": world.fetched.isoformat(timespec="minutes"),
        "samples": [[s.lat, s.lon, s.country, s.capital, s.population] for s in world.samples],
        "v": world.values, "codes": {str(k): v for k, v in CODES.items()},
        "alerts": [{"kind": a.kind, "name": a.name, "level": a.level, "country": a.country, "lat": a.lat,
                    "lon": a.lon, "since": a.since, "severity": a.severity,
                    "url": a.url if a.url.startswith(("http://", "https://")) else ""}
                   for a in alerts if a.lat is not None and a.lon is not None],
        "levels": LEVEL_COLOURS, "focus": -1 if focus is None else focus,
        "layer": layer if layer in LAYERS else "temperature",
    }


HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root { --bg:#03070d; --panel:#091522; --line:#12314a; --text:#eaf5ff; --muted:#8fa7ba; --cyan:#4de1ff; --amber:#ffb43b; }
html, body { margin:0; height:100%; background:var(--bg); color:var(--text); font-family:"Segoe UI", system-ui, sans-serif; }
main { display:grid; grid-template-columns:minmax(0,1fr) 340px; height:100vh; }
#map { height:100%; background:#02060b; }
aside { background:var(--panel); padding:14px 16px; overflow:auto; border-left:1px solid var(--line); }
h1 { font-size:18px; font-weight:500; margin:0 0 4px; color:var(--cyan); }
h2 { font-size:12px; font-weight:500; letter-spacing:2px; color:var(--cyan); text-transform:uppercase; margin:16px 0 6px; }
.meta { color:var(--muted); font-size:12px; }
.layers { display:grid; grid-template-columns:repeat(3,1fr); gap:6px; margin:10px 0 4px; }
button { background:#0f2639; color:var(--text); border:1px solid #1c4766; border-radius:6px; padding:6px 8px;
         cursor:pointer; font:inherit; font-size:13px; }
button:hover { border-color:var(--cyan); }
button.on { background:#12405e; border-color:var(--cyan); color:#fff; }
.time { display:flex; align-items:center; gap:8px; margin-top:10px; }
.time input { flex:1; accent-color:var(--cyan); }
#when { font-size:14px; margin-top:4px; }
.toggle { display:flex; align-items:center; gap:8px; font-size:13px; padding:3px 0; cursor:pointer; }
.toggle input { accent-color:var(--cyan); }
#legendBar { height:10px; border-radius:5px; margin:6px 0 2px; border:1px solid #1c4766; }
#legendTicks { display:flex; justify-content:space-between; font-size:11px; color:var(--muted); }
#find { width:100%; box-sizing:border-box; background:#06111c; color:var(--text); border:1px solid #1c4766;
        border-radius:6px; padding:6px 8px; font:inherit; font-size:13px; }
.row { display:flex; justify-content:space-between; gap:8px; font-size:13px; padding:4px 2px; border-bottom:1px solid #0e2235; cursor:pointer; }
.row:hover { background:#0c1d2e; }
.row small { color:var(--muted); }
#list { max-height:38vh; overflow:auto; }
.alert a { color:var(--text); text-decoration:none; } .alert a:hover { color:var(--cyan); }
.leaflet-popup-content-wrapper, .leaflet-popup-tip { background:var(--panel); color:var(--text); }
.leaflet-popup-content { font-size:13px; line-height:1.45; } .leaflet-popup-content a { color:var(--cyan); }
.cap { background:transparent; border:0; }
.cap i { display:block; width:6px; height:6px; border-radius:50%; background:#eaf5ff; box-shadow:0 0 0 1px #03070d; }
.cap b { position:absolute; left:8px; top:-5px; font-size:11px; font-weight:600; white-space:nowrap; color:#fff;
         text-shadow:0 0 3px #000, 0 0 2px #000, 0 0 1px #000; pointer-events:none; }
#map.z1 .cap.t2 b, #map.z1 .cap.t3 b, #map.z2 .cap.t3 b { display:none; }
#map.z1 .cap.t3 i { display:none; }
.field, .flow { pointer-events:none; }
.ir { mix-blend-mode:screen; }
#note { color:var(--amber); font-size:12px; min-height:14px; }
__TILES_CSS__@media (max-width: 800px) { main { grid-template-columns:1fr; grid-template-rows:60vh auto; } }
</style></head>
<body><main><div id="map"></div>
<aside><h1>__TITLE__</h1>
<div class="meta">Jarvis, __NOW__ UTC. Forecast models from Open-Meteo, at every capital and over the seas;
the colours between the points are filled in.</div>
<div class="layers" id="layers"></div>
<div class="time"><button id="play" title="Play the next 48 hours">&#9654;</button>
<input id="hour" type="range" min="0" value="0" step="1"></div>
<div id="when"></div>
<div id="legendBar"></div><div id="legendTicks"></div>
<h2>On the map</h2>
<label class="toggle"><input type="checkbox" id="flowOn" checked> Wind flow (moving streaks)</label>
<label class="toggle"><input type="checkbox" id="irOn"> Satellite clouds now (NASA, not over Europe and Africa)</label>
<label class="toggle"><input type="checkbox" id="photoOn"> Satellite photo of yesterday (NASA)</label>
<label class="toggle"><input type="checkbox" id="radarOn"> Rain radar (RainViewer, where there is radar)</label>
<label class="toggle"><input type="checkbox" id="capsOn" checked> Capitals and their numbers</label>
<div id="note"></div>
<h2 id="listTitle">Countries</h2>
<input id="find" placeholder="Find a country" autocomplete="off">
<div id="list"></div>
<h2>Storm and disaster alerts</h2><div id="alerts"></div>
<p class="meta">Each country's numbers are at its capital. Official warnings: each country's weather service
(in Sri Lanka, the Department of Meteorology and the DMC, 117). Places: GeoNames.</p>
</aside></main>
<script>__TILES_JS__
const DATA = __DATA__;
"""

SCRIPT = r"""
const LAYERS = {
  temperature: { key: 't', name: 'Temperature', unit: '°C', fmt: v => Math.round(v) + '°',
    stops: [[-40, 225, 215, 255, .6], [-25, 155, 123, 255, .6], [-10, 58, 107, 255, .55], [0, 77, 225, 255, .5],
            [10, 100, 239, 183, .5], [20, 232, 232, 90, .5], [30, 255, 180, 59, .55], [40, 255, 77, 77, .6],
            [50, 163, 0, 27, .65]] },
  clouds: { key: 'cloud', name: 'Clouds', unit: '% of the sky', fmt: v => Math.round(v) + '%',
    stops: [[0, 255, 255, 255, 0], [30, 200, 215, 230, .15], [70, 225, 235, 245, .45], [100, 245, 250, 255, .7]] },
  rain: { key: 'rain', name: 'Rain', unit: 'mm in the hour', fmt: v => v < 0.05 ? '0' : v.toFixed(1),
    stops: [[0, 77, 225, 255, 0], [0.1, 77, 225, 255, .3], [1, 58, 139, 255, .55], [5, 180, 140, 255, .65],
            [20, 255, 118, 111, .75]] },
  wind: { key: 'wind', name: 'Wind', unit: 'km/h', fmt: v => Math.round(v),
    stops: [[0, 22, 48, 74, .35], [10, 43, 108, 176, .45], [20, 77, 225, 255, .45], [35, 100, 239, 183, .5],
            [50, 232, 232, 90, .55], [70, 255, 180, 59, .6], [100, 255, 77, 77, .65], [150, 194, 24, 91, .7]] },
  humidity: { key: 'rh', name: 'Humidity', unit: '%', fmt: v => Math.round(v) + '%',
    stops: [[0, 196, 120, 60, .5], [30, 232, 196, 110, .4], [60, 100, 239, 183, .35], [80, 77, 225, 255, .45],
            [100, 58, 107, 255, .55]] },
  pressure: { key: 'p', name: 'Pressure', unit: 'hPa at sea level', fmt: v => Math.round(v),
    stops: [[960, 194, 24, 91, .6], [985, 180, 140, 255, .5], [1000, 58, 139, 255, .4], [1013, 22, 48, 74, .25],
            [1025, 232, 232, 90, .4], [1040, 255, 140, 59, .55]] },
};
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
const S = DATA.samples, N = S.length, V = DATA.v, T = DATA.times;
const COMPASS = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
const fromDir = d => d == null ? '' : COMPASS[Math.round(d / 22.5) % 16];
let layer = LAYERS[DATA.layer] ? DATA.layer : 'temperature', step = 0;

// ---- filling in between the points (modified Shepard: 8 nearest, weights reach zero at the 9th) ----
const RES = 2, COLS = 360 / RES, LAT0 = 86, ROWS = Math.floor((LAT0 + 86) / RES) + 1;
const K = 8, nb = new Int32Array(COLS * ROWS * K), wt = new Float32Array(COLS * ROWS * K);
const t0 = performance.now();
(function neighbours() {
  const bd = new Float64Array(K + 1), bi = new Int32Array(K + 1);
  for (let r = 0; r < ROWS; r++) {
    const lat = LAT0 - r * RES, cl = Math.max(0.05, Math.cos(lat * Math.PI / 180));
    for (let c = 0; c < COLS; c++) {
      const lon = -180 + c * RES;
      bd.fill(Infinity); bi.fill(-1);
      for (let i = 0; i < N; i++) {               // keep the K+1 nearest, nearest first
        let dl = Math.abs(lon - S[i][1]); if (dl > 180) dl = 360 - dl;
        const dx = dl * cl, dy = lat - S[i][0], d = dx * dx + dy * dy;
        if (d >= bd[K]) continue;
        let j = K;
        while (j > 0 && bd[j - 1] > d) { bd[j] = bd[j - 1]; bi[j] = bi[j - 1]; j--; }
        bd[j] = d; bi[j] = i;
      }
      const R = Math.sqrt(bd[K]) + 1e-6, cell = (r * COLS + c) * K;
      for (let a = 0; a < K; a++) {
        const di = Math.max(Math.sqrt(bd[a]), 0.05), w = Math.max(0, R - di) / (R * di);
        nb[cell + a] = bi[a]; wt[cell + a] = w * w;
      }
    }
  }
})();
window.jarvisFillMs = Math.round(performance.now() - t0);
function fieldOf(values) {                      // values: one number (or null) per point
  const f = new Float32Array(COLS * ROWS);
  for (let cell = 0; cell < COLS * ROWS; cell++) {
    let sw = 0, sv = 0;
    for (let a = 0; a < K; a++) {
      const v = values[nb[cell * K + a]];
      if (v == null || Number.isNaN(v)) continue;
      const w = wt[cell * K + a]; sw += w; sv += w * v;
    }
    f[cell] = sw > 0 ? sv / sw : NaN;
  }
  return f;
}
function at(f, lat, lon) {                      // bilinear, wrapping round the world
  lon = ((lon + 180) % 360 + 360) % 360 - 180;
  const y = (LAT0 - lat) / RES, x = (lon + 180) / RES;
  if (y < 0 || y > ROWS - 1) return NaN;
  const r0 = Math.floor(y), c0 = Math.floor(x) % COLS, r1 = Math.min(ROWS - 1, r0 + 1), c1 = (c0 + 1) % COLS;
  const fy = y - r0, fx = x - Math.floor(x);
  const a = f[r0 * COLS + c0], b = f[r0 * COLS + c1], c = f[r1 * COLS + c0], d = f[r1 * COLS + c1];
  return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
}
const cacheF = new Map();
function field(key, s) {
  const id = key + '@' + s;
  if (!cacheF.has(id)) {
    let vals;
    if (key === 'u' || key === 'v') vals = S.map((_, i) => {
      const sp = V.wind[i][s], dir = V.dir[i][s];
      if (sp == null || dir == null) return null;
      const r = dir * Math.PI / 180;              // the wind comes FROM dir: it blows the other way
      return key === 'u' ? -sp * Math.sin(r) : -sp * Math.cos(r);
    });
    else vals = S.map((_, i) => V[key][i][s]);
    cacheF.set(id, fieldOf(vals));
    if (cacheF.size > 40) cacheF.delete(cacheF.keys().next().value);
  }
  return cacheF.get(id);
}
function colour(stops, v) {
  if (Number.isNaN(v)) return null;
  if (v <= stops[0][0]) return stops[0].slice(1);
  for (let i = 1; i < stops.length; i++) if (v <= stops[i][0]) {
    const a = stops[i - 1], b = stops[i], t = (v - a[0]) / (b[0] - a[0]);
    return [1, 2, 3, 4].map(k => a[k] + (b[k] - a[k]) * t);
  }
  return stops[stops.length - 1].slice(1);
}

// ---- the map ----
const map = L.map('map', { maxZoom: 10, zoomSnap: 0.25 }).setView(__CENTRE__, __ZOOM__);
addBaseLayers(map);
fitWorld(map);
const zoomClass = () => { const z = map.getZoom(), m = document.getElementById('map');   // zooms can be fractions
  m.classList.toggle('z1', z < 3); m.classList.toggle('z2', z >= 3 && z < 4); };
map.on('zoomend', zoomClass); zoomClass();

const CanvasLayer = L.Layer.extend({
  initialize(cls, hideOnMove) { this.cls = cls; this.hideOnMove = hideOnMove; },
  onAdd(m) {
    this.canvas = L.DomUtil.create('canvas', this.cls);
    m.getPanes().overlayPane.appendChild(this.canvas);
    m.on('moveend resize', this.reset, this); m.on(this.hideOnMove ? 'movestart zoomstart' : 'zoomstart', this.hide, this);
    this.reset();
  },
  onRemove(m) {
    m.off('moveend resize', this.reset, this); m.off('movestart zoomstart', this.hide, this);
    this.canvas.remove(); if (this.stop) this.stop();
  },
  hide() { this.canvas.style.visibility = 'hidden'; if (this.stop) this.stop(); },
  reset() {
    const size = map.getSize(), pr = window.devicePixelRatio || 1;
    L.DomUtil.setPosition(this.canvas, map.containerPointToLayerPoint([0, 0]));
    this.canvas.width = size.x * pr; this.canvas.height = size.y * pr;
    this.canvas.style.width = size.x + 'px'; this.canvas.style.height = size.y + 'px';
    this.canvas.style.visibility = 'visible';
    this.draw(size, pr);
  },
});

const fieldLayer = new (CanvasLayer.extend({
  draw(size, pr) {
    const B = 4, w = Math.ceil(size.x / B), h = Math.ceil(size.y / B), off = document.createElement('canvas');
    off.width = w; off.height = h;
    const img = off.getContext('2d').createImageData(w, h), L_ = LAYERS[layer], f = field(L_.key, step);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const ll = map.containerPointToLatLng([x * B + B / 2, y * B + B / 2]), c = colour(L_.stops, at(f, ll.lat, ll.lng));
      if (!c) continue;
      const k = (y * w + x) * 4;
      img.data[k] = c[0]; img.data[k + 1] = c[1]; img.data[k + 2] = c[2]; img.data[k + 3] = c[3] * 255;
    }
    off.getContext('2d').putImageData(img, 0, 0);
    const ctx = this.canvas.getContext('2d');
    ctx.imageSmoothingEnabled = true; ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.drawImage(off, 0, 0, w * B * pr, h * B * pr);
  },
}))('field', false);
fieldLayer.addTo(map);

const flowLayer = new (CanvasLayer.extend({
  draw(size, pr) {
    this.stop();
    const ctx = this.canvas.getContext('2d'), n = Math.min(4500, Math.round(size.x * size.y / 220));
    const fu = field('u', step), fv = field('v', step), parts = [];
    const spawn = p => { p.x = Math.random() * size.x; p.y = Math.random() * size.y; p.age = Math.random() * 80; return p; };
    for (let i = 0; i < n; i++) parts.push(spawn({}));
    const k = 0.022 * Math.pow(1.25, Math.max(0, map.getZoom() - 2));     // pixels a frame for each km/h
    ctx.scale(pr, pr); ctx.lineWidth = 1.1;
    const frame = () => {
      ctx.globalCompositeOperation = 'destination-in'; ctx.fillStyle = 'rgba(0,0,0,0.93)';
      ctx.fillRect(0, 0, size.x, size.y);
      ctx.globalCompositeOperation = 'source-over'; ctx.strokeStyle = 'rgba(236,247,255,0.78)';
      ctx.beginPath();
      for (const p of parts) {
        const ll = map.containerPointToLatLng([p.x, p.y]), u = at(fu, ll.lat, ll.lng), v = at(fv, ll.lat, ll.lng);
        if (Number.isNaN(u) || Number.isNaN(v) || ++p.age > 110) { spawn(p); p.age = 0; continue; }
        const nx = p.x + u * k, ny = p.y - v * k;
        ctx.moveTo(p.x, p.y); ctx.lineTo(nx, ny); p.x = nx; p.y = ny;
        if (nx < 0 || ny < 0 || nx > size.x || ny > size.y) { spawn(p); p.age = 0; }
      }
      ctx.stroke();
      this.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
  },
  stop() { if (this.raf) cancelAnimationFrame(this.raf); this.raf = 0; },
}))('flow', true);
flowLayer.addTo(map);

// ---- the capitals ----
const capLayer = L.layerGroup().addTo(map), caps = [];
S.forEach((s, i) => {
  if (!s[2]) return;
  const tier = s[4] >= 40e6 ? 't1' : s[4] >= 8e6 ? 't2' : 't3';
  const m = L.marker([s[0], s[1]], { icon: L.divIcon({ className: 'cap ' + tier, html: '<i></i><b></b>', iconSize: [6, 6] }),
                                     title: s[2] + ' (' + s[3] + ')', keyboard: false });
  m.on('click', () => m.bindPopup(popup(i), { maxWidth: 300 }).openPopup());
  m.addTo(capLayer); caps.push([i, m]);
});
function value(i, key, s = step) { const row = V[key] && V[key][i]; return row ? row[s] : null; }
function relabel() {
  const L_ = LAYERS[layer];
  for (const [i, m] of caps) {
    const el = m.getElement(); if (!el) continue;
    const v = value(i, L_.key); el.querySelector('b').textContent = v == null ? '' : L_.fmt(v);
  }
}
map.on('zoomend', relabel);
function spark(i) {                             // 48 hours of temperature (line) and rain (bars)
  const t = V.t[i], r = V.rain[i], w = 260, h = 54, n = T.length;
  const ok = t.filter(x => x != null); if (!ok.length) return '';
  const lo = Math.min(...ok), hi = Math.max(...ok), y = v => h - 8 - (v - lo) / Math.max(1, hi - lo) * (h - 18);
  const pts = t.map((v, k) => v == null ? '' : `${(k / (n - 1) * w).toFixed(1)},${y(v).toFixed(1)}`).filter(Boolean).join(' ');
  const bars = r.map((v, k) => v ? `<rect x="${(k / (n - 1) * w - 3).toFixed(1)}" y="${h - Math.min(h - 4, v * 6)}" width="6" height="${Math.min(h - 4, v * 6)}" fill="#3a8bff" opacity=".7"/>` : '').join('');
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block;margin-top:6px">${bars}` +
    `<polyline points="${pts}" fill="none" stroke="#ffb43b" stroke-width="2"/>` +
    `<line x1="${(step / (n - 1) * w).toFixed(1)}" x2="${(step / (n - 1) * w).toFixed(1)}" y1="0" y2="${h}" stroke="#4de1ff" stroke-dasharray="2 2"/>` +
    `<text x="0" y="10" fill="#8fa7ba" font-size="10">${Math.round(hi)}°</text>` +
    `<text x="0" y="${h - 1}" fill="#8fa7ba" font-size="10">${Math.round(lo)}° · next 48 h</text></svg>`;
}
function lines(get) {
  const t = get('t'), code = get('code'), wind = get('wind'), gust = get('gust'), dir = get('dir');
  const n = (v, u, d = 0) => v == null || Number.isNaN(v) ? '?' : Number(v).toFixed(d) + u;
  return `${n(t, ' °C')}${code == null ? '' : ', ' + esc(DATA.codes[String(Math.round(code))] || '')}<br>` +
    `clouds ${n(get('cloud'), '%')} · rain ${n(get('rain'), ' mm/h', 1)}<br>` +
    `wind ${n(wind, ' km/h')}${dir == null ? '' : ' from ' + fromDir(dir)} · gusts ${n(gust, ' km/h')}<br>` +
    `humidity ${n(get('rh'), '%')} · ${n(get('p'), ' hPa')}`;
}
function popup(i) {
  const s = S[i];
  return `<b>${esc(s[2])}</b> <span style="color:#8fa7ba">at ${esc(s[3])}, ${esc(whenText(step))}</span><br>` +
    lines(k => value(i, k)) + spark(i);
}
map.on('click', e => {                          // anywhere else: the filled-in numbers there
  const get = k => k === 'code' ? null : k === 'dir' ? dirAt(e.latlng) : at(field(k, step), e.latlng.lat, e.latlng.lng);
  L.popup().setLatLng(e.latlng).setContent(`<b>Around here</b> <span style="color:#8fa7ba">(filled in between ` +
    `the nearest points, ${esc(whenText(step))})</span><br>` + lines(get)).openOn(map);
});
function dirAt(ll) {
  const u = at(field('u', step), ll.lat, ll.lng), v = at(field('v', step), ll.lat, ll.lng);
  return Number.isNaN(u) ? null : (Math.atan2(-u, -v) * 180 / Math.PI + 360) % 360;
}

// ---- satellites (NASA GIBS), radar (RainViewer), alerts (GDACS) ----
const GIBS = 'https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi';
const note = msg => { document.getElementById('note').textContent = msg; };
function gibs(name, time, extra) {
  const l = L.tileLayer.wms(GIBS, Object.assign({ layers: name, format: 'image/png', transparent: true,
    version: '1.1.1', time, zIndex: 5, attribution: 'Satellite: NASA GIBS' }, extra));
  let bad = 0; l.on('tileerror', () => { if (++bad === 6) note("NASA's satellite layer didn't answer: try again later."); });
  return l;
}
const geoTime = () => { const t = new Date(Date.now() - 50 * 60e3);
  t.setUTCMinutes(Math.floor(t.getUTCMinutes() / 10) * 10, 0, 0); return t.toISOString().slice(0, 19) + 'Z'; };
const yesterday = () => new Date(Date.now() - 864e5).toISOString().slice(0, 10);
let irLayer = null, photoLayer = null, radar = null;
document.getElementById('irOn').addEventListener('change', e => {
  if (irLayer) { map.removeLayer(irLayer); irLayer = null; }
  if (!e.target.checked) { note(''); return; }
  const t = geoTime();
  irLayer = L.layerGroup(['GOES-West_ABI_Band13_Clean_Infrared', 'GOES-East_ABI_Band13_Clean_Infrared',
    'Himawari_AHI_Band13_Clean_Infrared'].map(n => gibs(n, t, { className: 'ir', opacity: 0.9, zIndex: 6 }))).addTo(map);
  note('Infrared from about ' + new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) +
       ': cold cloud tops are bright.');
});
document.getElementById('photoOn').addEventListener('change', e => {
  if (photoLayer) { map.removeLayer(photoLayer); photoLayer = null; }
  if (!e.target.checked) { note(''); return; }
  const names = ['VIIRS_NOAA20_CorrectedReflectance_TrueColor', 'VIIRS_SNPP_CorrectedReflectance_TrueColor',
                 'MODIS_Terra_CorrectedReflectance_TrueColor'];
  const tryOne = k => {                          // another satellite if one doesn't answer
    photoLayer = gibs(names[k], yesterday(), { transparent: false, format: 'image/jpeg' });
    let bad = 0; photoLayer.on('tileerror', () => { if (++bad === 4 && k + 1 < names.length && photoLayer) {
      map.removeLayer(photoLayer); tryOne(k + 1); } });
    photoLayer.addTo(map);
  };
  tryOne(0); note("Yesterday's photo, " + yesterday() + ": dark gaps are where no satellite passed in daylight.");
});
document.getElementById('radarOn').addEventListener('change', async e => {
  if (radar) { map.removeLayer(radar); radar = null; }
  if (!e.target.checked) { note(''); return; }
  try {
    const info = await (await fetch('https://api.rainviewer.com/public/weather-maps.json')).json();
    const frame = info.radar.past[info.radar.past.length - 1];
    radar = L.tileLayer(info.host + frame.path + '/256/{z}/{x}/{y}/2/1_1.png',
      { opacity: 0.7, maxNativeZoom: 7, maxZoom: 12, zIndex: 7, attribution: 'Radar &copy; RainViewer' }).addTo(map);
    note('Radar at ' + new Date(frame.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '.');
  } catch (err) { note("The radar couldn't be loaded."); e.target.checked = false; }
});
document.getElementById('flowOn').addEventListener('change', e => e.target.checked ? flowLayer.addTo(map) : map.removeLayer(flowLayer));
document.getElementById('capsOn').addEventListener('change', e => { e.target.checked ? capLayer.addTo(map) : map.removeLayer(capLayer); relabel(); });
for (const a of DATA.alerts) {
  const c = DATA.levels[String(a.level).toLowerCase()] || '#eaf5ff';
  L.circleMarker([a.lat, a.lon], { radius: 11, color: c, fillColor: c, fillOpacity: 0.2, weight: 3, dashArray: '4 3' })
    .bindPopup(`<b>${esc(a.level)} alert: ${esc(a.kind)}</b><br>${esc(a.name)}<br>${esc(a.country)}<br>${esc(a.severity)}` +
               (a.url ? `<br><a href="${esc(a.url)}" target="_blank" rel="noopener">GDACS report</a>` : '')).addTo(map);
}
document.getElementById('alerts').innerHTML = DATA.alerts.map(a =>
  `<div class="row alert" data-lat="${Number(a.lat)}" data-lon="${Number(a.lon)}"><span>` +
  (a.url ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.kind)}: ${esc(a.name)}</a>` : `${esc(a.kind)}: ${esc(a.name)}`) +
  `<br><small>${esc(a.country || 'at sea')}</small></span><span style="color:${DATA.levels[String(a.level).toLowerCase()] || '#eaf5ff'}">${esc(a.level)}</span></div>`).join('') ||
  '<div class="meta">No current alerts.</div>';
document.getElementById('alerts').addEventListener('click', e => {
  const row = e.target.closest('.row'); if (!row || e.target.closest('a')) return;
  map.flyTo([Number(row.dataset.lat), Number(row.dataset.lon)], 5);
});

// ---- the side panel: layers, hours, legend, countries ----
function whenText(s) {
  if (!T[s]) return 'now';
  const d = new Date(T[s] + 'Z'), h = s * (T.length > 1 ? (Date.parse(T[1] + 'Z') - Date.parse(T[0] + 'Z')) / 36e5 : 3);
  return d.toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' }) + (s === 0 ? ' (now)' : ` (+${h} h)`);
}
const layerBox = document.getElementById('layers');
for (const [id, L_] of Object.entries(LAYERS)) {
  const b = document.createElement('button'); b.textContent = L_.name; b.dataset.id = id;
  b.addEventListener('click', () => setLayer(id)); layerBox.appendChild(b);
}
function legend() {
  const L_ = LAYERS[layer], st = L_.stops, lo = st[0][0], hi = st[st.length - 1][0];
  document.getElementById('legendBar').style.background = 'linear-gradient(90deg,' + st.map(s =>
    `rgba(${s[1]},${s[2]},${s[3]},${Math.max(0.25, s[4] * 1.4)}) ${((s[0] - lo) / (hi - lo) * 100).toFixed(1)}%`).join(',') + ')';
  document.getElementById('legendTicks').innerHTML = [st[0], st[Math.floor(st.length / 2)], st[st.length - 1]]
    .map(s => `<span>${esc(s[0])}</span>`).join('') + `<span>${esc(L_.unit)}</span>`;
  document.getElementById('legendTicks').title = L_.unit;
}
function list() {
  const L_ = LAYERS[layer], q = document.getElementById('find').value.trim().toLowerCase();
  const rows = caps.map(([i]) => i).filter(i => !q || S[i][2].toLowerCase().includes(q) || S[i][3].toLowerCase().includes(q))
    .sort((a, b) => (value(b, L_.key) ?? -1e9) - (value(a, L_.key) ?? -1e9));
  document.getElementById('listTitle').textContent = `Countries by ${L_.name.toLowerCase()} (${L_.unit})`;
  document.getElementById('list').innerHTML = rows.map(i => `<div class="row" data-i="${i}"><span>${esc(S[i][2])} ` +
    `<small>${esc(S[i][3])}</small></span><span>${value(i, L_.key) == null ? '?' : esc(L_.fmt(value(i, L_.key)))}</span></div>`).join('');
}
document.getElementById('find').addEventListener('input', list);
document.getElementById('list').addEventListener('click', e => {
  const row = e.target.closest('.row'); if (!row) return;
  showCountry(Number(row.dataset.i));
});
const openCountry = i => { const m = caps.find(c => c[0] === i); if (m) m[1].bindPopup(popup(i), { maxWidth: 300 }).openPopup(); };
function showCountry(i, zoom = 5) {
  map.flyTo([S[i][0], S[i][1]], zoom, { duration: 1.2 });
  map.once('moveend', () => openCountry(i));
}
function redraw() {
  document.querySelectorAll('#layers button').forEach(b => b.classList.toggle('on', b.dataset.id === layer));
  document.getElementById('when').textContent = LAYERS[layer].name + ', ' + whenText(step);
  legend(); list(); relabel();
  if (map.hasLayer(fieldLayer)) fieldLayer.reset();
  if (map.hasLayer(flowLayer)) flowLayer.reset();
}
function setLayer(id) {
  if (id === 'satellite') { const b = document.getElementById('irOn'); if (!b.checked) b.click(); return; }
  if (id === 'radar') { const b = document.getElementById('radarOn'); if (!b.checked) b.click(); return; }
  if (!LAYERS[id]) return;
  layer = id; redraw();
}
window.jarvisLayer = setLayer;                  // Jarvis: "show me the wind" (map_tiles.followJarvis)
const slider = document.getElementById('hour');
slider.max = Math.max(0, T.length - 1);
slider.addEventListener('input', () => { step = Number(slider.value); redraw(); });
let playing = 0;
document.getElementById('play').addEventListener('click', () => {
  const b = document.getElementById('play');
  if (playing) { clearInterval(playing); playing = 0; b.innerHTML = '&#9654;'; return; }
  b.innerHTML = '&#10074;&#10074;';
  playing = setInterval(() => { step = (step + 1) % T.length; slider.value = String(step); redraw(); }, 1100);
});
followJarvis(map);
panelToggle(map);
redraw();
if (DATA.focus >= 0) setTimeout(() => openCountry(DATA.focus), 300);   // the country asked about
</script></body></html>
"""


def page(world: World, alerts: list[Alert], title: str, now: datetime | None = None,
         centre: tuple[float, float] = (20.0, 20.0), zoom: int = 2, focus: int | None = None,
         layer: str = "temperature") -> str:
    now = now or datetime.now(UTC)
    data = json.dumps(map_data(world, alerts, focus, layer), ensure_ascii=False,
                      separators=(",", ":")).replace("</", "<\\/")
    heading = html.escape(title)
    head = (HEAD.replace("__TITLE__", heading).replace("__NOW__", f"{now:%Y-%m-%d %H:%M}")
            .replace("__TILES_CSS__", map_tiles.CSS).replace("__TILES_JS__", map_tiles.JS))
    script = SCRIPT.replace("__CENTRE__", json.dumps([round(centre[0], 3), round(centre[1], 3)])).replace(
        "__ZOOM__", str(int(zoom)))
    return head.replace("__DATA__", data) + script


def save_world_map(world: World, alerts: list[Alert], folder: Path, title: str = "World weather",
                   now: datetime | None = None, centre: tuple[float, float] = (20.0, 20.0), zoom: int = 2,
                   focus: int | None = None, layer: str = "temperature") -> Path:
    now = now or datetime.now(UTC)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"weather-map {now:%Y-%m-%d %H%M} world.html"     # "weather-map *": Jarvis's window finds it
    path.write_text(page(world, alerts, title, now, centre, zoom, focus, layer), encoding="utf-8")
    return path


__all__ = ["LAYERS", "map_data", "page", "save_world_map"]
