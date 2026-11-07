from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from landing_zone_engine import LandingZoneEngine
from weather_pipeline import WeatherFetchError, WeatherPipeline

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
pipeline = WeatherPipeline()
landing_engine = LandingZoneEngine()


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/")
def index():
    return render_template("unified.html")


@app.get("/legacy")
def legacy():
    return render_template("index.html")

@app.get("/workspace/<role>")
def workspace(role):
    if role not in ("application", "engineer"):
        return jsonify(error="Unknown role"), 404
    return render_template("unified.html")

from scripts.ui.api import register_api
register_api(app, Path(__file__).parent, legacy_authoring=False)
from scripts.ui.unified_api import register_unified_api
from scripts.ui.analysis_jobs import register_analysis_api
register_unified_api(app, Path(__file__).parent)
register_analysis_api(app, Path(__file__).parent)

@app.get("/api/operational-regions")
def operational_regions():
    """Display the selected Bhadra package and any explicitly accepted uploads."""
    from scripts.ui.unified_api import registered_region_features

    return jsonify(type="FeatureCollection", features=registered_region_features(Path(__file__).parent))


@app.post("/api/weather")
def weather():
    payload = request.get_json(silent=True) or {}

    try:
        latitude = float(payload["latitude"])
        longitude = float(payload["longitude"])

        timestamp_value = str(payload["timestamp"]).strip()

        if not timestamp_value:
            raise ValueError("A UTC timestamp is required.")

        timestamp_value = timestamp_value.replace("Z", "+00:00")

        # Parse ISO 8601 timestamp
        timestamp = datetime.fromisoformat(timestamp_value)

        if timestamp.year < 1000 or timestamp.year > 9999:
            raise ValueError(
                "Invalid year. The year must contain exactly 4 digits."
            )

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)

        helicopter_model = payload.get("helicopter_model", "hal_dhruv")
        mission_context = payload.get("mission_context", "hybrid_balanced")
        custom_specs = payload.get("custom_specs")

        record = pipeline.fetch_weather(
            latitude,
            longitude,
            timestamp
        )

        # Evaluate landing zones around query coordinates with live weather record and helicopter profile
        landing_data = landing_engine.find_landing_spots(
            query_lat=latitude,
            query_lon=longitude,
            max_scan_radius_km=10.0,
            max_results=30,
            weather=record,
            helicopter_model=helicopter_model,
            mission_context_id=mission_context,
            custom_specs=custom_specs
        )
        record["landing_zones"] = landing_data

        return jsonify(record)

    except KeyError as exc:
        return jsonify({
            "error": f"Missing field: {exc.args[0]}"
        }), 400

    except (TypeError, ValueError) as exc:
        return jsonify({
            "error": f"Invalid input: {exc}"
        }), 400

    except WeatherFetchError as exc:
        return jsonify({
            "error": str(exc)
        }), 422

    except Exception as exc:  # noqa: BLE001
        return jsonify({
            "error": f"Weather lookup failed: {exc}"
        }), 502


@app.post("/api/landing-zones")
def landing_zones():
    payload = request.get_json(silent=True) or {}
    try:
        latitude = float(payload["latitude"])
        longitude = float(payload["longitude"])
        radius_km = float(payload.get("radius_km", 10.0))
        weather_data = payload.get("weather")
        helicopter_model = payload.get("helicopter_model", "hal_dhruv")
        mission_context = payload.get("mission_context", "hybrid_balanced")
        custom_specs = payload.get("custom_specs")

        results = landing_engine.find_landing_spots(
            query_lat=latitude,
            query_lon=longitude,
            max_scan_radius_km=radius_km,
            max_results=30,
            weather=weather_data,
            helicopter_model=helicopter_model,
            mission_context_id=mission_context,
            custom_specs=custom_specs
        )
        return jsonify(results)
    except (TypeError, ValueError, KeyError) as exc:
        return jsonify({"error": f"Invalid input: {exc}"}), 400
    except Exception as exc:
        return jsonify({"error": f"Landing zone lookup failed: {exc}"}), 500


@app.get("/api/gpkg-zones")
def all_gpkg_zones():
    """Return landable zones directly from the GPKG dataset as a GeoJSON FeatureCollection."""
    features = []
    for z in landing_engine.zones:
        geometry = z.get("geometry")
        if not geometry:
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "zone_id": z["zone_id"],
                "area_m2": z["area_m2"],
                "length_m": z["length_m"],
                "width_m": z["width_m"],
                "max_clear_diameter_m": z["max_clear_diameter_m"],
                "slope_deg": z.get("slope_deg", 3.0),
                "center_lat": z["latitude"],
                "center_lon": z["longitude"]
            },
            "geometry": geometry
        })

    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })


@app.get("/api/pipeline-zones")
def pipeline_zones():
    """Serve the same loaded, quarantine-filtered geometry used by map/ranking."""
    return all_gpkg_zones()


@app.get("/api/pipeline-run-info")
def pipeline_run_info():
    """Describe the loaded geometry; newly completed runs require engine reload."""
    return jsonify(landing_engine.active_run_info)


@app.post("/api/reload-zones")
def reload_zones():
    """Reload landing zones from canonical GPKG files without restarting the Flask server."""
    from urllib.parse import urlparse
    origin = request.headers.get('Origin')
    if request.headers.get('X-HELPS-Role') != 'engineer' or request.remote_addr not in ('127.0.0.1','::1') or (origin and urlparse(origin).netloc != request.host):
        return jsonify(error='Local Data Engineer role required'), 403
    try:
        landing_engine._load_datasets()
        return jsonify({
            "status": "reloaded",
            "total_zones": landing_engine.total_zones
        }), 200
    except Exception as exc:
        return jsonify({
            "error": f"Failed to reload landing zones: {exc}"
        }), 500



if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)

