from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from landing_zone_engine import LandingZoneEngine
from weather_pipeline import WeatherFetchError, WeatherPipeline

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
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
    return render_template("index.html")


@app.get("/api/operational-regions")
def operational_regions():
    """Return operational region boundaries across India with user-specified status."""
    import json
    regions_file = Path(__file__).parent / "data" / "raw" / "Bhadra" / "bhadra_entire_region.geojson"
    bhadra_coords = []
    if regions_file.exists():
        try:
            with open(regions_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("features"):
                    bhadra_coords = data["features"][0]["geometry"]["coordinates"]
        except Exception:
            pass

    # Exact specified operational regions
    features = [
        {
            "type": "Feature",
            "properties": {
                "id": "bhadra_reserve",
                "name": "Bhadra Wildlife Sanctuary & Tiger Reserve",
                "state": "Karnataka",
                "status": "ready",
                "status_label": "DATA AVAILABLE (READY)",
                "color": "#22c55e",
                "sites_count": 2694,
                "center": [13.6800, 75.6400],
                "description": "Entire Bhadra operational territory. 2,694 verified candidate landing sites extracted from Sentinel-2 & DEM terrain pipelines ready for decision making."
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": bhadra_coords if bhadra_coords else [[[75.50, 13.35], [75.82, 13.35], [75.82, 13.82], [75.50, 13.82], [75.50, 13.35]]]
            }
        },
        {
            "type": "Feature",
            "properties": {
                "id": "wayanad_district",
                "name": "Wayanad Highland Sector",
                "state": "Kerala",
                "status": "in_progress",
                "status_label": "IN PROGRESS (DATA PROCESSING)",
                "color": "#eab308",
                "sites_count": 620,
                "center": [11.6854, 76.1320],
                "description": "Wayanad terrain, slope assessment, and vegetation classification currently in progress."
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[75.85, 11.50], [76.32, 11.52], [76.42, 11.88], [76.10, 12.02], [75.82, 11.78], [75.85, 11.50]]]
            }
        },
        {
            "type": "Feature",
            "properties": {
                "id": "ladakh_region",
                "name": "Ladakh High-Altitude Sector",
                "state": "Ladakh",
                "status": "under_consideration",
                "status_label": "UNDER CONSIDERATION",
                "color": "#ef4444",
                "sites_count": 0,
                "center": [34.1526, 77.5771],
                "description": "High-altitude mountain landing sectors under airspace feasibility and density altitude clearance."
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[76.80, 33.50], [78.60, 33.70], [78.90, 35.20], [77.10, 35.10], [76.80, 33.50]]]
            }
        },
        {
            "type": "Feature",
            "properties": {
                "id": "himalayas_sector",
                "name": "Himalayas Mountain Range",
                "state": "Himachal / Uttarakhand",
                "status": "under_consideration",
                "status_label": "UNDER CONSIDERATION",
                "color": "#ef4444",
                "sites_count": 0,
                "center": [31.1048, 78.1700],
                "description": "Extreme terrain Himalayan operational corridor under airspace and steep terrain evaluation."
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[77.00, 30.50], [80.20, 29.80], [80.90, 31.40], [77.60, 32.60], [77.00, 30.50]]]
            }
        }
    ]

    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })


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
        poly = z.get("polygon")
        if not poly or len(poly) < 3:
            continue
        # GeoJSON uses [lon, lat]
        coords = [[pt[1], pt[0]] for pt in poly]
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
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            }
        })

    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })


@app.get("/api/pipeline-zones")
def pipeline_zones():
    """Serve the final landing zone annotations generated by the latest pipeline run."""
    runs_dir = Path(__file__).parent / "data" / "runs"
    if runs_dir.exists():
        run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir() and d.name != "archive"],
                          key=lambda d: d.name, reverse=True)
        for d in run_dirs:
            geojson_path = d / "final_zones.geojson"
            if geojson_path.exists():
                return send_file(geojson_path, mimetype="application/geo+json")
    return all_gpkg_zones()


@app.get("/api/pipeline-run-info")
def pipeline_run_info():
    """Return metadata and summary of the latest pipeline run."""
    runs_dir = Path(__file__).parent / "data" / "runs"
    if runs_dir.exists():
        run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir() and d.name != "archive"],
                          key=lambda d: d.name, reverse=True)
        for d in run_dirs:
            run_json = d / "run.json"
            if run_json.exists():
                import json
                try:
                    with open(run_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data["run_id"] = d.name
                        return jsonify(data)
                except Exception:
                    pass
    return jsonify({"status": "no_runs", "run_id": None})


@app.post("/api/reload-zones")
def reload_zones():
    """Reload landing zones from canonical GPKG files without restarting the Flask server."""
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
    app.run(debug=True, host="127.0.0.1", port=5000)

