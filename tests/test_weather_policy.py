from datetime import datetime, timezone, timedelta
from copy import deepcopy
import pytest
from helicopter_profiles import resolve_profile

NOW=datetime(2026,10,13,10,tzinfo=timezone.utc)
def snapshot():
    return dict(location=dict(latitude=13.5,longitude=75.5),observation_time_utc=NOW.isoformat(),
        wind=dict(speed_kt=10,gust_kt=15,direction_deg=270), visibility_m=5000,
        precipitation=dict(current_hour_mm=0),source=dict(provider='fixture',model='forecast',retrieved_at_utc=NOW.isoformat()))

def test_wind_from_and_heading_are_separate_and_strict_heading_required():
    from scripts.recommendation.weather_policy import assess_weather
    p=resolve_profile('hal_dhruv')
    assert assess_weather(snapshot(),p,NOW,{},now=NOW).state == 'unknown'
    d=assess_weather(snapshot(),p,NOW,{},heading_deg=270,now=NOW)
    assert d.state == 'pass'
    assert d.evidence['wind_from_deg'] == 270
    assert d.evidence['headwind_kt'] == pytest.approx(10)

@pytest.mark.parametrize('field', ['speed_kt','gust_kt','direction_deg','visibility_m','current_hour_mm'])
def test_missing_weather_is_unknown(field):
    from scripts.recommendation.weather_policy import assess_weather
    s=snapshot()
    container=s['wind'] if field in s['wind'] else s['precipitation'] if field=='current_hour_mm' else s
    container[field]=None
    assert assess_weather(s,resolve_profile('hal_dhruv'),NOW,{},270,now=NOW).state == 'unknown'

def test_stale_and_historical_cannot_masquerade_as_current():
    from scripts.recommendation.weather_policy import assess_weather
    s=snapshot();s['source']['retrieved_at_utc']=(NOW-timedelta(hours=3)).isoformat()
    assert assess_weather(s,resolve_profile('hal_dhruv'),NOW,{},270,now=NOW).state == 'unknown'
    s=snapshot();s['source']['model']='archive ERA5 reanalysis'
    assert assess_weather(s,resolve_profile('hal_dhruv'),NOW,{},270,now=NOW).state == 'unknown'

def test_weather_limit_is_independent_failure():
    from scripts.recommendation.weather_policy import assess_weather
    s=snapshot();s['wind']['gust_kt']=50
    assert assess_weather(s,resolve_profile('hal_dhruv'),NOW,{},270,now=NOW).state == 'fail'

def test_malformed_provider_snapshot_is_unknown_without_crash():
    from scripts.recommendation.weather_policy import assess_weather
    s=snapshot();s['wind']='invalid'
    assert assess_weather(s,resolve_profile('hal_dhruv'),NOW,{},270,now=NOW).state=='unknown'

def test_extreme_sustained_wind_cannot_hide_behind_lower_gust():
    from scripts.recommendation.weather_policy import assess_weather
    s=snapshot();s['wind'].update(speed_kt=100,gust_kt=1)
    result=assess_weather(s,resolve_profile('hal_dhruv'),NOW,{},270,now=NOW)
    assert result.state=='unknown'
    assert 'wind_gust_below_sustained' in result.reason_codes

def test_configured_total_wind_limit_is_distinct_from_crosswind():
    from scripts.recommendation.weather_policy import assess_weather
    s=snapshot();s['wind'].update(speed_kt=30,gust_kt=32)
    p=resolve_profile('hal_dhruv',{'max_wind_speed_kt':25})
    result=assess_weather(s,p,NOW,{},270,now=NOW)
    assert result.state=='fail'
    assert 'sustained_wind_exceeds_limit' in result.reason_codes
    assert result.evidence['crosswind_kt']==0

def test_far_past_target_is_historical_even_if_source_claims_forecast():
    from scripts.recommendation.weather_policy import assess_weather
    past=NOW-timedelta(days=10);s=snapshot();s['observation_time_utc']=past.isoformat()
    result=assess_weather(s,resolve_profile('hal_dhruv'),past,{},270,now=NOW)
    assert result.state=='unknown'
    assert 'historical_weather_not_current' in result.reason_codes
    assert assess_weather(s,resolve_profile('hal_dhruv'),past,{'allow_historical':True},270,now=NOW).state=='pass'

def test_cache_does_not_reuse_other_location_or_time():
    from scripts.recommendation.weather_policy import WeatherSnapshotCache
    calls=[]
    def fetch(lat,lon,at):
        calls.append((lat,lon,at));s=snapshot();s['location']=dict(latitude=lat,longitude=lon);s['observation_time_utc']=at.isoformat();return s
    cache=WeatherSnapshotCache(fetch,clock=lambda:NOW)
    assert cache.get_or_fetch((13.5,75.5),NOW,{})['location']['latitude']==13.5
    cache.get_or_fetch((13.5001,75.5),NOW,{})
    cache.get_or_fetch((14.5,75.5),NOW,{})
    cache.get_or_fetch((13.5,75.5),NOW+timedelta(hours=3),{})
    assert len(calls)==3
