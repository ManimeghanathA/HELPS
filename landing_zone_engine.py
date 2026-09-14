"""
landing_zone_engine.py
----------------------
HELPS (Helicopter Emergency Landing Planning System)
Landing Zone Evaluation & Multi-Criteria Decision Engine.

Integrates:
1. Helicopter Current Coordinates (Spatial Query)
2. Helicopter Operational Specifications (Rotor diameter, Footprint, Max Slope, Crosswind limit)
3. Mission Context Prioritization (Emergency, Safest Precautionary, Medevac, Hybrid)
4. Current Weather & Wind Telemetry (Headwind/Crosswind vectors, Visibility, Rain rate)
5. Terrain Knowledge Database (4,130 GPKG validated operational zones)

Sorts candidate landing areas strictly from most suitable to least suitable in range.
"""

from __future__ import annotations

import math
import sqlite3
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from helicopter_profiles import (
    HELICOPTER_FLEET,
    MISSION_CONTEXTS,
    get_helicopter_profile,
    get_mission_context,
)

# WGS84 Constants
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_B = WGS84_A * (1.0 - WGS84_F)
WGS84_E_SQ = (WGS84_A**2 - WGS84_B**2) / (WGS84_A**2)
WGS84_E_PRIME_SQ = (WGS84_A**2 - WGS84_B**2) / (WGS84_B**2)
UTM_K0 = 0.9996


def utm_to_latlon(easting: float, northing: float, zone: int = 43, northern: bool = True) -> Tuple[float, float]:
    """Convert UTM coordinates (Zone 43N) to WGS84 Latitude and Longitude."""
    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)

    m = y / UTM_K0
    mu = m / (WGS84_A * (1.0 - WGS84_E_SQ / 4.0 - 3.0 * WGS84_E_SQ**2 / 64.0 - 5.0 * WGS84_E_SQ**3 / 256.0))
    e1 = (1.0 - math.sqrt(1.0 - WGS84_E_SQ)) / (1.0 + math.sqrt(1.0 - WGS84_E_SQ))

    j1 = 3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0
    j2 = 21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0
    j3 = 151.0 * e1**3 / 96.0
    j4 = 1097.0 * e1**4 / 512.0

    fp = mu + j1 * math.sin(2.0 * mu) + j2 * math.sin(4.0 * mu) + j3 * math.sin(6.0 * mu) + j4 * math.sin(8.0 * mu)

    sin_fp = math.sin(fp)
    cos_fp = math.cos(fp)
    tan_fp = math.tan(fp)

    c1 = WGS84_E_PRIME_SQ * cos_fp * cos_fp
    t1 = tan_fp * tan_fp
    n1 = WGS84_A / math.sqrt(1.0 - WGS84_E_SQ * sin_fp * sin_fp)
    r1 = WGS84_A * (1.0 - WGS84_E_SQ) / ((1.0 - WGS84_E_SQ * sin_fp * sin_fp) ** 1.5)
    d = x / (n1 * UTM_K0)

    # Latitude
    fact1 = n1 * tan_fp / r1
    fact2 = d * d / 2.0
    fact3 = (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1 * c1 - 9.0 * WGS84_E_PRIME_SQ) * (d**4) / 24.0
    fact4 = (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1 * t1 - 252.0 * WGS84_E_PRIME_SQ - 3.0 * c1 * c1) * (d**6) / 720.0
    lat = fp - fact1 * (fact2 - fact3 + fact4)

    # Longitude
    fact2 = d
    fact3 = (1.0 + 2.0 * t1 + c1) * (d**3) / 6.0
    fact4 = (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1 * c1 + 8.0 * WGS84_E_PRIME_SQ + 24.0 * t1 * t1) * (d**5) / 120.0
    lon = lon0 + (fact2 - fact3 + fact4) / cos_fp

    return math.degrees(lat), math.degrees(lon)


def parse_gpkg_point(blob: bytes) -> Optional[Tuple[float, float]]:
    """Extract (Easting, Northing) from a GeoPackage geometry blob."""
    if not blob or len(blob) < 8:
        return None
    flags = blob[3]
    envelope_type = (flags >> 1) & 0x07
    header_len = 8
    if envelope_type == 1:
        header_len += 32
    elif envelope_type in (2, 3):
        header_len += 48
    elif envelope_type == 4:
        header_len += 64

    wkb = blob[header_len:]
    if len(wkb) < 21:
        return None

    wkb_order = "<" if wkb[0] == 1 else ">"
    geom_type = struct.unpack(f"{wkb_order}I", wkb[1:5])[0]
    if geom_type % 1000 == 1:  # Point
        x, y = struct.unpack(f"{wkb_order}dd", wkb[5:21])
        return x, y
    return None


def parse_gpkg_polygon_and_bbox(blob: bytes) -> Tuple[Optional[List[float]], Optional[List[List[float]]]]:
    """Extract (bbox [lat_min, lon_min, lat_max, lon_max], exterior_polygon_coords [[lat, lon], ...]) from a GeoPackage geometry blob."""
    if not blob or len(blob) < 8:
        return None, None
    flags = blob[3]
    envelope_type = (flags >> 1) & 0x07
    header_len = 8
    bbox = None
    if envelope_type == 1:
        minx, maxx, miny, maxy = struct.unpack('<dddd', blob[8:40])
        lat_min, lon_min = utm_to_latlon(minx, miny, zone=43, northern=True)
        lat_max, lon_max = utm_to_latlon(maxx, maxy, zone=43, northern=True)
        bbox = [round(lat_min, 6), round(lon_min, 6), round(lat_max, 6), round(lon_max, 6)]
        header_len += 32
    elif envelope_type in (2, 3):
        header_len += 48
    elif envelope_type == 4:
        header_len += 64

    wkb = blob[header_len:]
    if len(wkb) < 9:
        return bbox, None

    wkb_order = "<" if wkb[0] == 1 else ">"
    geom_type = struct.unpack(f"{wkb_order}I", wkb[1:5])[0]
    polygon_coords = []

    if geom_type % 1000 == 3:  # Polygon
        num_rings = struct.unpack(f"{wkb_order}I", wkb[5:9])[0]
        offset = 9
        if num_rings > 0 and offset + 4 <= len(wkb):
            num_pts = struct.unpack(f"{wkb_order}I", wkb[offset:offset+4])[0]
            offset += 4
            for _ in range(num_pts):
                if offset + 16 > len(wkb):
                    break
                x, y = struct.unpack(f"{wkb_order}dd", wkb[offset:offset+16])
                offset += 16
                lat, lon = utm_to_latlon(x, y, zone=43, northern=True)
                polygon_coords.append([round(lat, 6), round(lon, 6)])

    # If bbox wasn't in envelope header, compute it from polygon points if available
    if not bbox and polygon_coords:
        lats = [pt[0] for pt in polygon_coords]
        lons = [pt[1] for pt in polygon_coords]
        bbox = [round(min(lats), 6), round(min(lons), 6), round(max(lats), 6), round(max(lons), 6)]

    return bbox, (polygon_coords if polygon_coords else None)


def haversine_distance_and_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
    """Compute distance in km and bearing in degrees (0..360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance_km = 6371.0 * c

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing_deg = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

    return distance_km, bearing_deg


def bearing_to_compass(bearing: float) -> str:
    """Convert bearing degrees to 16-point cardinal compass string."""
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(bearing / 22.5) % 16
    return points[idx]


class LandingZoneEngine:
    """
    Geospatial Decision Support Engine for Helicopter Emergency Landing Planning.
    """

    def __init__(self, data_root: Optional[Path] = None):
        if data_root is None:
            data_root = Path(__file__).resolve().parent / "data"
        self.data_root = data_root
        self.zones: List[Dict[str, Any]] = []
        self._load_datasets()

    def _load_datasets(self) -> None:
        """Load and index all validated zones from the terrain database."""
        self.zones = []
        gpkg_files = list(self.data_root.glob("processed/**/sentinel2/**/bhadra_final_open_land_zones.gpkg"))
        if not gpkg_files:
            gpkg_files = list(self.data_root.glob("**/*final_open_land_zones.gpkg"))

        for gpkg_path in gpkg_files:
            try:
                conn = sqlite3.connect(str(gpkg_path))
                cursor = conn.cursor()

                query = """
                SELECT f.zone_id, f.parent_candidate_id,
                       f.area_m2, f.length_m, f.width_m, f.max_clear_radius_m, f.max_clear_diameter_m,
                       m.geom AS center_geom, f.geom AS poly_geom
                FROM final_open_land_zones f
                LEFT JOIN maximum_clearance_centers m
                  ON f.zone_id = m.zone_id
                """
                cursor.execute(query)
                rows = cursor.fetchall()

                for row in rows:
                    (zone_id, parent_id, area_m2, length_m, width_m,
                     clear_r, clear_d, center_geom_blob, poly_geom_blob) = row

                    pt = parse_gpkg_point(center_geom_blob)
                    if not pt:
                        continue

                    easting, northing = pt
                    lat, lon = utm_to_latlon(easting, northing, zone=43, northern=True)

                    bbox, polygon_coords = parse_gpkg_polygon_and_bbox(poly_geom_blob)

                    # Estimate ground slope profile from clearance & dimensions
                    # Zones in flat open terrain have low slope (<4 deg), hillside zones have 6-10 deg
                    estimated_slope_deg = round(max(1.5, min(14.0, (120.0 / max(30.0, clear_d)) * 2.2)), 1)

                    self.zones.append({
                        "zone_id": zone_id,
                        "parent_id": parent_id,
                        "latitude": round(lat, 6),
                        "longitude": round(lon, 6),
                        "bbox": bbox,
                        "polygon": polygon_coords,
                        "easting": round(easting, 1),
                        "northing": round(northing, 1),
                        "area_m2": round(area_m2, 1),
                        "length_m": round(length_m, 1),
                        "width_m": round(width_m, 1),
                        "max_clear_diameter_m": round(clear_d, 1),
                        "max_clear_radius_m": round(clear_r, 1),
                        "slope_deg": estimated_slope_deg,
                        "surface": "Open Ground / Cleared Field",
                    })

                conn.close()
            except Exception as exc:
                print(f"[LandingZoneEngine] Warning loading {gpkg_path}: {exc}")

    @property
    def total_zones(self) -> int:
        return len(self.zones)

    def evaluate_zone_for_mission(
        self,
        zone: Dict[str, Any],
        dist_km: float,
        bearing_deg: float,
        heli_profile: Dict[str, Any],
        mission: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
        max_scan_radius_km: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Evaluate landing feasibility and multi-factor suitability score (0-100%)
        combining aircraft operational specifications, mission weights, and weather.
        """
        weights = mission.get("weights", {
            "clearance": 0.35,
            "distance": 0.30,
            "weather": 0.20,
            "area": 0.15,
        })

        clear_d = zone["max_clear_diameter_m"]
        area_m2 = zone["area_m2"]
        slope_deg = zone.get("slope_deg", 3.0)

        req_clear_d = heli_profile.get("min_clear_diameter_m", 25.0)
        req_area = heli_profile.get("min_area_m2", 1000.0)
        max_slope = heli_profile.get("max_slope_deg", 10.0)
        max_crosswind = heli_profile.get("max_crosswind_kt", 25.0)
        max_gust = heli_profile.get("max_gust_kt", 35.0)
        cruise_speed = heli_profile.get("cruise_speed_kt", 120.0)

        # 1. Clearance Footprint & Obstacle Safety (0 - 100)
        clearance_margin_m = round(clear_d - req_clear_d, 1)
        if clear_d < req_clear_d:
            # Below required rotorcraft clearance
            deficit_ratio = clear_d / req_clear_d
            clearance_score = max(5.0, deficit_ratio * 40.0)
            clearance_grade = "Restricted (Below Required Footprint)"
        else:
            # Meets or exceeds safety footprint
            excess = clear_d - req_clear_d
            clearance_score = min(100.0, 70.0 + (excess / req_clear_d) * 35.0)
            if excess >= req_clear_d * 0.8:
                clearance_grade = "Optimal (Wide Safety Buffer)"
            elif excess >= req_clear_d * 0.3:
                clearance_grade = "Good (Adequate Safety Margin)"
            else:
                clearance_grade = "Standard (Nominal Clearance)"

        # 2. Distance & Response Time Score (0 - 100)
        # Closer = higher score
        dist_ratio = max(0.0, min(1.0, dist_km / max_scan_radius_km))
        distance_score = max(10.0, (1.0 - dist_ratio) * 100.0)
        
        # Flight ETA calculation (seconds and minutes)
        speed_kmh = cruise_speed * 1.852
        flight_seconds = round((dist_km / speed_kmh) * 3600.0)
        if flight_seconds < 60:
            eta_str = f"{flight_seconds} sec"
        else:
            eta_str = f"{flight_seconds // 60} min {flight_seconds % 60} sec"

        # 3. Usable Area & Slope Score (0 - 100)
        area_ratio = min(2.5, area_m2 / req_area)
        area_score = min(100.0, 50.0 + area_ratio * 20.0)
        if slope_deg > max_slope:
            area_score = max(10.0, area_score - 40.0)

        # 4. Atmospheric & Wind Feasibility Score (0 - 100)
        weather_score = 90.0
        safety_flags = []
        adverse_flags = []
        recommended_approach = None

        if weather:
            wind = weather.get("wind", {})
            speed_kt = float(wind.get("speed_kt", 0.0) or 0.0)
            gust_kt = float(wind.get("gust_kt", 0.0) or 0.0)
            wind_dir = float(wind.get("direction_deg", 0.0) or 0.0)
            vis_m = float(weather.get("visibility_m", 10000.0) or 10000.0)
            precip = weather.get("precipitation", {})
            rain_mm = float(precip.get("current_hour_mm", 0.0) or 0.0)
            daylight = weather.get("daylight_status", "day")

            # Wind heading approach: Helicopters approach into the wind
            headwind_approach_deg = int(round((wind_dir + 180.0) % 360.0))
            wind_dir_int = int(round(wind_dir))
            recommended_approach = f"Approach {headwind_approach_deg:03d}° into {wind_dir_int:03d}° wind at {speed_kt:.0f} kt"

            # Check gust limits
            if gust_kt > max_gust:
                weather_score -= 40.0
                adverse_flags.append(f"Gusts {gust_kt:.0f} kt exceed {heli_profile['name']} limit ({max_gust:.0f} kt)")
            elif speed_kt > max_crosswind:
                weather_score -= 25.0
                adverse_flags.append(f"Wind {speed_kt:.0f} kt near operating envelope limit")
            elif speed_kt <= 15.0 and gust_kt <= 20.0:
                safety_flags.append("Favorable surface wind conditions")

            # Visibility checks
            if vis_m < 1500.0:
                weather_score -= 35.0
                adverse_flags.append(f"Low visibility ({vis_m:.0f} m)")
            elif vis_m < 4000.0:
                weather_score -= 15.0
                safety_flags.append(f"Marginal visibility ({vis_m:.0f} m)")

            # Rain checks
            if rain_mm > 5.0:
                weather_score -= 20.0
                adverse_flags.append(f"Heavy rain active ({rain_mm:.1f} mm/h)")

            # Daylight checks
            if daylight == "night":
                weather_score -= 15.0
                safety_flags.append("Night operations - searchlight / NVG required")

        weather_score = max(5.0, min(100.0, weather_score))

        # 5. Composite Mission Weighted Score
        composite_score = (
            clearance_score * weights.get("clearance", 0.35)
            + distance_score * weights.get("distance", 0.30)
            + weather_score * weights.get("weather", 0.20)
            + area_score * weights.get("area", 0.15)
        )

        # Critical failure penalty
        if clear_d < req_clear_d or (weather and weather_score < 40.0):
            composite_score = min(composite_score, 45.0)

        final_score = int(round(max(10.0, min(99.0, composite_score))))

        # Status categorization
        if final_score >= 82 and clear_d >= req_clear_d and not adverse_flags:
            status = "Optimal / Recommended"
            status_code = "optimal"
            summary_badge = "Optimal"
        elif final_score >= 60 and clear_d >= req_clear_d * 0.9:
            status = "Acceptable / Caution"
            status_code = "caution"
            summary_badge = "Caution"
        else:
            status = "Adverse / Restricted"
            status_code = "warning"
            summary_badge = "Restricted"

        # Operational recommendation rationale
        if clearance_margin_m >= 0:
            briefing = f"+{clearance_margin_m:.1f} m safety clearance for {heli_profile['name']}. ETA {eta_str}. {recommended_approach or 'Clear corridor'}."
        else:
            briefing = f"Clearance shortfall of {abs(clearance_margin_m):.1f} m for {heli_profile['name']}. Marginal landing site."

        return {
            "score": final_score,
            "status": status,
            "status_code": status_code,
            "summary_badge": summary_badge,
            "clearance_margin_m": clearance_margin_m,
            "clearance_grade": clearance_grade,
            "eta_seconds": flight_seconds,
            "eta_str": eta_str,
            "recommended_approach": recommended_approach,
            "briefing": briefing,
            "safety_flags": safety_flags,
            "adverse_flags": adverse_flags,
            "subscores": {
                "clearance": round(clearance_score, 1),
                "distance": round(distance_score, 1),
                "weather": round(weather_score, 1),
                "area": round(area_score, 1),
            }
        }

    def find_landing_spots(
        self,
        query_lat: float,
        query_lon: float,
        max_scan_radius_km: float = 10.0,
        max_results: int = 30,
        weather: Optional[Dict[str, Any]] = None,
        helicopter_model: str = "hal_dhruv",
        custom_specs: Optional[Dict[str, Any]] = None,
        mission_context_id: str = "immediate_emergency",
    ) -> Dict[str, Any]:
        """
        Retrieve nearby operational zones, evaluate against helicopter specifications
        and mission priorities, and return sorted strictly from most suitable to least.
        """
        heli_profile = get_helicopter_profile(helicopter_model, custom_specs)
        mission = get_mission_context(mission_context_id)

        evaluated_spots = []
        nearest_distance_km = float("inf")
        nearest_spot = None

        for zone in self.zones:
            dist_km, bearing_deg = haversine_distance_and_bearing(
                query_lat, query_lon, zone["latitude"], zone["longitude"]
            )

            if dist_km < nearest_distance_km:
                nearest_distance_km = dist_km
                nearest_spot = (zone, dist_km, bearing_deg)

            if dist_km <= max_scan_radius_km:
                suitability = self.evaluate_zone_for_mission(
                    zone=zone,
                    dist_km=dist_km,
                    bearing_deg=bearing_deg,
                    heli_profile=heli_profile,
                    mission=mission,
                    weather=weather,
                    max_scan_radius_km=max_scan_radius_km,
                )

                rad = math.radians(bearing_deg)
                norm_dist = min(1.0, dist_km / max_scan_radius_km)
                radar_x = round(50.0 + norm_dist * 44.0 * math.sin(rad), 2)
                radar_y = round(50.0 - norm_dist * 44.0 * math.cos(rad), 2)

                evaluated_spots.append({
                    **zone,
                    "distance_km": round(dist_km, 2),
                    "bearing_deg": round(bearing_deg, 1),
                    "compass": bearing_to_compass(bearing_deg),
                    "radar_x": radar_x,
                    "radar_y": radar_y,
                    "suitability": suitability,
                })

        # Sort STRICTLY from Most Suitable (Rank 1 / Highest Score) to Least Suitable
        evaluated_spots.sort(key=lambda s: (-s["suitability"]["score"], s["distance_km"]))

        # Assign explicit rank numbers
        for rank_idx, spot in enumerate(evaluated_spots, start=1):
            spot["rank"] = rank_idx

        selected_spots = evaluated_spots[:max_results]

        return {
            "query_location": {"latitude": query_lat, "longitude": query_lon},
            "helicopter": {
                "id": heli_profile["id"],
                "name": heli_profile["name"],
                "category": heli_profile["category"],
                "rotor_diameter_m": heli_profile["rotor_diameter_m"],
                "min_clear_diameter_m": heli_profile["min_clear_diameter_m"],
                "max_slope_deg": heli_profile["max_slope_deg"],
                "max_crosswind_kt": heli_profile["max_crosswind_kt"],
                "cruise_speed_kt": heli_profile["cruise_speed_kt"],
            },
            "mission": {
                "id": mission["id"],
                "name": mission["name"],
                "priority_focus": mission["priority_focus"],
            },
            "scan_radius_km": max_scan_radius_km,
            "total_candidates_in_range": len(evaluated_spots),
            "spots": selected_spots,
            "nearest_available_distance_km": round(nearest_distance_km, 2) if nearest_spot else None,
            "has_spots_in_range": len(selected_spots) > 0,
            "available_database_total": len(self.zones),
        }
