"""Independent mandatory gates. No ranking score can bypass them."""
from shapely.geometry import Point
import math
from .contracts import GateDecision
from .inputs import DEFAULT_POLICY
from .weather_policy import number

def validate_footprint(metric_geometry,metric_poi,required_radius_m):
    radius=number(required_radius_m)
    if metric_geometry is None or metric_poi is None or radius is None or radius<=0:
        return GateDecision('unknown',('footprint_geometry_missing',))
    if metric_poi.is_empty or not all(math.isfinite(v) for v in (metric_poi.x,metric_poi.y)):
        return GateDecision('unknown',('footprint_reference_invalid',))
    if metric_geometry.is_empty or not metric_geometry.is_valid or metric_geometry.geom_type not in ('Polygon','MultiPolygon'):
        return GateDecision('unknown',('footprint_geometry_invalid',))
    # Exact distance to ALL boundaries includes holes. Buffer tessellation alone
    # would underestimate the requested circle and could hide a shortfall.
    centre_inside=metric_geometry.contains(metric_poi)
    clearance=metric_geometry.boundary.distance(metric_poi)
    evidence=dict(required_radius_m=radius,actual_boundary_distance_m=clearance,centre_inside=centre_inside,
                  method='exact point-to-full-boundary distance; no positive tolerance')
    if not centre_inside: return GateDecision('fail',('footprint_centre_outside',),evidence)
    if clearance<radius: return GateDecision('fail',('footprint_crosses_boundary',),evidence)
    if not metric_geometry.covers(metric_poi.buffer(radius,quad_segs=128)):
        return GateDecision('fail',('footprint_not_contained',),evidence)
    return GateDecision('pass',(),evidence)

def minimum(value,limit,name):
    value=number(value);evidence=dict(measured=value,required_minimum=limit)
    return GateDecision('unknown',(f'{name}_unknown',),evidence) if value is None else GateDecision('pass' if value>=limit else 'fail',() if value>=limit else (f'{name}_below_limit',),evidence)

def assess_zone(zone_record,terrain_record,environment_record,profile,weather_decision,policy):
    policy={**DEFAULT_POLICY,**policy}; z=zone_record;t=terrain_record or {};env=environment_record or {}
    slope=number(z.get('max_slope_deg'));support=number(z.get('dem_valid_fraction'))
    # Exact polygon-cell intersections can sum to 1 minus a few ulps.
    # This tolerance concerns coverage arithmetic only, never slope/clearance.
    coverage_roundoff_tolerance=1e-12
    evidence=dict(max_slope_deg=slope,dem_valid_fraction=support,maximum=profile['max_slope_deg'],
        coverage_roundoff_tolerance=coverage_roundoff_tolerance,
        required_support=policy['min_dem_valid_fraction'],source=z.get('slope_evidence',t.get('slope_evidence')))
    if slope is not None and slope>profile['max_slope_deg']: slope_gate=GateDecision('fail',('slope_exceeds_limit',),evidence)
    elif slope is None or slope>90 or support is None or support>1+coverage_roundoff_tolerance or support+coverage_roundoff_tolerance<policy['min_dem_valid_fraction']:
        slope_gate=GateDecision('unknown',('slope_unsupported',),evidence)
    else: slope_gate=GateDecision('pass',(),evidence)
    surface=env.get('surface_type',t.get('surface_type'));verified=env.get('surface_verified',t.get('surface_verified',False))
    surface_evidence=dict(surface_type=surface,verified=verified,source=env.get('surface_evidence',t.get('surface_evidence')))
    if not surface or not verified: surface_gate=GateDecision('unknown',('surface_unverified',),surface_evidence)
    elif surface not in profile['surface_types']: surface_gate=GateDecision('fail',('surface_not_permitted',),surface_evidence)
    else: surface_gate=GateDecision('pass',(),surface_evidence)
    restrictions=env.get('restriction_state','unknown')
    restriction_evidence=dict(state=restrictions,source=env.get('restriction_evidence'))
    if restrictions in ('restricted','restricted_mapped','blocked','overlap'): restriction_gate=GateDecision('fail',('restriction_overlap',),restriction_evidence)
    elif restrictions in ('verified_clear','verified_coverage_clear'): restriction_gate=GateDecision('pass',(),restriction_evidence)
    else: restriction_gate=GateDecision('unknown',('restrictions_unverified',),restriction_evidence)
    # Metric coordinates may be negative in local projected synthetic frames.
    try:
        x=float(z['poi_easting']);y=float(z['poi_northing'])
        poi=Point(x,y) if math.isfinite(x) and math.isfinite(y) else None
    except (KeyError,TypeError,ValueError): poi=None
    geometry=z.get('metric_geometry')
    stored_area=number(z.get('area_m2'))
    geometry_area=geometry.area if geometry is not None and geometry.is_valid and not geometry.is_empty and geometry.geom_type in ('Polygon','MultiPolygon') else None
    conservative_area=min(stored_area,geometry_area) if stored_area is not None and geometry_area is not None else geometry_area if geometry_area is not None else stored_area
    area_gate=minimum(conservative_area,profile['min_area_m2'],'area')
    area_gate=GateDecision(area_gate.state,area_gate.reason_codes,{**area_gate.evidence,'stored_area_m2':stored_area,'geometry_area_m2':geometry_area})
    gates=dict(slope=slope_gate,area=area_gate,
        clearance=minimum(z.get('max_clear_diameter_m'),profile['min_clear_diameter_m'],'clearance'),
        footprint=validate_footprint(z.get('metric_geometry'),poi,profile['min_clear_diameter_m']/2),
        surface=surface_gate,restrictions=restriction_gate,weather=weather_decision)
    state='fail' if any(d.state=='fail' for d in gates.values()) else 'unknown' if any(d.state=='unknown' for d in gates.values()) else 'pass'
    return dict(zone=z,terrain=t,environment=env,gates=gates,state=state,
        reason_codes=[code for decision in gates.values() for code in decision.reason_codes])
