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
from copy import deepcopy
import math

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
        "total_length_m": 13.85,
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

# Heuristic research priorities, not learned/calibrated safety probabilities.
# Temporal policy reserves 0.10; prior factor ratios are preserved within 0.90.
# Ranking multiplies temporal weight by historical support before normalization.
MISSION_CONTEXTS: Dict[str, Dict[str, Any]] = {
    "immediate_emergency": {
        "id": "immediate_emergency",
        "name": "Immediate Emergency (Engine / Critical)",
        "priority_focus": "Minimum Travel Distance and Rapid Direct Approach",
        "weights": {
            "distance": 0.405,
            "clearance": 0.270,
            "weather": 0.135,
            "area": 0.090,
            "temporal": 0.10,
        },
        "description": "Prioritizes the closest reachable landing opportunity to minimize time in the air during critical emergencies.",
    },
    "safest_landing": {
        "id": "safest_landing",
        "name": "Safest Precautionary Landing",
        "priority_focus": "Maximum Clearance and Optimal Wind Alignment",
        "weights": {
            "clearance": 0.225,
            "weather": 0.180,
            "area": 0.090,
            "distance": 0.045,
            "slope": 0.135,
            "roughness": 0.090,
            "openness": 0.090,
            "water": 0.045,
            "temporal": 0.10,
        },
        "description": "Prioritizes wide obstacle-free zones and favorable headwind vectors for controlled precautionary landings.",
    },
    "medevac": {
        "id": "medevac",
        "name": "Medical / Casualty Evacuation (Medevac)",
        "priority_focus": "Surface Quality, Large Footprint and Clear Access",
        "weights": {
            "access": 0.315,
            "clearance": 0.180,
            "area": 0.135,
            "weather": 0.135,
            "distance": 0.135,
            "temporal": 0.10,
        },
        "description": "Prioritizes stable, spacious terrain for safe patient handling, medical transfers, and ground operations.",
    },
    "hybrid_balanced": {
        "id": "hybrid_balanced",
        "name": "Hybrid Operational Balance",
        "priority_focus": "Balanced Distance, Clearance, and Atmospheric Safety",
        "weights": {
            "clearance": 0.162,
            "distance": 0.162,
            "weather": 0.108,
            "area": 0.063,
            "slope": 0.090,
            "roughness": 0.063,
            "surface": 0.063,
            "vegetation": 0.036,
            "access": 0.063,
            "openness": 0.054,
            "water": 0.036,
            "temporal": 0.10,
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


def resolve_profile(model_id: str, overrides=None) -> Dict[str, Any]:
    """Strict V1 profile resolution; built-ins are unverified research limits."""
    if model_id not in HELICOPTER_FLEET:
        raise ValueError('Unknown helicopter model')
    profile = deepcopy(HELICOPTER_FLEET[model_id])
    numeric = {'rotor_diameter_m', 'total_length_m', 'min_clear_diameter_m', 'min_area_m2',
               'max_slope_deg', 'max_crosswind_kt', 'max_gust_kt', 'cruise_speed_kt'}
    if overrides is None: overrides = {}
    if not isinstance(overrides, dict): raise ValueError('overrides must be an object')
    if set(overrides) - numeric - {'surface_types','max_wind_speed_kt'}: raise ValueError('Unsupported profile override')
    profile.update(overrides)
    if 'max_wind_speed_kt' in profile: numeric.add('max_wind_speed_kt')
    for key in numeric:
        try:
            if isinstance(profile[key], bool): raise ValueError()
            profile[key] = float(profile[key])
            if not math.isfinite(profile[key]) or profile[key] < 0: raise ValueError()
            if key not in {'max_slope_deg','max_crosswind_kt','max_gust_kt','max_wind_speed_kt'} and profile[key] == 0: raise ValueError()
        except (TypeError, ValueError): raise ValueError(f'{key} must be a finite supported value') from None
    if profile['max_slope_deg'] > 90: raise ValueError('max_slope_deg exceeds 90')
    if profile['min_clear_diameter_m'] < max(profile['rotor_diameter_m'],profile['total_length_m']):
        raise ValueError('Clearance diameter must contain aircraft dimensions')
    if not isinstance(profile['surface_types'],list) or not profile['surface_types'] or any(not isinstance(s,str) or not s.strip() for s in profile['surface_types']):
        raise ValueError('surface_types must contain permitted surfaces')
    profile.update(configuration_source='HELPS built-in research fleet',configuration_revision='2026-10-14-v2',
                   configuration_status='research_unverified',custom_overrides=deepcopy(overrides))
    profile['short_name']=UI_SHORT_NAMES.get(model_id,profile['name'])
    provenance=deepcopy(DIMENSION_PROVENANCE.get(model_id,{}))
    for key in ('rotor_diameter_m','total_length_m'):
        if key in overrides:
            provenance[key]={'status':'custom_unverified','value':profile[key],
                             'source':'User aircraft adjustment; no manufacturer verification'}
    profile['dimension_provenance']=provenance
    profile['operational_limits_status']='research_unverified'
    return profile


UI_MODEL_IDS = ('hal_prachand', 'hal_luh', 'hal_dhruv')
UI_SHORT_NAMES = dict(zip(UI_MODEL_IDS, ('LCH', 'LUH', 'ALH')))


def get_ui_profiles():
    """Three supported aircraft, serialized from the effective engine settings."""
    return [resolve_profile(model_id) for model_id in UI_MODEL_IDS]


DIMENSION_PROVENANCE = {
    'hal_luh': {
        'rotor_diameter_m': {'status':'verified_manufacturer','value':11.6,'units':'m',
            'source':'HAL Light Utility Helicopter brochure, dimensional drawing p6',
            'url':'https://hal-india.co.in/backend/wp-content/uploads/2023/05/303_Download_Light-Utility-helicopter-LUH-Brochure.pdf'},
        'total_length_m': {'status':'verified_manufacturer','value':13.85,'units':'m',
            'meaning':'Overall length with rotors; 11.49 m is fuselage length',
            'source':'HAL Light Utility Helicopter brochure, dimensional drawing p6',
            'url':'https://hal-india.co.in/backend/wp-content/uploads/2023/05/303_Download_Light-Utility-helicopter-LUH-Brochure.pdf'},
    },
    'hal_dhruv': {
        'rotor_diameter_m': {'status':'manufacturer_family_reference','value':13.2,'units':'m',
            'source':'HAL ALH Dhruv upgraded civil brochure; Mk III/IV variant confirmation required',
            'url':'https://hal-india.co.in/backend/wp-content/uploads/2023/05/297_Download_ALH-DHRUV-UPGRADED-CIVIL.pdf'},
        'total_length_m': {'status':'research_unverified','value':15.9,'units':'m',
            'source':'Configured Mk III/IV estimate; civil family brochure quotes 15.89 m'},
    },
    'hal_prachand': {
        'rotor_diameter_m': {'status':'research_unverified','value':13.3,'units':'m',
            'source':'HAL LCH brochure could not yet be extracted; configured dimension requires verification',
            'url':'https://hal-india.co.in/backend/wp-content/uploads/2023/05/302_Download_Light-Combat-Helicopter-LCH.pdf'},
        'total_length_m': {'status':'research_unverified','value':15.8,'units':'m',
            'source':'HAL LCH brochure could not yet be extracted; configured dimension requires verification',
            'url':'https://hal-india.co.in/backend/wp-content/uploads/2023/05/302_Download_Light-Combat-Helicopter-LCH.pdf'},
    },
}
