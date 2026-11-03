"""The base map under the news and weather maps: tiles that need no account or key.

CARTO's dark tiles, used at first, began answering "API KEY REQUIRED" (30 Oct).
Now: OpenStreetMap's tiles, darkened in the browser to match Jarvis's look;
if those don't load (no network, or OpenStreetMap's usage limits), Esri's
street map, darkened the same way. Streets and satellite imagery are a click
away (the layer button, top right). Both ask only for the credit shown.
"""

CSS = (".dark-tiles { filter: invert(1) hue-rotate(180deg) brightness(0.9) contrast(0.9) saturate(0.6); }\n"
       ".leaflet-control-layers { background:#091522; color:#eaf5ff; border:1px solid #12314a; }\n"
       "main.full { grid-template-columns:minmax(0,1fr) 0 !important; } main.full > aside { display:none; }\n"
       ".panelHide { float:right; margin:0 0 6px 8px; font-size:12px; padding:3px 8px; background:#0f2639; "
       "color:#eaf5ff; border:1px solid #1c4766; border-radius:6px; cursor:pointer; }\n"
       ".panelShow { font:12px 'Segoe UI', system-ui, sans-serif; padding:6px 10px; background:#091522; "
       "color:#eaf5ff; border:1px solid #1c4766; border-radius:6px; cursor:pointer; }\n"
       ".panelHide:hover, .panelShow:hover { border-color:#4de1ff; }\n")

JS = """
function addBaseLayers(map) {
  const osm = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  const esri = name => 'https://server.arcgisonline.com/ArcGIS/rest/services/' + name + '/MapServer/tile/{z}/{y}/{x}';
  const osmCredit = '&copy; OpenStreetMap contributors', esriCredit = 'Tiles &copy; Esri';
  const layers = {
    'Dark': L.tileLayer(osm, { attribution: osmCredit, maxZoom: 18, className: 'dark-tiles' }),
    'Dark (Esri)': L.tileLayer(esri('World_Street_Map'), { attribution: esriCredit, maxZoom: 18, className: 'dark-tiles' }),
    'Streets': L.tileLayer(osm, { attribution: osmCredit, maxZoom: 18 }),
    'Satellite': L.tileLayer(esri('World_Imagery'), { attribution: esriCredit, maxZoom: 18 }),
  };
  layers['Dark'].addTo(map);
  let failed = 0;
  layers['Dark'].on('tileerror', () => {          // OpenStreetMap didn't answer: Esri's map instead
    if (++failed === 4 && map.hasLayer(layers['Dark'])) {
      map.removeLayer(layers['Dark']);
      layers['Dark (Esri)'].addTo(map);
    }
  });
  L.control.layers(layers, null, { position: 'topright' }).addTo(map);
  return layers;
}
// The side panel can be hidden for a bigger map, and shown again (remembered for next time).
function panelToggle(map) {
  const main = document.querySelector('main'), aside = document.querySelector('main > aside');
  if (!main || !aside) return;
  const hide = document.createElement('button');
  hide.className = 'panelHide'; hide.type = 'button'; hide.textContent = 'Hide panel \u203a';
  hide.title = 'Hide this panel: a bigger map';
  aside.prepend(hide);
  const show = L.control({ position: 'topright' });
  show.onAdd = () => {
    const b = L.DomUtil.create('button', 'panelShow');
    b.type = 'button'; b.textContent = '\u2039 Panel'; b.title = 'Show the panel again';
    L.DomEvent.disableClickPropagation(b); b.addEventListener('click', () => set(false));
    return b;
  };
  function set(full) {
    main.classList.toggle('full', full);
    if (full) show.addTo(map); else show.remove();
    setTimeout(() => map.invalidateSize(), 60);
    try { localStorage.setItem('jarvisMapFull', full ? '1' : ''); } catch (e) {}
  }
  hide.addEventListener('click', () => set(true));
  let full = false;
  try { full = localStorage.getItem('jarvisMapFull') === '1'; } catch (e) {}
  if (full) set(true);
}
// Jarvis moves the map when asked ("show Sri Lanka and zoom in"): his window passes the
// move on. Only from the window's own address, and only numbers are used.
function followJarvis(map) {
  let mark = null;
  window.addEventListener('message', e => {
    if (e.origin !== window.location.origin || !e.data || typeof e.data !== 'object') return;
    const m = e.data;
    if (m.action === 'layer' && typeof m.layer === 'string' && typeof window.jarvisLayer === 'function') {
      window.jarvisLayer(m.layer);                 // the world weather map: "show me the wind"
    } else if (m.action === 'zoom_in') map.zoomIn(2);
    else if (m.action === 'zoom_out') map.zoomOut(2);
    else if (m.action === 'focus' && Number.isFinite(m.lat) && Number.isFinite(m.lon)) {
      map.flyTo([m.lat, m.lon], Number.isFinite(m.zoom) ? m.zoom : 7, { duration: 1.5 });
      if (mark) map.removeLayer(mark);
      mark = L.circleMarker([m.lat, m.lon], { radius: 9, color: '#ffb43b', weight: 3, fillOpacity: 0 }).addTo(map);
      if (typeof m.label === 'string') mark.bindTooltip(m.label.slice(0, 80), { permanent: true, direction: 'top' });
    }
  });
}
"""
