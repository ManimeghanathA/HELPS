import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"HELPS" in response.data
    assert b"Tactical Radar" in response.data
    assert b"Quick Region Presets" in response.data or b"preset-chip" in response.data

def test_api_landing_zones_endpoint(client):
    payload = {
        "latitude": 13.78,
        "longitude": 75.66,
        "radius_km": 10.0,
        "weather": {
            "wind": {"speed_kt": 10.0, "gust_kt": 15.0, "direction_deg": 240.0},
            "visibility_m": 9000.0,
            "precipitation": {"current_hour_mm": 0.0},
            "daylight_status": "day"
        }
    }
    response = client.post("/api/landing-zones", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["has_spots_in_range"] is True
    assert data["total_candidates_in_range"] > 0
    assert len(data["spots"]) > 0
    assert "radar_x" in data["spots"][0]
    assert "radar_y" in data["spots"][0]
    assert "suitability" in data["spots"][0]
    assert "rank" in data["spots"][0]
    assert data["spots"][0]["rank"] == 1
    # Verify sorted strictly descending by score
    scores = [s["suitability"]["score"] for s in data["spots"]]
    assert scores == sorted(scores, reverse=True)


def test_helicopter_model_and_mission_ranking(client):
    # Test Mi-17 heavy transport (requires 45m clearance) vs LUH (requires 24m)
    base_payload = {
        "latitude": 13.78,
        "longitude": 75.66,
        "radius_km": 10.0,
        "weather": {
            "wind": {"speed_kt": 12.0, "gust_kt": 18.0, "direction_deg": 180.0},
            "visibility_m": 8000.0,
            "precipitation": {"current_hour_mm": 0.0},
            "daylight_status": "day"
        }
    }

    # Query for Mi-17 (Heavy)
    payload_mi17 = {**base_payload, "helicopter_model": "mi_17", "mission_context": "safest_landing"}
    resp_mi17 = client.post("/api/landing-zones", json=payload_mi17)
    assert resp_mi17.status_code == 200
    data_mi17 = resp_mi17.get_json()
    assert data_mi17["helicopter"]["id"] == "mi_17"
    assert data_mi17["helicopter"]["min_clear_diameter_m"] == 45.0
    assert data_mi17["mission"]["id"] == "safest_landing"

    # Query for LUH (Light)
    payload_luh = {**base_payload, "helicopter_model": "hal_luh", "mission_context": "immediate_emergency"}
    resp_luh = client.post("/api/landing-zones", json=payload_luh)
    assert resp_luh.status_code == 200
    data_luh = resp_luh.get_json()
    assert data_luh["helicopter"]["id"] == "hal_luh"
    assert data_luh["helicopter"]["min_clear_diameter_m"] == 24.0
    assert data_luh["mission"]["id"] == "immediate_emergency"

