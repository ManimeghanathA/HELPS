"""
helicopter_profiles.py
----------------------
HELPS (Helicopter Emergency Landing Planning System)
Helicopter Operational Profiles and Mission Contexts Database.

Defines aircraft-specific operational specifications:
- Rotor diameter (m)
- Total length (m)
- Minimum safety clearance diameter (m)
- Minimum usable area (m²)
- Maximum allowable slope (degrees)
- Maximum allowable crosswind (kt)
- Maximum allowable gust (kt)
- Cruise speed for ETA calculation (kt)
- Surface type permissions
"""

from typing import Dict, Any

HELICOPTER_FLEET: Dict[str, Dict[str, Any]] = {
    "hal_dhruv": {
        "id": "hal_dhruv",
        "name": "HAL Dhruv (ALH Mk III / IV)",
        "category": "Medium Multi-role (5.5t)",
        "rotor_diameter_m": 13.2,
        "total_length_m": 15.9,
        "min_clear_diameter_m": 27.0,
        "min_area_m2": 1000.0,
        "max_slope_deg": 10.0,
        "max_crosswind_kt": 25.0,
        "max_gust_kt": 35.0,
        "cruise_speed_kt": 130.0,
        "surface_types": ["Grass", "Compact Soil", "Hardstand", "Gravel"],
        "description": "Standard twin-engine utility helicopter with high-altitude and all-weather tactical capability.",
    },
    "hal_prachand": {
        "id": "hal_prachand",
        "name": "HAL Prachand (LCH)",
        "category": "Dedicated Light Combat (5.8t)",
        "rotor_diameter_m": 13.3,
        "total_length_m": 15.8,
        "min_clear_diameter_m": 28.0,
        "min_area_m2": 1100.0,
        "max_slope_deg": 12.0,
        "max_crosswind_kt": 30.0,
        "max_gust_kt": 40.0,
        "cruise_speed_kt": 140.0,
        "surface_types": ["Grass", "Compact Soil", "Hardstand", "Gravel", "Rock"],
        "description": "Narrow-fuselage tandem combat rotorcraft engineered for desert, jungle and high-altitude operations.",
    },
    "hal_luh": {
        "id": "hal_luh",
        "name": "HAL LUH (Light Utility Helicopter)",
        "category": "Light Single-engine (3.15t)",
        "rotor_diameter_m": 11.6,
        "total_length_m": 11.4,
        "min_clear_diameter_m": 24.0,
        "min_area_m2": 800.0,
        "max_slope_deg": 10.0,
        "max_crosswind_kt": 22.0,
        "max_gust_kt": 32.0,
        "cruise_speed_kt": 125.0,
        "surface_types": ["Grass", "Compact Soil", "Hardstand", "Gravel"],
        "description": "Agile modern utility helicopter for search, rescue, reconnaissance, and tight-clearance operations.",
    },
    "mi_17": {
        "id": "mi_17",
        "name": "Mil Mi-17 V5",
        "category": "Heavy Transport (13.0t)",
        "rotor_diameter_m": 21.3,
        "total_length_m": 25.3,
        "min_clear_diameter_m": 45.0,
        "min_area_m2": 3200.0,
        "max_slope_deg": 7.0,
        "max_crosswind_kt": 20.0,
        "max_gust_kt": 30.0,
        "cruise_speed_kt": 120.0,
        "surface_types": ["Compact Soil", "Hardstand", "Firm Grass"],
        "description": "Heavy lift transport helicopter requiring wide approach corridors and large firm landing zones.",
    },
    "ec_135": {
        "id": "ec_135",
        "name": "Eurocopter EC135 / H135",
        "category": "Light Twin EMS / Utility (2.98t)",
        "rotor_diameter_m": 10.2,
        "total_length_m": 12.2,
        "min_clear_diameter_m": 21.0,
        "min_area_m2": 700.0,
        "max_slope_deg": 12.0,
        "max_crosswind_kt": 30.0,
        "max_gust_kt": 38.0,
        "cruise_speed_kt": 135.0,
        "surface_types": ["Grass", "Compact Soil", "Hardstand", "Gravel"],
        "description": "Compact twin-engine emergency medical and utility helicopter with shrouded Fenestron tail rotor.",
    }
}

MISSION_CONTEXTS: Dict[str, Dict[str, Any]] = {
    "immediate_emergency": {
        "id": "immediate_emergency",
        "name": "Immediate Emergency (Engine / Critical)",
        "priority_focus": "Minimum Travel Distance and Rapid Direct Approach",
        "weights": {
            "distance": 0.45,
            "clearance": 0.30,
            "weather": 0.15,
            "area": 0.10,
        },
        "description": "Prioritizes the closest reachable landing opportunity to minimize time in the air during critical emergencies.",
    },
    "safest_landing": {
        "id": "safest_landing",
        "name": "Safest Precautionary Landing",
        "priority_focus": "Maximum Clearance and Optimal Wind Alignment",
        "weights": {
            "clearance": 0.40,
            "weather": 0.30,
            "area": 0.20,
            "distance": 0.10,
        },
        "description": "Prioritizes wide obstacle-free zones and favorable headwind vectors for controlled precautionary landings.",
    },
    "medevac": {
        "id": "medevac",
        "name": "Medical / Casualty Evacuation (Medevac)",
        "priority_focus": "Surface Quality, Large Footprint and Clear Access",
        "weights": {
            "clearance": 0.35,
            "area": 0.30,
            "weather": 0.20,
            "distance": 0.15,
        },
        "description": "Prioritizes stable, spacious terrain for safe patient handling, medical transfers, and ground operations.",
    },
    "hybrid_balanced": {
        "id": "hybrid_balanced",
        "name": "Hybrid Operational Balance",
        "priority_focus": "Balanced Distance, Clearance, and Atmospheric Safety",
        "weights": {
            "clearance": 0.30,
            "distance": 0.30,
            "weather": 0.25,
            "area": 0.15,
        },
        "description": "Balanced composite multi-criteria evaluation across all physical and operational factors.",
    },
}


def get_helicopter_profile(model_id: str, custom_overrides: Dict[str, Any] = None) -> Dict[str, Any]:
    """Retrieve helicopter specifications with optional custom overrides."""
    base = HELICOPTER_FLEET.get(model_id, HELICOPTER_FLEET["hal_dhruv"]).copy()
    if custom_overrides:
        for k, v in custom_overrides.items():
            if v is not None and k in base:
                base[k] = v
    return base


def get_mission_context(context_id: str) -> Dict[str, Any]:
    """Retrieve mission context and weight configuration."""
    return MISSION_CONTEXTS.get(context_id, MISSION_CONTEXTS["hybrid_balanced"])
