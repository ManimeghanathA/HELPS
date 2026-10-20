from datetime import datetime, timezone
import math
from helicopter_profiles import resolve_profile, MISSION_CONTEXTS
from .contracts import RecommendationRequest

class InputError(ValueError): pass

DEFAULT_POLICY = dict(id='research-hard-checks-v2', require_heading=True, max_weather_age_minutes=120,
    max_observation_offset_minutes=60, weather_coverage_radius_m=1000, min_dem_valid_fraction=1.0,
    min_visibility_m=1000, max_rain_mm_h=10, allow_historical=False)

def finite(value, name, lower=None, upper=None):
    if isinstance(value, bool): raise InputError(f'{name} must be numeric')
    try: number=float(value)
    except (ValueError,TypeError): raise InputError(f'{name} must be numeric') from None
    if not math.isfinite(number) or (lower is not None and number<lower) or (upper is not None and number>upper):
        raise InputError(f'{name} is outside the supported range')
    return number

def utc_timestamp(value):
    try:
        parsed=value if isinstance(value,datetime) else datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None: raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError,TypeError,AttributeError): raise InputError('requested_at must be an ISO timestamp with timezone') from None

def validate_request(payload):
    if not isinstance(payload,dict): raise InputError('Request must be a JSON object')
    weather=payload.get('weather')
    if weather is not None:
        if not isinstance(weather,dict): raise InputError('weather must be an object')
        for key in ('wind','source','precipitation','location'):
            if key in weather and not isinstance(weather[key],dict): raise InputError(f'weather.{key} must be an object')
    for key in ('dataset_id','region_id','model_id','mission'):
        if not isinstance(payload.get(key),str) or not payload[key].strip(): raise InputError(f'{key} is required')
    if payload['mission'] not in MISSION_CONTEXTS: raise InputError('Unknown mission')
    try: profile=resolve_profile(payload['model_id'],payload.get('overrides'))
    except ValueError as error: raise InputError(str(error)) from None
    radius=finite(payload.get('radius_km',20),'radius_km',0.001,1000)
    top=finite(payload.get('top_k',5),'top_k',1,100)
    if top != int(top): raise InputError('top_k must be an integer')
    supplied=payload.get('policy',{})
    if not isinstance(supplied,dict): raise InputError('policy must be an object')
    unknown=set(supplied)-set(DEFAULT_POLICY)-{'heading_deg'}
    if unknown: raise InputError('Unknown policy fields: '+', '.join(sorted(unknown)))
    policy={**DEFAULT_POLICY,**supplied}
    for key in ('require_heading','allow_historical'):
        if not isinstance(policy[key],bool): raise InputError(f'{key} must be boolean')
    for key in ('max_weather_age_minutes','max_observation_offset_minutes','weather_coverage_radius_m','min_visibility_m','max_rain_mm_h'):
        policy[key]=finite(policy[key],key,0,1e6)
    policy['min_dem_valid_fraction']=finite(policy['min_dem_valid_fraction'],'min_dem_valid_fraction',0,1)
    if 'heading_deg' in policy: policy['heading_deg']=finite(policy['heading_deg'],'heading_deg',0,360)%360
    return RecommendationRequest(payload['dataset_id'],payload['region_id'],finite(payload.get('latitude'),'latitude',-90,90),
        finite(payload.get('longitude'),'longitude',-180,180),payload['model_id'],payload.get('overrides') or {},
        payload['mission'],utc_timestamp(payload.get('requested_at')),radius,int(top),policy,profile,payload.get('weather'))
