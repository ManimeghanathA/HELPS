# HELPS Weather Data Module — README

Weather acquisition component for the HELPS (Helicopter Emergency Landing
Planning System) pipeline. Given a `(latitude, longitude, timestamp)`, it
returns a normalized JSON record of the conditions at that point in time.

---

## 1. Setup

```bash
pip install -r requirements.txt
```

Dependencies: `requests` (HTTP calls), `astral` (sunrise/sunset/twilight math).
No API key is required for any data source used here.

You also need **Python 3.10+** installed. On Windows, verify it with
`py --version`; then use `py -3 -m pip install -r requirements.txt` and
`py -3 weather_pipeline.py ...` if the `python` command is not available.

---

## 2. Feature reference

| Field | Unit | How it's acquired |
|---|---|---|
| `location.latitude` / `longitude` | decimal degrees | Passed in by you — the query point. |
| `requested_timestamp_utc` | ISO 8601, UTC | The timestamp you asked for. |
| `observation_time_utc` | ISO 8601, UTC | The exact time the returned values represent. With interpolation on (default), this equals `requested_timestamp_utc`. With it off, this is the nearest hourly bucket instead. |
| `wind.speed_kt` | knots | Open-Meteo hourly variable `wind_speed_10m` (10m above ground), requested directly in knots via `wind_speed_unit=kn`. |
| `wind.gust_kt` | knots | Open-Meteo hourly variable `wind_gusts_10m`. |
| `wind.direction_deg` | degrees, 0–360 (direction wind is blowing **from**) | Open-Meteo hourly variable `wind_direction_10m`. |
| `visibility_m` | meters | Open-Meteo hourly variable `visibility` — model-derived, not a ground observation (see §5 caveat). |
| `precipitation.current_hour_mm` | mm | Open-Meteo hourly variable `precipitation`. |
| `precipitation.last_24h_mm` | mm | Computed locally: sum of the `precipitation` values across the 24 hourly rows ending at the target hour. Not interpolated — it's a rolling accumulation. |
| `temperature_c` | °C | Open-Meteo hourly variable `temperature_2m` (2m above ground). |
| `pressure_hpa` | hPa | Open-Meteo hourly variable `pressure_msl` (mean sea level pressure). |
| `cloud_cover_pct` | % (0–100) | Open-Meteo hourly variable `cloud_cover`. |
| `daylight_status` | `"day"` / `"civil_twilight"` / `"night"` | Computed locally with the `astral` library from lat/lon/date — no API call. Classified against sunrise/sunset (day) and dawn/dusk (civil twilight) for the exact requested timestamp. |
| `source.provider` | text | Always `"Open-Meteo"` currently. |
| `source.model` | text | Which Open-Meteo endpoint answered: `"open-meteo-forecast (blended model)"` for recent/near-future dates, or `"open-meteo-archive (ERA5 reanalysis)"` for older historical dates. |
| `source.retrieved_at_utc` | ISO 8601, UTC | When your pipeline made the request (i.e. "now," not the observation time). |
| `source.interpolated` | object | `{"applied": bool, "between": [t1, t2] or null}` — see §4. |

---

## 3. Where the data actually comes from

**Open-Meteo** (`open-meteo.com`) is the single upstream source for every
field except `daylight_status` (computed) and `precipitation.last_24h_mm`
(derived by summation, not a separate fetch).

- **Forecast endpoint** (`api.open-meteo.com/v1/forecast`) — used when your
  timestamp is within ~92 days in the past to 16 days in the future. This
  blends live numerical weather model output with recent-past data.
- **Archive endpoint** (`archive-api.open-meteo.com/v1/archive`) — used for
  anything older than that. Backed by **ECMWF ERA5 / ERA5-Land reanalysis**,
  a scientifically citable dataset (useful for your literature review /
  methodology section if needed) covering 1940 to ~5 days ago.

The pipeline picks the right endpoint automatically based on the timestamp
— you never choose it manually.

---

## 4. Reducing the time gap (interpolation)

Open-Meteo's hourly model/reanalysis values are bucketed on the hour: `10:00`, `11:00`, etc.
There's no native `10:30` row. Originally this module snapped to the
**nearest** hour, which is why a `10:30` request returned `10:00` data (a
30-minute gap in the worst case).

**Fixed by default now.** `fetch_weather(..., interpolate=True)` — the
default — linearly interpolates between the two bounding hourly rows so the
returned values estimate the condition **exactly at your requested
timestamp**, not the nearest bucket:

- Continuous values (temperature, pressure, cloud cover, visibility, wind
  speed/gust) — straight linear interpolation.
- Wind direction — **circular** interpolation (shortest angular path), so
  interpolating between e.g. 350° and 10° correctly passes through 360°/0°
  instead of the wrong way around through 180°.
- `precipitation.current_hour_mm` — linearly interpolated between adjacent
  hourly totals too, but this is an approximation since precipitation is
  fundamentally an hourly-accumulated quantity, not an instantaneous one.
  Treat it as indicative, not exact.

With interpolation on, `observation_time_utc` equals `requested_timestamp_utc`
exactly, and `source.interpolated` tells you which two source hours were
blended (`{"applied": true, "between": ["...10:00...", "...11:00..."]}`).

**If you want the old behavior** (raw, un-modeled hourly value — e.g. for
auditing against the exact source data), call:
```python
pipeline.fetch_weather(lat, lon, timestamp, interpolate=False)
```

**Hard limit:** hourly is the finest resolution the ERA5 archive offers —
there's no way to get sub-hourly precision for historical dates beyond the
~92-day forecast lookback window, no matter the source; interpolation is
the practical ceiling there. For very recent/near-future dates, Open-Meteo
does offer a `minutely_15` product on select variables — worth adding as a
future enhancement if you specifically need forecast-window precision
finer than interpolation provides.

---

## 5. Known caveats

- **Visibility is modeled, not observed.** For ground-truth visibility,
  cross-checking against METAR reports (`aviationweather.gov`, also
  keyless) near candidate landing sites within a few nautical miles of an
  airport would be more trustworthy — not yet implemented here.
- **Precipitation interpolation is approximate** (see §4) — don't treat
  `current_hour_mm` as a precise instantaneous rain rate.
- **Batch runs** insert a small delay between requests (0.2s) to stay well
  under Open-Meteo's free-tier rate limit; large batches (thousands of DEM
  grid points) will take proportionally longer.

---

## 6. Usage

**Web frontend:** start the local weather console with:
```bash
py -3 -m pip install -r requirements.txt
py -3 app.py
```
Then open http://127.0.0.1:5000 and enter latitude, longitude, and a UTC
timestamp. The dashboard displays the full normalized record returned by the
pipeline. The browser calls `POST /api/weather` with `latitude`, `longitude`,
and an ISO 8601 `timestamp`.

**Single point:** save this in a `.py` file (for example `run_single.py`) and
run it with Python — do not paste the Python lines directly into PowerShell.
```python
from datetime import datetime
from weather_pipeline import WeatherPipeline

pipeline = WeatherPipeline()
record = pipeline.fetch_weather(12.9698, 79.1559, datetime(2026, 9, 4, 10, 30))
```

**Batch from CSV** (columns: `latitude, longitude, timestamp, label`):
```bash
py -3 weather_pipeline.py --input points.csv --output weather_data.json
```
