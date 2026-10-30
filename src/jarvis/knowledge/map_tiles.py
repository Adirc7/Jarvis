"""The base map under the news and weather maps: tiles that need no account or key.

CARTO's dark tiles, used at first, began answering "API KEY REQUIRED" (30 Oct).
Now: OpenStreetMap's tiles, darkened in the browser to match Jarvis's look;
if those don't load (no network, or OpenStreetMap's usage limits), Esri's
street map, darkened the same way. Streets and satellite imagery are a click
away (the layer button, top right). Both ask only for the credit shown.
"""

CSS = (".dark-tiles { filter: invert(1) hue-rotate(180deg) brightness(0.9) contrast(0.9) saturate(0.6); }\n"
       ".leaflet-control-layers { background:#091522; color:#eaf5ff; border:1px solid #12314a; }\n")

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
"""
