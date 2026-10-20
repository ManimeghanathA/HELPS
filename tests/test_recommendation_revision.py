from copy import deepcopy
import math
import json
import pytest
from shapely.geometry import Polygon
from test_recommendation_engine import Repository, Weather, zone, request
from scripts.recommendation.engine import RecommendationEngine
from scripts.recommendation.ranking import rank_eligible
from scripts.recommendation.contracts import GateDecision
from test_mission_ranking import assessed


def test_research_ranks_unknown_without_passing_unknown_gates_and_excludes_failure():
    unknown=zone('research'); unknown['surface_verified']=False
    failed=zone('failed'); failed['max_slope_deg']=30
    missing=zone('missing'); missing['metric_geometry']=None
    invalid=zone('invalid'); invalid['metric_geometry']=Polygon([(0,0),(1,1),(1,0),(0,1),(0,0)])
    result=RecommendationEngine(Repository([unknown,failed,missing,invalid]),Weather()).recommend(request()).to_dict()
    assert [x['zone_id'] for x in result['research_candidates']]==['research']
    candidate=result['research_candidates'][0]
    assert candidate['gates']['surface']['state']=='unknown'
    assert candidate['verification_state']=='requires_verification'
    assert candidate['missing_verification_reasons']
    assert result['research_count']==1
    assert result['distinct_opportunity_counts']['research']==1


def test_remote_weather_failure_and_crosswind_do_not_apply_to_uncovered_zone():
    class BadRemoteWeather(Weather):
        def get_or_fetch(self,*args):
            value=super().get_or_fetch(*args); value['wind']['gust_kt']=100
            return value
    distant=zone(); distant['latitude']=13.6
    result=RecommendationEngine(Repository([distant]),BadRemoteWeather()).recommend(request()).to_dict()
    candidate=result['research_candidates'][0]
    assert candidate['gates']['weather']['state']=='unknown'
    assert 'weather' not in candidate['score_factors']


def test_supported_weight_coverage_and_expected_contributions():
    a=assessed('a'); a['gates']['weather']=GateDecision('unknown',('weather_location_not_covered',),{'crosswind_kt':0})
    result=rank_eligible([a],{'weights':{'distance':.5,'area':.25,'weather':.25}},(13.5,75.5),5)[0]
    assert result['supported_factor_weight_coverage']==pytest.approx(.75)
    assert result['normalized_weights']==pytest.approx({'distance':2/3,'area':1/3})
    assert result['score']==pytest.approx(100*(2/3+1/3*(1600/2600)))
    assert 'weather' in result['missing_optional_factors']


def test_soft_zero_missing_nonfinite_values_do_not_eliminate():
    low=zone(); low.update(mean_roughness_m=1e300,road_distance_m=None,water_distance_m=float('inf'),openness_score=0)
    result=RecommendationEngine(Repository([low]),Weather()).recommend(request(mission='hybrid_balanced')).to_dict()
    assert len(result['research_candidates'])==1
    c=result['research_candidates'][0]
    assert math.isfinite(c['score']) and 0<=c['score']<=100
    json.dumps(result,allow_nan=False)
    assert set(c['available_factors'])=={'distance','clearance','weather','area','slope','roughness','surface','vegetation','access','openness','water','temporal'}


def test_three_ui_profiles_are_effective_copies_and_dimensions_override_is_unverified():
    from helicopter_profiles import get_ui_profiles, resolve_profile
    profiles=get_ui_profiles()
    assert [p['short_name'] for p in profiles]==['LCH','LUH','ALH']
    assert all(p==resolve_profile(p['id']) for p in profiles)
    profiles[0]['surface_types'].clear()
    assert get_ui_profiles()[0]['surface_types']
    custom=resolve_profile('hal_prachand',{'total_length_m':16})
    assert custom['dimension_provenance']['total_length_m']['status']=='custom_unverified'


@pytest.mark.parametrize('key,increasing',[('distance',False),('clearance',True),('area',True),('access',False),('slope',False),('roughness',False),('water',True)])
def test_factor_transforms_are_bounded_monotonic_with_declared_units(key,increasing):
    from scripts.recommendation.ranking import _factor
    scales={'distance':1000,'clearance':30,'area':1000,'access':1000,'slope':10,'roughness':1,'water':100}
    values=[_factor(value,scales[key],not increasing) for value in [0,.01,1,10,1000,1e300]]
    assert all(math.isfinite(v) and 0<=v<=1 for v in values)
    assert values==sorted(values,reverse=not increasing)


def test_invalid_dem_fraction_stays_unknown_and_geometry_area_cannot_be_inflated():
    invalid=zone();invalid['dem_valid_fraction']=2
    result=RecommendationEngine(Repository([invalid]),Weather()).recommend(request()).to_dict()
    assert result['research_candidates'][0]['gates']['slope']['state']=='unknown'
    assert 'slope' not in result['research_candidates'][0]['score_factors']
    from shapely.geometry import box
    small=zone();small['metric_geometry']=box(549986,1489986,550014,1490014)
    result=RecommendationEngine(Repository([small]),Weather()).recommend(request()).to_dict()
    assert not result['research_candidates']
    assert result['excluded'][0]['gates']['area']['state']=='fail'


def test_spectral_fraction_support_accepts_only_declared_roundoff():
    a=assessed('a');a['terrain']={'bare_surface_fraction':1,'vegetation_fraction':0,'surface_observations':{'scl':{'observable_fraction':1-2e-12}}}
    result=rank_eligible([a],{'weights':{'surface':1}},(13.5,75.5),5)[0]
    assert result['score'] is None
    assert result['supported_factor_weight_coverage']==0


def test_full_balanced_factors_numeric_score_and_eta():
    from helicopter_profiles import MISSION_CONTEXTS,resolve_profile
    a=assessed('a');a['terrain']={'mean_roughness_m':1,'bare_surface_fraction':.5,'vegetation_fraction':.5,'surface_observations':{'scl':{'observable_fraction':1}}}
    a['environment'].update(road_distance_m=1000,water_distance_m=100,openness_score=.5,context_coverage_state='verified')
    a['gates']['weather']=GateDecision('pass',(),{'crosswind_kt':20})
    a['zone'].update(max_clear_diameter_m=30,area_m2=1000,max_slope_deg=10)
    c=rank_eligible([a],MISSION_CONTEXTS['hybrid_balanced'],(13.5,75.5),5,resolve_profile('hal_dhruv'))[0]
    assert len(c['score_factors'])==11
    assert c['score']==pytest.approx(59)
    assert c['supported_factor_weight_coverage']==pytest.approx(.9)
    assert sum(c['score_contributions'].values())*100==pytest.approx(c['score'])
    assert c['straight_line_eta_minutes']==0
    assert all('units' in c['factor_evidence'][key] for key in c['score_factors'])



def test_stale_adverse_weather_is_not_a_known_current_failure():
    from datetime import timedelta
    from scripts.recommendation.weather_policy import assess_weather
    from test_weather_policy import NOW,snapshot
    from helicopter_profiles import resolve_profile
    weather=snapshot();weather['wind']['gust_kt']=100
    weather['observation_time_utc']=(NOW-timedelta(days=1)).isoformat()
    decision=assess_weather(weather,resolve_profile('hal_dhruv'),NOW,{},270,now=NOW)
    assert decision.state=='unknown'
    assert 'gust_exceeds_limit' not in decision.reason_codes
    assert 'gust_exceeds_limit' in decision.evidence['unscoped_limit_observations']


def test_nonfinite_provider_location_cannot_pass_weather_coverage():
    class InvalidLocation(Weather):
        def get_or_fetch(self,*args):
            weather=super().get_or_fetch(*args);weather['location']['latitude']=float('nan');return weather
    result=RecommendationEngine(Repository([zone()]),InvalidLocation()).recommend(request()).to_dict()
    assert result['research_candidates'][0]['gates']['weather']['state']=='unknown'
    assert 'weather' not in result['research_candidates'][0]['score_factors']


def test_excluded_candidate_has_excluded_verification_state():
    failed=zone();failed['max_slope_deg']=30
    result=RecommendationEngine(Repository([failed]),Weather()).recommend(request()).to_dict()
    assert result['excluded'][0]['verification_state']=='excluded_known_failure'



def test_changed_aircraft_configuration_and_policy_have_new_revision():
    from helicopter_profiles import resolve_profile
    from scripts.recommendation.inputs import DEFAULT_POLICY
    assert resolve_profile('hal_luh')['configuration_revision']=='2026-10-14-v2'
    assert DEFAULT_POLICY['id']=='research-hard-checks-v2'



def test_roundoff_cannot_make_a_score_exceed_one_hundred():
    a=assessed('a',road=0)
    a['zone'].update(area_m2=1e300,max_clear_diameter_m=1e300,max_slope_deg=0)
    a['terrain']={'mean_roughness_m':0,'bare_surface_fraction':1,'vegetation_fraction':0,'surface_observations':{'scl':{'observable_fraction':1}}}
    a['environment'].update(openness_score=1,context_coverage_state='verified',water_distance_m=1e300)
    a['gates']['weather']=GateDecision('pass',(),{'crosswind_kt':0})
    keys=['distance','clearance','weather','area','slope','roughness','surface','vegetation','access','openness','water']
    result=rank_eligible([a],{'weights':dict.fromkeys(keys,.1)},(13.5,75.5),5)[0]
    assert result['score']<=100



def test_scores_use_verified_geometry_area_and_reference_clearance_bounds():
    z=zone();z['area_m2']=100000;z['max_clear_diameter_m']=1000
    candidate=RecommendationEngine(Repository([z]),Weather()).recommend(request()).to_dict()['research_candidates'][0]
    assert candidate['score_factors']['area']==pytest.approx(1600/2600)
    assert candidate['score_factors']['clearance']==pytest.approx(40/70)
