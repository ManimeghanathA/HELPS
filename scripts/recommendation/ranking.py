"""Relative mission priorities from stored context; scores are not probabilities."""
from shapely.geometry import Point
import math
from .weather_policy import distance_m, number

def _factor(value,scale,inverse=False):
    value=number(value)
    if value is None:return None
    return scale/(scale+value) if inverse else value/(scale+value)

def _fraction(value,inverse=False):
    value=number(value)
    if value is None or value>1:return None
    return 1-value if inverse else value

def same_opportunity(a,b):
    za,zb=a['zone'],b['zone']
    if za.get('terrain_id')!=zb.get('terrain_id'):return False
    ga,gb=za.get('metric_geometry'),zb.get('metric_geometry')
    if not valid_geometry(ga) or not valid_geometry(gb):return False
    overlap=ga.intersection(gb).area/min(ga.area,gb.area)
    try:
        separation=Point(za['poi_easting'],za['poi_northing']).distance(Point(zb['poi_easting'],zb['poi_northing']))
        radius=min(za['max_clear_diameter_m'],zb['max_clear_diameter_m'])/2
    except (KeyError,TypeError,ValueError):return False
    return overlap>=0.8 and separation<=radius

def valid_geometry(geometry):
    return (geometry is not None and not geometry.is_empty and geometry.is_valid
            and geometry.geom_type in ('Polygon','MultiPolygon') and math.isfinite(geometry.area) and geometry.area>0)


def verification_details(assessed):
    missing=[{'gate':name,'reason_code':code,'message':code.replace('_',' ').capitalize()}
             for name,gate in assessed.get('gates',{}).items() if gate.state=='unknown'
             for code in (gate.reason_codes or (name+'_unverified',))]
    env=assessed.get('environment') or {};terrain=assessed.get('terrain') or {}
    if env.get('ground_firmness_state',terrain.get('ground_firmness_state'))!='verified':
        missing.append({'gate':'ground_firmness','reason_code':'ground_firmness_unverified','message':'Ground load bearing firmness requires verification; spectral surface classes cannot establish it.'})
    missing.extend([
        {'gate':'aircraft_policy','reason_code':'operational_limits_unverified','message':'Configured aircraft operational limits require authoritative verification.'},
        {'gate':'obstacles','reason_code':'obstacle_height_unverified','message':'Obstacle heights, canopy clearance and approach require verification.'},
    ])
    return dict(verification_state='excluded_known_failure' if assessed['state']=='fail' else 'requires_verification',missing_verification_reasons=missing,
                hard_check_state=assessed['state'],reason_codes=assessed.get('reason_codes',[]))


def rank_eligible(assessed_zones,mission,query_location,top_k,profile=None,research=False):
    scored=[];weights=mission['weights']
    for assessed in assessed_zones:
        if assessed['state']=='fail' or (not research and assessed['state']!='pass'):continue
        if research and not valid_geometry(assessed['zone'].get('metric_geometry')):continue
        if any(gate.state=='fail' for gate in assessed.get('gates',{}).values()):continue
        z=assessed['zone'];env=assessed.get('environment') or {};terrain=assessed.get('terrain') or {}
        temporal=z if any(key in z for key in ('temporal_open_confidence','temporal_support')) else terrain
        temporal_confidence=_fraction(temporal.get('temporal_open_confidence'))
        temporal_support=_fraction(temporal.get('temporal_support'))
        temporal_supported=temporal_confidence is not None and temporal_support is not None and temporal_support>0
        distance=distance_m(query_location,(z['latitude'],z['longitude']))
        weather=assessed.get('gates',{}).get('weather');we=weather.evidence if weather else {}
        surface_support=(terrain.get('surface_observations') or {}).get('scl',{}).get('observable_fraction')
        surface_supported=number(surface_support) is not None and 1-1e-12<=float(surface_support)<=1+1e-12
        terrain_supported=assessed.get('gates',{}).get('slope') is None or assessed['gates']['slope'].state=='pass'
        area_gate=assessed.get('gates',{}).get('area')
        area=area_gate.evidence.get('measured') if area_gate else z.get('area_m2')
        clearance=number(z.get('max_clear_diameter_m'))
        footprint=assessed.get('gates',{}).get('footprint')
        boundary_distance=number(footprint.evidence.get('actual_boundary_distance_m')) if footprint else None
        if boundary_distance is not None:
            clearance=min(clearance,boundary_distance*2) if clearance is not None else boundary_distance*2
        factors=dict(distance=_factor(distance,1000,True),clearance=_factor(clearance,30),
            area=_factor(area,1000),access=_factor(env.get('road_distance_m'),1000,True),
            slope=_factor(z.get('max_slope_deg'),10,True) if terrain_supported else None,roughness=_factor(terrain.get('mean_roughness_m'),1,True) if terrain_supported else None,
            openness=_fraction(env.get('openness_score')) if env.get('context_coverage_state')=='verified' else None,water=_factor(env.get('water_distance_m'),100),
            surface=_fraction(terrain.get('bare_surface_fraction')) if surface_supported else None,
            vegetation=_fraction(terrain.get('vegetation_fraction'),inverse=True) if surface_supported else None,
            weather=_factor(we.get('crosswind_kt'),20,True) if weather and weather.state=='pass' else None,
            temporal=temporal_confidence if temporal_supported else None)
        used={key:value for key,value in factors.items() if key in weights and value is not None and number(weights[key]) is not None and weights[key]>0}
        effective={key:weights[key]*(temporal_support if key=='temporal' else 1) for key in used}
        total=sum(effective.values())
        configured_total=sum(value for value in weights.values() if number(value) is not None and value>0)
        normalized={key:effective[key]/total for key in used} if total else {}
        contributions={key:used[key]*normalized[key] for key in used}
        speed=profile.get('cruise_speed_kt') if profile else None
        record={key:value for key,value in z.items() if key!='metric_geometry'}
        record.update(assessed_area_m2=area,assessed_clear_diameter_m=clearance,score=min(100.0,max(0.0,sum(contributions.values())*100)) if total else None,
            supported_factor_weight_coverage=total/configured_total if configured_total else 0,
            supported_factor_weight=total,configured_factor_weight=configured_total,
            score_complete=bool(configured_total and total/configured_total>=1-1e-12),score_kind='relative_mission_priority',
            score_factors=used,score_contributions=contributions,normalized_weights=normalized,effective_weights=effective,
            available_factors=factors,mission_excluded_factors=[key for key in factors if key not in weights],
            factor_evidence={'surface':{'meaning':'spectral bare-surface proportion; not ground firmness','date':terrain.get('surface_evidence_date'),'support':terrain.get('surface_observations'),'required_observable_fraction':1,'numerical_tolerance':1e-12,'scope':'parent_terrain'},
                'vegetation':{'meaning':'SCL vegetation proportion; not tree height or canopy clearance','date':terrain.get('surface_evidence_date')},
                'access':{'meaning':'nearest mapped road proximity; access permission and traversability remain separate','state':env.get('road_access_state'),'tags':env.get('road_tags')},
                'openness':{'meaning':'mapped surrounding occupancy in two dimensions; not an approach corridor','state':env.get('context_coverage_state')},
                'temporal':{'meaning':'historical open proportion among valid observed area; soft research priority, not landing clearance or a probability of safe landing',
                    'scope':'zone' if temporal is z else 'parent_terrain','confidence':temporal_confidence,'support':temporal_support,
                    'history_date_count':temporal.get('history_date_count'),'valid_history_count':temporal.get('valid_history_count'),
                    'history_dates':temporal.get('history_dates'),'source_ids':temporal.get('temporal_source_ids'),
                    'configured_weight':number(weights.get('temporal')) or 0,'effective_weight':effective.get('temporal',0),
                    'normalized_weight':normalized.get('temporal',0),'contribution':contributions.get('temporal',0),
                    'weight_policy':'heuristic research policy; effective weight = configured weight * support; not learned or calibrated',
                    'support_meaning':'valid historical area divided by entity area across requested history dates'}},
            missing_optional_factors=[key for key in weights if key not in used],distance_m=distance,
            straight_line_eta_minutes=distance/(speed*1852/60) if speed else None,
            eta_assumptions='Straight-line distance / configured cruise speed; excludes approach, terrain, route and fuel',
            deduplicated_zone_ids=[],gates={key:value.to_dict() for key,value in assessed.get('gates',{}).items()},
            state=assessed['state'],environment=env,terrain=terrain)
        factor_scales={'distance':('m',1000,True),'clearance':('m',30,False),'weather':('kt',20,True),
                       'area':('m2',1000,False),'slope':('degrees',10,True),'roughness':('m',1,True),
                       'access':('m',1000,True),'water':('m',100,False),
                       'surface':('fraction',None,False),'vegetation':('fraction',None,True),'openness':('fraction',None,False),
                       'temporal':('fraction',None,False)}
        for key,(units,scale,inverse) in factor_scales.items():
            record['factor_evidence'].setdefault(key,{}).update(units=units,scale=scale,
                transform=('1 - fraction' if inverse else 'fraction') if scale is None else ('scale / (scale + value)' if inverse else 'value / (scale + value)'),
                supported=factors[key] is not None)
        record['factor_evidence']['weather'].update(state=weather.state if weather else 'unknown',
            reason_codes=list(weather.reason_codes) if weather else ['weather_unavailable'],source=we.get('source'),
            observation_time_utc=we.get('observation_time_utc'),requested_at=we.get('requested_at'))
        record.update(verification_details(assessed))
        scored.append((record,assessed))
    scored.sort(key=lambda item:(-(item[0]['score'] if item[0]['score'] is not None else -1),item[0]['distance_m'],str(item[0].get('zone_id'))))
    unique=[]
    for record,assessed in scored:
        duplicate=next((prior for prior in unique if same_opportunity(prior[1],assessed)),None)
        if duplicate:duplicate[0]['deduplicated_zone_ids'].append(record['zone_id'])
        else:unique.append((record,assessed))
    results=[item[0] for item in unique[:top_k]]
    for rank,record in enumerate(results,1):record['rank']=rank
    return results


def rank_research(assessed_zones,mission,query_location,top_k,profile=None):
    return rank_eligible(assessed_zones,mission,query_location,top_k,profile,research=True)
