# The world weather map

"Show me the world's weather", "weather map of Asia", "weather map of India",
"show the wind", "show the clouds", "show the satellite". Sri Lanka (the
default) still opens the towns map, with rain day by day for 16 towns.

## What it shows

| Layer | What the colours are | Where it comes from |
|---|---|---|
| Temperature | °C at 2 m, -40 (lilac) to 50 (dark red) | Open-Meteo |
| Clouds | % of the sky covered, clear to white | Open-Meteo |
| Rain | mm in the hour, light blue to red | Open-Meteo |
| Wind | km/h at 10 m, plus moving streaks along the wind | Open-Meteo |
| Humidity | % relative humidity, dry brown to wet blue | Open-Meteo |
| Pressure | hPa at sea level: lows purple, highs orange | Open-Meteo |
| Satellite clouds now | infrared, every 10 minutes: cold (high) cloud tops are bright | NASA GIBS: GOES-West, GOES-East, Himawari |
| Satellite photo of yesterday | the true-colour picture of the whole world | NASA GIBS: VIIRS (NOAA-20, else S-NPP, else MODIS) |
| Rain radar | the latest radar picture, where countries share radar | RainViewer |
| Alerts | cyclones, floods, earthquakes... now | GDACS |

- **Every country**: a dot at its capital with the layer's number. Click it
  for everything (temperature, sky, clouds, rain, wind and its direction,
  gusts, humidity, pressure) and a 48-hour line of temperature and rain.
  Click anywhere else for the numbers filled in there.
- **The next 48 hours**: the slider moves in 3-hour steps; the play button
  runs them like a film, so you can watch a cyclone's rain and winds move.
- **The list**: every country, sorted by the layer (hottest first, windiest
  first...), with a search box. Click one to fly there.
- **By voice**, while it's open: "show the wind", "show the pressure",
  "show the satellite", "zoom in", "show Japan".

## How it works

1. **The places** (`knowledge/world_countries.json`): every country and
   territory with a capital, 244 of them, from GeoNames (CC BY 4.0).
2. **The seas**: a 15-degree grid, keeping only points more than 600 km
   from any capital: 183 points over the oceans, the poles and the deserts.
3. **One ask, in 5 parts** (`knowledge/world_weather.py`): Open-Meteo takes
   up to 100 places per request; 9 hourly values (temperature, humidity,
   rain, weather code, clouds, pressure, wind speed and direction, gusts) for
   the next 49 hours, kept every 3 hours. Each place costs one of Open-Meteo's
   free calls (10,000 a day, 600 a minute): the world is 427. The answer is
   kept on disk for an hour, so opening the map again is free.
4. **Filling in** (in the page): a 2-degree grid over the world; each cell
   takes its 8 nearest points, weighted by modified Shepard interpolation
   (weights fall to zero at the 9th point, so no seams). Wind is filled in
   as its east-west and north-south parts, so directions average properly.
   About 0.1 s, once.
5. **Drawing**: the colours are drawn on a canvas at a quarter of the screen's
   resolution and smoothed; the streaks are 4,500 particles carried by the
   wind, their trails fading (like earth.nullschool.net).

## Limits

- One point per country: a big country's other parts can be very different
  from its capital; the colours between points are an estimate. For a
  town's real forecast, ask "weather in Kandy".
- NASA's live infrared doesn't cover Europe and Africa (no geostationary
  satellite in GIBS there), and it is about 40-60 minutes behind.
- RainViewer's free radar stops at zoom 7 and covers only countries that
  share their radar.

## Ideas to take it further

- A finer grid where you look: ask Open-Meteo for a 1-degree grid over the
  visible area when you zoom in (about 400 points for a country).
- A globe (three.js, like the 3D explorer) instead of a flat map.
- Your own model: compare Open-Meteo's forecast for Colombo with what
  actually happened (the archive API), day after day, and learn its bias.

## Learn

- Open-Meteo forecast API: many places in one request, hourly variables
  (open-meteo.com/en/docs).
- Shepard's method of interpolation, and its modified form (Franke and
  Nielson, 1980).
- NASA GIBS (Global Imagery Browse Services): WMS and WMTS, time
  (nasa-gibs.github.io/gibs-api-docs).
- earth.nullschool.net (Cameron Beccario): how wind particles are drawn.
