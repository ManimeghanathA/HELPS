"""
weather_pipeline.py
--------------------
HELPS (Helicopter Emergency Landing Planning System)
Weather Data Acquisition Module — "Data Sources" / "Preprocessing" stage.

Given (latitude, longitude, timestamp), returns a normalized weather
observation record (confirmed schema, see WEATHER SCHEMA below) containing:
wind speed/gust/direction, visibility, precipitation (instant + trailing
24h), temperature, pressure, cloud cover, daylight status, the actual
observation time used, and source metadata.

Supports:
    - single-point lookups          -> fetch_weather(..., interpolate=True)
    - in-memory batch lookups       -> fetch_batch(...)
    - CSV-driven batch automation   -> fetch_from_csv(...) / CLI

PRIMARY SOURCE
    Open-Meteo (https://open-meteo.com)
    - No API key required, ~10,000 calls/day free tier
    - Forecast endpoint: covers ~92 days in the past -> 16 days forward
    - Archive endpoint: 1940 -> ~5 days ago, backed by ECMWF ERA5 /
      ERA5-Land reanalysis (citable in academic work)
    Endpoint is chosen automatically based on how far the requested
    timestamp is from "now".

DAYLIGHT STATUS
    Computed locally (no network call) via `astral` sun geometry
    (dawn/sunrise/sunset/dusk) -> "day" / "civil_twilight" / "night".

WEATHER SCHEMA (confirmed)
{
  "location": {"latitude": float, "longitude": float},
  "requested_timestamp_utc": "ISO8601",
  "observation_time_utc": "ISO8601",
  "wind": {
      "speed_kt": float,
      "gust_kt": float,
      "direction_deg": float
  },
  "visibility_m": float,
  "precipitation": {
      "current_hour_mm": float,
      "last_24h_mm": float
  },
  "temperature_c": float,
  "pressure_hpa": float,
  "cloud_cover_pct": float,
  "daylight_status": "day" | "civil_twilight" | "night",
  "source": {
      "provider": "Open-Meteo",
      "model": "open-meteo-forecast (blended model)" | "open-meteo-archive (ERA5 reanalysis)",
      "retrieved_at_utc": "ISO8601",
      "interpolated": {"applied": bool, "between": ["ISO8601", "ISO8601"] | null}
  }
}
On a per-point failure in batch mode, the record instead looks like:
{
  "location": {"latitude": float, "longitude": float},
  "requested_timestamp_utc": "ISO8601",
  "error": "message"
}

EXTENDING THIS MODULE (recommended next steps for HELPS)
    - Add a METAR cross-check (aviationweather.gov/api/data/metar) for
      points within ~15 nm of an airport for observed (not modeled)
      visibility/ceiling.
    - Add a disk/DB cache keyed on (round(lat,2), round(lon,2), hour)
      in your Spatial Storage stage.
    - Add proper retry/backoff + rate limiting for large batch runs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, date
from typing import Optional, List, Tuple, Iterable

import requests
from astral import LocationInfo
from astral.sun import sun

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

HOURLY_VARS = [
    "temperature_2m",
    "precipitation",
    "pressure_msl",
    "cloud_cover",
    "visibility",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]

FORECAST_PAST_LIMIT_DAYS = 92
FORECAST_FUTURE_LIMIT_DAYS = 16

# Simple politeness delay between batch requests (seconds) to stay well
# under Open-Meteo's free-tier rate limit on large runs.
BATCH_REQUEST_DELAY_SEC = 0.2
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.5


class WeatherFetchError(RuntimeError):
    pass


@dataclass
class Point:
    latitude: float
    longitude: float
    timestamp: datetime
    label: Optional[str] = None  # optional id/name passthrough (e.g. site_id)


class WeatherPipeline:
    def __init__(self, session: Optional[requests.Session] = None, timeout: int = 15):
        self.session = session or requests.Session()
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # Public API — single point
    # ------------------------------------------------------------------ #
    def fetch_weather(
        self, lat: float, lon: float, timestamp: datetime, interpolate: bool = True
    ) -> dict:
        """Returns one record matching the confirmed WEATHER SCHEMA."""
        self._validate_coordinates(lat, lon)
        ts = self._ensure_utc(timestamp)
        endpoint, model_label = self._select_endpoint(ts)

        window_start = (ts - timedelta(hours=24)).date()
        # A non-hour request needs the next hourly row as well (e.g. 11:00
        # for a 10:30 request).  This also handles 23:30 correctly.
        window_end = self._ceil_to_hour(ts).date()

        raw = self._call_open_meteo_with_retry(endpoint, lat, lon, window_start, window_end)
        rows = self._to_rows(raw)

        target_row, interpolation = self._value_at_timestamp(rows, ts, interpolate)
        precip_24h = self._sum_precip_last_24h(rows, ts)
        daylight = self._daylight_status(lat, lon, ts)

        return {
            "location": {"latitude": lat, "longitude": lon},
            "requested_timestamp_utc": ts.isoformat(),
            "observation_time_utc": target_row["time"].isoformat(),
            "wind": {
                "speed_kt": target_row.get("wind_speed_10m"),
                "gust_kt": target_row.get("wind_gusts_10m"),
                "direction_deg": target_row.get("wind_direction_10m"),
            },
            "visibility_m": target_row.get("visibility"),
            "precipitation": {
                "current_hour_mm": target_row.get("precipitation"),
                "last_24h_mm": precip_24h,
            },
            "temperature_c": target_row.get("temperature_2m"),
            "pressure_hpa": target_row.get("pressure_msl"),
            "cloud_cover_pct": target_row.get("cloud_cover"),
            "daylight_status": daylight,
            "source": {
                "provider": "Open-Meteo",
                "model": model_label,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "interpolated": interpolation,
            },
        }

    # ------------------------------------------------------------------ #
    # Public API — batch
    # ------------------------------------------------------------------ #
    def fetch_batch(self, points: Iterable[Point], verbose: bool = True) -> List[dict]:
        """
        Fetches weather for a list of Point objects, one record per point.
        Failures on individual points do not abort the batch — they are
        recorded inline with an "error" key so the run is auditable.
        """
        results = []
        points = list(points)
        total = len(points)

        for i, pt in enumerate(points, start=1):
            if verbose:
                label = f" [{pt.label}]" if pt.label else ""
                print(f"[{i}/{total}] fetching{label} lat={pt.latitude}, "
                      f"lon={pt.longitude}, ts={pt.timestamp.isoformat()}",
                      file=sys.stderr)
            try:
                record = self.fetch_weather(pt.latitude, pt.longitude, pt.timestamp)
                if pt.label is not None:
                    record["label"] = pt.label
                results.append(record)
            except Exception as exc:  # noqa: BLE001 - batch must keep going
                error_record = {
                    "location": {"latitude": pt.latitude, "longitude": pt.longitude},
                    "requested_timestamp_utc": self._ensure_utc(pt.timestamp).isoformat(),
                    "error": str(exc),
                }
                if pt.label is not None:
                    error_record["label"] = pt.label
                results.append(error_record)
                if verbose:
                    print(f"    ! failed: {exc}", file=sys.stderr)

            if i < total:
                time.sleep(BATCH_REQUEST_DELAY_SEC)

        return results

    # ------------------------------------------------------------------ #
    # Public API — CSV automation
    # ------------------------------------------------------------------ #
    def fetch_from_csv(
        self,
        input_csv_path: str,
        output_json_path: Optional[str] = None,
        lat_col: str = "latitude",
        lon_col: str = "longitude",
        ts_col: str = "timestamp",
        label_col: Optional[str] = "label",
    ) -> List[dict]:
        """
        Reads a CSV with columns [latitude, longitude, timestamp, (label)]
        — timestamp as ISO 8601 (e.g. 2026-09-04T10:30:00) — fetches
        weather for every row, and optionally writes the results as a
        JSON array to `output_json_path`.
        """
        points = []
        with open(input_csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row[ts_col])
                points.append(
                    Point(
                        latitude=float(row[lat_col]),
                        longitude=float(row[lon_col]),
                        timestamp=ts,
                        label=row.get(label_col) if label_col else None,
                    )
                )

        results = self.fetch_batch(points)

        if output_json_path:
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
            print(f"Wrote {len(results)} records -> {output_json_path}", file=sys.stderr)

        return results

    # ------------------------------------------------------------------ #
    # Endpoint selection
    # ------------------------------------------------------------------ #
    def _select_endpoint(self, ts: datetime) -> Tuple[str, str]:
        now = datetime.now(timezone.utc)
        if ts > now + timedelta(days=FORECAST_FUTURE_LIMIT_DAYS):
            raise WeatherFetchError(
                f"Timestamp is more than {FORECAST_FUTURE_LIMIT_DAYS} days in the "
                "future; Open-Meteo cannot forecast that far ahead."
            )

        # Interpolation and the 24-hour total require one preceding day of
        # data. Keep that complete request inside the forecast API's past
        # horizon; otherwise use the archive, which has the same hourly
        # response shape for this pipeline.
        if ts >= now - timedelta(days=FORECAST_PAST_LIMIT_DAYS - 1):
            return OPEN_METEO_FORECAST_URL, "open-meteo-forecast (blended model)"

        return OPEN_METEO_ARCHIVE_URL, "open-meteo-archive (ERA5 reanalysis)"

    # ------------------------------------------------------------------ #
    # Network call (with retry)
    # ------------------------------------------------------------------ #
    def _call_open_meteo_with_retry(
        self, endpoint: str, lat: float, lon: float, start: date, end: date
    ) -> dict:
        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return self._call_open_meteo(endpoint, lat, lon, start, end)
            except WeatherFetchError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
        raise last_exc

    def _call_open_meteo(
        self, endpoint: str, lat: float, lon: float, start: date, end: date
    ) -> dict:
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(HOURLY_VARS),
            "wind_speed_unit": "kn",
            "precipitation_unit": "mm",
            "timezone": "UTC",
        }
        resp = self.session.get(endpoint, params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise WeatherFetchError(
                f"Open-Meteo request failed ({resp.status_code}): {resp.text[:300]}"
            )
        data = resp.json()
        if "hourly" not in data:
            raise WeatherFetchError(f"Unexpected response shape: {data}")
        return data

    # ------------------------------------------------------------------ #
    # Response shaping
    # ------------------------------------------------------------------ #
    @staticmethod
    def _to_rows(raw: dict) -> List[dict]:
        hourly = raw["hourly"]
        times = hourly.get("time")
        if not isinstance(times, list) or not times:
            raise WeatherFetchError("Open-Meteo response has no hourly timestamps.")
        n = len(times)
        rows = []
        for i in range(n):
            row = {"time": datetime.fromisoformat(times[i]).replace(tzinfo=timezone.utc)}
            for var in HOURLY_VARS:
                values = hourly.get(var)
                if values is not None and len(values) != n:
                    raise WeatherFetchError(
                        f"Hourly variable {var!r} has {len(values)} values; expected {n}."
                    )
                row[var] = values[i] if values is not None else None
            rows.append(row)
        return sorted(rows, key=lambda row: row["time"])

    @staticmethod
    def _nearest_hour_row(rows: List[dict], ts: datetime) -> dict:
        if not rows:
            raise WeatherFetchError("No hourly data returned for this location/time.")
        return min(rows, key=lambda r: abs((r["time"] - ts).total_seconds()))

    @staticmethod
    def _ceil_to_hour(ts: datetime) -> datetime:
        """Return ts unchanged on the hour, otherwise the following hour."""
        if ts.minute == 0 and ts.second == 0 and ts.microsecond == 0:
            return ts
        return ts.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    @classmethod
    def _value_at_timestamp(
        cls, rows: List[dict], ts: datetime, interpolate: bool
    ) -> Tuple[dict, dict]:
        """Return either a raw nearest-hour row or values estimated at ``ts``."""
        if not rows:
            raise WeatherFetchError("No hourly data returned for this location/time.")

        exact = next((row for row in rows if row["time"] == ts), None)
        if exact is not None:
            return exact, {"applied": False, "between": None}

        if not interpolate:
            return cls._nearest_hour_row(rows, ts), {"applied": False, "between": None}

        before = [row for row in rows if row["time"] < ts]
        after = [row for row in rows if row["time"] > ts]
        if not before or not after:
            raise WeatherFetchError(
                "Cannot interpolate: Open-Meteo did not return hourly values on both "
                "sides of the requested timestamp."
            )

        left, right = before[-1], after[0]
        span_seconds = (right["time"] - left["time"]).total_seconds()
        if span_seconds <= 0:
            raise WeatherFetchError("Cannot interpolate duplicate or unordered hourly timestamps.")
        fraction = (ts - left["time"]).total_seconds() / span_seconds

        estimated = {"time": ts}
        for var in HOURLY_VARS:
            estimated[var] = cls._interpolate_value(
                left.get(var), right.get(var), fraction, circular=var == "wind_direction_10m"
            )
        return estimated, {
            "applied": True,
            "between": [left["time"].isoformat(), right["time"].isoformat()],
        }

    @staticmethod
    def _interpolate_value(
        left: Optional[float], right: Optional[float], fraction: float, circular: bool = False
    ) -> Optional[float]:
        """Linearly interpolate numeric values; directions use the shortest arc."""
        if left is None or right is None:
            return None
        if circular:
            delta = ((right - left + 180) % 360) - 180
            return round((left + fraction * delta) % 360, 2)
        return round(left + fraction * (right - left), 2)

    @staticmethod
    def _sum_precip_last_24h(rows: List[dict], ts: datetime) -> Optional[float]:
        # Hourly precipitation is an accumulation for a completed hour.  Do
        # not include a future bucket merely because the other fields were
        # interpolated using it.
        window = [
            r["precipitation"]
            for r in rows
            if r["precipitation"] is not None
            and ts - timedelta(hours=24) <= r["time"] <= ts
        ]
        return round(sum(window), 2) if window else None

    # ------------------------------------------------------------------ #
    # Daylight status (no network call)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _daylight_status(lat: float, lon: float, ts: datetime) -> str:
        loc = LocationInfo(latitude=lat, longitude=lon)
        try:
            s = sun(loc.observer, date=ts.date(), tzinfo=timezone.utc)
        except ValueError:
            return "day" if WeatherPipeline._solar_elevation(lat, lon, ts) > 0 else "night"

        if s["sunrise"] <= ts <= s["sunset"]:
            return "day"
        if (s["dawn"] <= ts < s["sunrise"]) or (s["sunset"] < ts <= s["dusk"]):
            return "civil_twilight"
        return "night"

    @staticmethod
    def _solar_elevation(lat: float, lon: float, ts: datetime) -> float:
        day_of_year = ts.timetuple().tm_yday
        decl = -23.44 * math.cos(math.radians(360 / 365 * (day_of_year + 10)))
        hour_angle = (ts.hour + ts.minute / 60 - 12) * 15 + lon
        lat_r, decl_r, ha_r = map(math.radians, (lat, decl, hour_angle))
        elevation = math.asin(
            math.sin(lat_r) * math.sin(decl_r)
            + math.cos(lat_r) * math.cos(decl_r) * math.cos(ha_r)
        )
        return math.degrees(elevation)

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ensure_utc(ts: datetime) -> datetime:
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    @staticmethod
    def _validate_coordinates(lat: float, lon: float) -> None:
        if not -90 <= lat <= 90:
            raise WeatherFetchError("Latitude must be between -90 and 90 degrees.")
        if not -180 <= lon <= 180:
            raise WeatherFetchError("Longitude must be between -180 and 180 degrees.")


# ---------------------------------------------------------------------- #
# CLI entry point
# ---------------------------------------------------------------------- #
def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HELPS weather acquisition — batch fetch from a CSV of points."
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Input CSV with columns: latitude, longitude, timestamp[, label]"
    )
    parser.add_argument(
        "--output", "-o", required=True,
        help="Output path for the JSON array of weather records."
    )
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    pipeline = WeatherPipeline()
    pipeline.fetch_from_csv(args.input, args.output)
