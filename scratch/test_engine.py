import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from landing_zone_engine import LandingZoneEngine

def test():
    engine = LandingZoneEngine()
    print(f"Total zones indexed: {engine.total_zones}")
    res = engine.find_landing_spots(
        13.78, 75.66,
        max_scan_radius_km=10.0,
        weather={
            "wind": {"speed_kt": 10.5, "gust_kt": 15.0, "direction_deg": 240},
            "visibility_m": 8000,
            "precipitation": {"current_hour_mm": 0.0},
            "daylight_status": "day"
        }
    )
    print(f"Candidates in 10km: {res['total_candidates_in_range']}")
    print("Top 5 spots sample:")
    for s in res['spots'][:5]:
        print(f" - {s['zone_id']} | Dist: {s['distance_km']} km {s['compass']} ({s['bearing_deg']}°) | Area: {s['area_m2']} m² | Clear: {s['max_clear_diameter_m']} m | Radar: ({s['radar_x']}%, {s['radar_y']}%) | Status: {s['suitability']['status']} (Score: {s['suitability']['score']}%)")

if __name__ == "__main__":
    test()
