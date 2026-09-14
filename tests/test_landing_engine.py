import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from landing_zone_engine import LandingZoneEngine, haversine_distance_and_bearing, utm_to_latlon

def test_utm_to_latlon_accuracy():
    # Test UTM 43N coordinate conversion against known Bhadra ground truth
    easting = 571555.0
    northing = 1527920.0
    lat, lon = utm_to_latlon(easting, northing, zone=43, northern=True)
    assert 13.81 < lat < 13.83
    assert 75.65 < lon < 75.67

def test_haversine_distance_and_bearing():
    # Test distance between two known coordinates
    dist_km, bearing = haversine_distance_and_bearing(13.0, 75.0, 13.0, 75.1)
    assert 10.0 < dist_km < 11.5
    assert 88.0 < bearing < 92.0

def test_landing_engine_indexing():
    engine = LandingZoneEngine()
    assert engine.total_zones > 0
    assert engine.total_zones == 8275

def test_landing_engine_query_and_suitability():
    engine = LandingZoneEngine()
    
    # Query within Bhadra North
    results = engine.find_landing_spots(
        query_lat=13.78,
        query_lon=75.66,
        max_scan_radius_km=10.0,
        weather={
            "wind": {"speed_kt": 12.0, "gust_kt": 16.0, "direction_deg": 270.0},
            "visibility_m": 10000.0,
            "precipitation": {"current_hour_mm": 0.0},
            "daylight_status": "day"
        }
    )
    
    assert results["has_spots_in_range"] is True
    assert results["total_candidates_in_range"] > 0
    assert len(results["spots"]) > 0
    
    first_spot = results["spots"][0]
    assert "distance_km" in first_spot
    assert "bearing_deg" in first_spot
    assert "radar_x" in first_spot
    assert "radar_y" in first_spot
    assert "suitability" in first_spot
    assert first_spot["suitability"]["score"] >= 70
    assert first_spot["distance_km"] <= 10.0

def test_landing_engine_adverse_weather():
    engine = LandingZoneEngine()
    
    # Severe weather query (high wind, low visibility, heavy rain)
    results = engine.find_landing_spots(
        query_lat=13.78,
        query_lon=75.66,
        max_scan_radius_km=10.0,
        weather={
            "wind": {"speed_kt": 35.0, "gust_kt": 48.0, "direction_deg": 90.0},
            "visibility_m": 800.0,
            "precipitation": {"current_hour_mm": 12.0},
            "daylight_status": "night"
        }
    )
    
    first_spot = results["spots"][0]
    assert first_spot["suitability"]["status_code"] == "warning"
    assert first_spot["suitability"]["score"] < 50
