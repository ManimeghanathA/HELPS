from shapely.geometry import box
from helicopter_profiles import MISSION_CONTEXTS

def assessed(identity,lat=13.5,road=100,geometry=None,parent='parent',state='pass'):
    return dict(state=state,zone=dict(zone_id=identity,terrain_id=parent,latitude=lat,longitude=75.5,
        area_m2=1600,max_clear_diameter_m=40,max_slope_deg=2,metric_geometry=geometry if geometry is not None else box(-20,-20,20,20),
        poi_easting=0,poi_northing=0),environment=dict(road_distance_m=road),gates={})

def test_medevac_prefers_stored_access_context():
    from scripts.recommendation.ranking import rank_eligible
    a=assessed('poor-access',road=5000,parent='a');b=assessed('access',road=10,parent='b')
    result=rank_eligible([a,b],MISSION_CONTEXTS['medevac'],(13.5,75.5),5)
    assert result[0]['zone_id']=='access'
    assert result[0]['score_contributions']['access']>0

def test_urgency_prioritizes_distance_and_excludes_nonpassing_zones():
    from scripts.recommendation.ranking import rank_eligible
    values=[assessed('far',lat=13.6,parent='a'),assessed('near',parent='b'),assessed('failed',state='fail'),assessed('unknown',state='unknown')]
    result=rank_eligible(values,MISSION_CONTEXTS['immediate_emergency'],(13.5,75.5),5)
    assert [v['zone_id'] for v in result]==['near','far']

def test_missing_optional_context_omits_factor_and_normalizes():
    from scripts.recommendation.ranking import rank_eligible
    a=assessed('a');a['environment']={}
    result=rank_eligible([a],MISSION_CONTEXTS['medevac'],(13.5,75.5),5)[0]
    assert 'access' not in result['score_contributions']
    assert sum(result['normalized_weights'].values())==1
    assert 'access' in result['missing_optional_factors']

def test_nested_threshold_duplicates_suppressed_distinct_parts_preserved():
    from scripts.recommendation.ranking import rank_eligible
    a=assessed('a');b=assessed('b',geometry=box(-21,-21,21,21));c=assessed('c',geometry=box(100,100,140,140))
    c['zone'].update(poi_easting=120,poi_northing=120)
    result=rank_eligible([c,b,a],MISSION_CONTEXTS['immediate_emergency'],(13.5,75.5),5)
    assert len(result)==2
    assert 'c' in [v['zone_id'] for v in result]
    assert any(v['deduplicated_zone_ids'] for v in result)

def test_stable_ties_use_identity():
    from scripts.recommendation.ranking import rank_eligible
    a=assessed('a',parent='a');b=assessed('b',parent='b')
    assert [x['zone_id'] for x in rank_eligible([b,a],MISSION_CONTEXTS['immediate_emergency'],(13.5,75.5),5)]==['a','b']

def test_precautionary_mission_uses_measured_roughness_and_openness():
    from scripts.recommendation.ranking import rank_eligible
    a=assessed('rough',parent='a');b=assessed('smooth',parent='b')
    a['terrain']={'mean_roughness_m':5};b['terrain']={'mean_roughness_m':0.1}
    a['environment']['openness_score']=0.2;b['environment']['openness_score']=0.9
    a['environment']['context_coverage_state']='verified';b['environment']['context_coverage_state']='verified'
    result=rank_eligible([a,b],MISSION_CONTEXTS['safest_landing'],(13.5,75.5),5)
    assert result[0]['zone_id']=='smooth'
    assert 'roughness' in result[0]['score_contributions']
    assert 'openness' in result[0]['score_contributions']


def test_balanced_mission_keeps_terrain_and_surface_evidence_in_scoring():
    from scripts.recommendation.ranking import rank_eligible
    a=assessed('a',parent='a')
    a['terrain']={'mean_roughness_m':.2,'bare_surface_fraction':.7,'vegetation_fraction':.1,'surface_evidence_date':'2026-06-01'}
    a['terrain']['surface_observations']={'scl':{'observable_fraction':1}}
    a['environment'].update(openness_score=.8,water_distance_m=300,context_coverage_state='verified')
    result=rank_eligible([a],MISSION_CONTEXTS['hybrid_balanced'],(13.5,75.5),5)[0]
    assert {'slope','roughness','surface','vegetation','access','openness','water'} <= set(result['score_contributions'])
    assert result['factor_evidence']['surface']['meaning']=='spectral bare-surface proportion; not ground firmness'
    assert abs(sum(result['normalized_weights'].values())-1)<1e-12


def test_unknown_or_sparse_coverage_cannot_earn_openness_or_vegetation_priority():
    from scripts.recommendation.ranking import rank_eligible
    a=assessed('a')
    a['terrain']={'vegetation_fraction':0,'bare_surface_fraction':.01,'surface_observations':{'scl':{'valid_fraction':.01,'observable_fraction':.01,'unknown_fraction':.99}}}
    a['environment']={'openness_score':1,'context_coverage_state':'unknown'}
    result=rank_eligible([a],{'weights':{'distance':.4,'openness':.3,'vegetation':.2,'surface':.1}},(13.5,75.5),5)[0]
    assert set(result['missing_optional_factors'])=={'openness','vegetation','surface'}
    assert set(result['score_factors'])=={'distance'}
