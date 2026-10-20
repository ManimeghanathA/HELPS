"""Strict model-weather evidence and coverage-scoped cache around WeatherPipeline."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import math
from threading import RLock
from .contracts import GateDecision
from .inputs import DEFAULT_POLICY, utc_timestamp, InputError

def distance_m(a,b):
    lat1,lon1,lat2,lon2=map(math.radians,(*a,*b))
    h=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371008.8*2*math.asin(min(1,math.sqrt(h)))

def number(value):
    try:
        if isinstance(value,bool): return None
        value=float(value)
        return value if math.isfinite(value) and value>=0 else None
    except (TypeError,ValueError): return None

def assess_weather(snapshot,profile,requested_at,policy,heading_deg=None,now=None):
    policy={**DEFAULT_POLICY,**policy}; now=now or datetime.now(timezone.utc)
    if not isinstance(snapshot,dict) or snapshot.get('error'):
        return GateDecision('unknown',('weather_unavailable',),{'error':snapshot.get('error') if isinstance(snapshot,dict) else None})
    if any(key in snapshot and snapshot[key] is not None and not isinstance(snapshot[key],dict) for key in ('wind','precipitation','source')):
        return GateDecision('unknown',('weather_snapshot_invalid',))
    wind=snapshot.get('wind') or {};precip=snapshot.get('precipitation') or {};source=snapshot.get('source') or {}
    values=dict(speed_kt=number(wind.get('speed_kt')),gust_kt=number(wind.get('gust_kt')),
        direction_deg=number(wind.get('direction_deg')),visibility_m=number(snapshot.get('visibility_m')),
        rain_mm_h=number(precip.get('current_hour_mm')))
    unknown=[f'weather_missing_{key}' for key,value in values.items() if value is None]
    fail=[]; evidence={'values':values,'source':deepcopy(source),'requested_at':requested_at.isoformat(),
        'observation_time_utc':snapshot.get('observation_time_utc'),'wind_from_deg':values['direction_deg']}
    try:
        observed=utc_timestamp(snapshot.get('observation_time_utc'));retrieved=utc_timestamp(source.get('retrieved_at_utc'))
        age=(now-retrieved).total_seconds()/60;offset=abs((requested_at-observed).total_seconds())/60
        evidence.update(retrieval_age_minutes=age,observation_offset_minutes=offset)
        if age< -5 or age>policy['max_weather_age_minutes']: unknown.append('weather_stale_retrieval')
        if offset>policy['max_observation_offset_minutes']: unknown.append('weather_time_not_covered')
    except InputError: unknown.append('weather_time_unknown')
    claimed_models=' '.join(str(source.get(key,'')) for key in ('model','supplied_model_claim'))
    historical_model=any(term in claimed_models.lower() for term in ('archive','reanalysis','historical'))
    # A freshly retrieved old observation is still historical evidence. A 48 h
    # lookback separates explicit historical study from current research queries.
    historical_target=(now-requested_at).total_seconds()>48*3600
    historical=historical_model or historical_target
    evidence['historical']=historical
    evidence.update(historical_model_claim=historical_model,historical_target=historical_target,
        current_target_lookback_hours=48)
    if historical and not policy['allow_historical']: unknown.append('historical_weather_not_current')
    if values['direction_deg'] is not None and values['direction_deg']>360: unknown.append('invalid_wind_direction')
    if values['gust_kt'] is not None and values['gust_kt']>profile['max_gust_kt']: fail.append('gust_exceeds_limit')
    if values['speed_kt'] is not None and values['gust_kt'] is not None and values['gust_kt']<values['speed_kt']:
        unknown.append('wind_gust_below_sustained')
    total_limit=profile.get('max_wind_speed_kt')
    evidence['configured_total_wind_limit_kt']=total_limit
    if total_limit is not None and values['speed_kt'] is not None and values['speed_kt']>total_limit:
        fail.append('sustained_wind_exceeds_limit')
    if values['visibility_m'] is not None and values['visibility_m']<policy['min_visibility_m']: fail.append('visibility_below_limit')
    if values['rain_mm_h'] is not None and values['rain_mm_h']>policy['max_rain_mm_h']: fail.append('rain_exceeds_limit')
    if heading_deg is None:
        evidence['crosswind_kt']=None
        if policy['require_heading']: unknown.append('heading_unknown')
    elif values['speed_kt'] is not None and values['direction_deg'] is not None:
        delta=math.radians(values['direction_deg']-heading_deg)
        cross=abs(values['speed_kt']*math.sin(delta));evidence.update(heading_deg=heading_deg,crosswind_kt=cross,headwind_kt=values['speed_kt']*math.cos(delta))
        if cross>profile['max_crosswind_kt']: fail.append('crosswind_exceeds_limit')
    if set(unknown)&{'weather_stale_retrieval','weather_time_not_covered','weather_time_unknown','historical_weather_not_current'}:
        evidence['unscoped_limit_observations']=list(fail)
        fail=[]
    return GateDecision('fail' if fail else 'unknown' if unknown else 'pass',tuple(fail+unknown),evidence)

class WeatherSnapshotCache:
    def __init__(self,provider=None,clock=None,max_entries=128):
        if provider is None:
            from weather_pipeline import WeatherPipeline
            provider=WeatherPipeline().fetch_weather
        self.provider=provider.fetch_weather if hasattr(provider,'fetch_weather') else provider
        self.clock=clock or (lambda:datetime.now(timezone.utc));self.max_entries=max_entries
        self._entries=OrderedDict();self._lock=RLock()

    def get_or_fetch(self,location,requested_at,coverage_policy):
        policy={**DEFAULT_POLICY,**coverage_policy}; now=self.clock()
        if isinstance(location,dict): location=(location['latitude'],location['longitude'])
        with self._lock:
            for key,entry in list(self._entries.items()):
                source=entry.get('source') or {}
                try:
                    age=(now-utc_timestamp(source.get('retrieved_at_utc'))).total_seconds()/60
                    offset=abs((requested_at-utc_timestamp(entry.get('observation_time_utc'))).total_seconds())/60
                    loc=entry['location'];sep=distance_m(location,(loc['latitude'],loc['longitude']))
                    if 0<=age<=policy['max_weather_age_minutes'] and offset<=policy['max_observation_offset_minutes'] and sep<=policy['weather_coverage_radius_m']:
                        self._entries.move_to_end(key);result=deepcopy(entry);result['cache']={'reused':True,'separation_m':sep};return result
                except (InputError,KeyError,TypeError,ValueError): continue
        try: result=self.provider(*location,requested_at)
        except Exception as error: return {'error':str(error),'source':{'provider':'Open-Meteo'},'location':dict(zip(('latitude','longitude'),location))}
        if not isinstance(result,dict): return {'error':'Provider returned invalid weather'}
        with self._lock:
            if not result.get('error'):
                self._entries[(location,requested_at.isoformat())]=deepcopy(result)
                while len(self._entries)>self.max_entries: self._entries.popitem(last=False)
        return deepcopy(result)
