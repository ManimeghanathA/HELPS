import math
import pytest

def valid(**kwargs):
    return dict(dataset_id='synthetic', region_id='bhadra', latitude=13.5, longitude=75.5,
                model_id='hal_dhruv', mission='medevac', requested_at='2026-10-13T10:00:00Z', **kwargs)

def test_input_contract_resolves_versioned_profile():
    from scripts.recommendation.inputs import validate_request
    request = validate_request(valid())
    assert request.requested_at.utcoffset().total_seconds() == 0
    assert request.profile['configuration_status'] == 'research_unverified'
    assert request.profile['min_clear_diameter_m'] == 27

@pytest.mark.parametrize('key,value', [('latitude', math.nan), ('longitude', math.inf), ('latitude',91),
    ('radius_km',0), ('radius_km',1001), ('top_k',1.5), ('top_k',0), ('model_id','missing'),
    ('mission','missing'), ('requested_at','bad'), ('requested_at','2026-01-01T12:00:00')])
def test_invalid_requests_are_not_silently_defaulted(key,value):
    from scripts.recommendation.inputs import validate_request, InputError
    payload=valid(); payload[key]=value
    with pytest.raises(InputError): validate_request(payload)

@pytest.mark.parametrize('overrides', [{'rotor_diameter_m':-1}, {'max_slope_deg':'x'},
    {'min_clear_diameter_m':1}, {'max_gust_kt':float('inf')}, {'surface_types':[]}, {'typo':10}])
def test_invalid_profile_overrides_are_rejected(overrides):
    from scripts.recommendation.inputs import validate_request, InputError
    with pytest.raises(InputError): validate_request(valid(overrides=overrides))

@pytest.mark.parametrize('weather',[[],{'wind':'invalid'},{'source':'forged'},{'precipitation':42}])
def test_malformed_client_weather_is_an_input_error(weather):
    from scripts.recommendation.inputs import validate_request,InputError
    with pytest.raises(InputError):validate_request(valid(weather=weather))
