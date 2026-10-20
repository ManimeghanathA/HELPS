import pytest
from shapely.geometry import box,Polygon,Point,MultiPolygon
from helicopter_profiles import resolve_profile
from scripts.recommendation.contracts import GateDecision

def zone():
    return dict(area_m2=1600,max_clear_diameter_m=40,max_slope_deg=2,dem_valid_fraction=1,
        poi_easting=0,poi_northing=0,metric_geometry=box(-20,-20,20,20))
def environment(): return dict(surface_type='Grass',surface_verified=True,restriction_state='verified_clear')

@pytest.mark.parametrize('support,state',[(0.9999999999998879,'pass'),(1-2e-12,'unknown'),(0.999999,'unknown')])
def test_dem_coverage_roundoff_does_not_hide_real_missing_support(support,state):
    from scripts.recommendation.compatibility import assess_zone
    z=zone();z['dem_valid_fraction']=support
    gate=assess_zone(z,{},environment(),resolve_profile('hal_dhruv'),GateDecision('pass'),{})['gates']['slope']
    assert gate.state==state
    assert gate.evidence['coverage_roundoff_tolerance']==1e-12

def test_required_circle_crosses_excluded_interior():
    from scripts.recommendation.compatibility import validate_footprint
    outer=box(-20,-20,20,20);hole=box(8,-2,9,2)
    geometry=Polygon(outer.exterior.coords,[hole.exterior.coords])
    assert validate_footprint(geometry,Point(0,0),10).state=='fail'

@pytest.mark.parametrize('geometry,point,radius,state',[(box(-10,-10,10,10),Point(0,0),10,'pass'),
    (box(-10,-10,10,10),Point(0,0),10.000001,'fail'),
    (MultiPolygon([box(-20,-20,-1,20),box(1,-20,20,20)]),Point(0,0),2,'fail'),
    (box(-20,-20,20,20),Point(50,0),1,'fail')])
def test_exact_footprint_boundaries(geometry,point,radius,state):
    from scripts.recommendation.compatibility import validate_footprint
    assert validate_footprint(geometry,point,radius).state==state

@pytest.mark.parametrize('changes,gate,state', [({'max_slope_deg':30},'slope','fail'),
    ({'max_slope_deg':None},'slope','unknown'),({'dem_valid_fraction':0.8},'slope','unknown'),
    ({'area_m2':10},'area','fail'),({'max_clear_diameter_m':10},'clearance','fail')])
def test_mandatory_geometry_gates_cannot_be_outvoted(changes,gate,state):
    from scripts.recommendation.compatibility import assess_zone
    z=zone();z.update(changes)
    assessed=assess_zone(z,{},environment(),resolve_profile('hal_dhruv'),GateDecision('pass'),{})
    assert assessed['gates'][gate].state==state
    assert assessed['state']!='pass'

def test_missing_surface_and_restriction_are_independently_unknown():
    from scripts.recommendation.compatibility import assess_zone
    assessed=assess_zone(zone(),{},{},resolve_profile('hal_dhruv'),GateDecision('pass'),{})
    assert assessed['gates']['surface'].state=='unknown'
    assert assessed['gates']['restrictions'].state=='unknown'

def test_unsupported_and_unverified_spectral_surfaces_are_not_passed():
    from scripts.recommendation.compatibility import assess_zone
    for surface,verified,state in [('Water',True,'fail'),('Compact Soil',False,'unknown')]:
        env=environment();env.update(surface_type=surface,surface_verified=verified)
        assert assess_zone(zone(),{},env,resolve_profile('hal_dhruv'),GateDecision('pass'),{})['gates']['surface'].state==state

@pytest.mark.parametrize('value',[float('nan'),float('inf'),float('-inf')])
def test_nonfinite_reference_point_is_unknown_not_geometry_error(value):
    from scripts.recommendation.compatibility import assess_zone
    z=zone();z['poi_easting']=value
    result=assess_zone(z,{},environment(),resolve_profile('hal_dhruv'),GateDecision('pass'),{})
    assert result['gates']['footprint'].state=='unknown'
