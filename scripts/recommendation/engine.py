"""Atomic selected-repository snapshot, strict gates and explained results."""
from copy import deepcopy
from threading import RLock
from datetime import datetime,timezone
from pyproj import CRS,Transformer
from shapely.geometry import mapping
from shapely.ops import transform
from helicopter_profiles import MISSION_CONTEXTS
from .inputs import InputError, validate_request, finite
from .contracts import GateDecision, RecommendationRequest,RecommendationResult,json_safe
from .weather_policy import assess_weather,WeatherSnapshotCache,distance_m
from .compatibility import assess_zone
from .ranking import rank_eligible,rank_research,same_opportunity,valid_geometry,verification_details

class RecommendationEngine:
    def __init__(self,repository,weather_service=None):
        self._lock=RLock();self._repository=repository
        self.weather_service=weather_service or WeatherSnapshotCache()
        self._validate_repository(repository,deep=False)

    @staticmethod
    def _validate_repository(repository,deep=True):
        if not repository.dataset_id or not repository.region_id:raise ValueError('Dataset identity is required')
        crs=CRS.from_user_input(repository.crs)
        if not crs.is_projected or any(axis.unit_conversion_factor!=1 for axis in crs.axis_info[:2]):
            raise ValueError('Knowledge geometry CRS must use projected metres')
        if deep:
            for z in repository.query_zones(internal=True):
                if not z.get('zone_id') or not z.get('terrain_id') or z.get('metric_geometry') is None:
                    raise ValueError('Incomplete knowledge zone')
                geometry=z['metric_geometry']
                if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ('Polygon','MultiPolygon'):
                    raise ValueError('Invalid knowledge geometry')

    def reload(self,repository):
        """Validate fully before swapping. Failure leaves selected snapshot intact."""
        self._validate_repository(repository)
        with self._lock:self._repository=repository

    def recommend(self,request,progress=None):
        def emit(phase,completed=None,total=None):
            if progress is not None:progress({'phase':phase,'completed':completed,'total':total})
        if not isinstance(request,RecommendationRequest):request=validate_request(request)
        with self._lock:repository=self._repository
        if request.dataset_id!=repository.dataset_id or request.region_id!=repository.region_id:
            raise InputError('Requested dataset/region does not match selected knowledge snapshot')
        # Include incompatible thresholds in evidence counts rather than silently
        # discarding measured hard-gate failures. Repository uses its spatial index.
        emit('retrieval')
        zones=repository.query_zones(latitude=request.latitude,longitude=request.longitude,
            radius_m=request.radius_km*1000,internal=True)
        emit('retrieval',len(zones),len(zones))
        emit('weather')
        metadata=deepcopy(repository.metadata)
        if request.weather is not None:
            snapshot=deepcopy(request.weather)
            if not isinstance(snapshot,dict):snapshot={'error':'Client weather must be an object'}
            snapshot['source']={**(snapshot.get('source') or {}),'provider':'user-supplied',
                'supplied_model_claim':(snapshot.get('source') or {}).get('model'),
                'model':'user-supplied evidence','verification':'unverified_client_input'}
        else:snapshot=self.weather_service.get_or_fetch((request.latitude,request.longitude),request.requested_at,request.policy)
        weather=assess_weather(snapshot,request.profile,request.requested_at,request.policy,request.policy.get('heading_deg'))
        transformer=Transformer.from_crs(repository.crs,'EPSG:4326',always_xy=True)
        assessed=[];counts={};uncertain=[];excluded=[];terrain_cache={}
        emit('hard_checks',0,len(zones))
        for position,z in enumerate(zones,1):
            if position%64==0:emit('hard_checks',position-1,len(zones))
            if z['terrain_id'] not in terrain_cache:
                terrain_cache[z['terrain_id']]=z.get('terrain_characteristics') if 'terrain_characteristics' in z else repository.get_terrain(z['terrain_id']) or {}
            terrain=terrain_cache[z['terrain_id']]
            env=z.get('environment') or ({} if 'restriction_state' in z else repository.get_environment(z['zone_id']) or {})
            # Repository joins characteristic/environment attributes on internal
            # zone records; separate records carry additional provenance.
            terrain={**terrain,**z};env={**z,**env}
            local_weather=weather
            try:
                location=snapshot['location']
                weather_location=(finite(location['latitude'],'weather latitude',-90,90),finite(location['longitude'],'weather longitude',-180,180))
                sep=distance_m((z['latitude'],z['longitude']),weather_location)
                if sep>request.policy['weather_coverage_radius_m']:
                    local_weather=GateDecision('unknown',
                        ('weather_location_not_covered',),{**weather.evidence,'location_separation_m':sep})
            except (KeyError,TypeError,ValueError):
                local_weather=GateDecision('unknown',('weather_location_unknown',),weather.evidence)
            item=assess_zone(z,terrain,env,request.profile,local_weather,request.policy)
            z.update(dataset_id=repository.dataset_id,region_id=repository.region_id,
                source_identity={'dataset_id':repository.dataset_id,'region_id':repository.region_id,
                    'date':metadata.get('date'),'analysis_run_id':metadata.get('analysis_run_id')},required_radius_m=request.profile['min_clear_diameter_m']/2,
                landing_reference=dict(latitude=z.get('latitude'),longitude=z.get('longitude'),
                    easting=z.get('poi_easting'),northing=z.get('poi_northing')))
            assessed.append(item)
            for name,gate in item['gates'].items():
                counts.setdefault(name,dict(pass_count=0,fail_count=0,unknown_count=0))[gate.state+'_count']+=1
            if item['state']!='pass':
                output={key:value for key,value in z.items() if key!='metric_geometry'}
                output.update(state=item['state'],reason_codes=item['reason_codes'],gates={key:value.to_dict() for key,value in item['gates'].items()},
                    distance_m=distance_m((request.latitude,request.longitude),(z['latitude'],z['longitude'])))
                output.update(verification_details(item))
                (excluded if item['state']=='fail' else uncertain).append(output)
        emit('hard_checks',len(zones),len(zones))
        emit('ranking')
        uncertain.sort(key=lambda value:(value['distance_m'],str(value['zone_id'])))
        excluded.sort(key=lambda value:(value['distance_m'],str(value['zone_id'])))
        uncertain_count=len(uncertain);excluded_count=len(excluded)
        by_id={item['zone']['zone_id']:item for item in assessed}
        def dedupe(values):
            unique=[];by_parent={}
            for value in values:
                siblings=by_parent.setdefault(value['terrain_id'],[])
                duplicate=next((prior for prior in siblings if same_opportunity(by_id[prior['zone_id']],by_id[value['zone_id']])),None)
                if duplicate:duplicate['deduplicated_zone_ids'].append(value['zone_id'])
                else:
                    value['deduplicated_zone_ids']=[];unique.append(value);siblings.append(value)
            return unique
        uncertain=dedupe(uncertain);excluded=dedupe(excluded)
        opportunity_counts=dict(uncertain=len(uncertain),excluded=len(excluded))
        uncertain=uncertain[:request.top_k];excluded=excluded[:request.top_k]
        mission={**deepcopy(MISSION_CONTEXTS[request.mission]),'configuration_revision':'2026-10-13-v1','configuration_status':'research_weights'}
        eligible_all=rank_eligible(assessed,mission,(request.latitude,request.longitude),len(assessed),request.profile)
        eligible=eligible_all[:request.top_k]
        research_all=rank_research(assessed,mission,(request.latitude,request.longitude),len(assessed),request.profile)
        research=research_all[:request.top_k]
        emit('geometry')
        for record in eligible+research+uncertain+excluded:
            geometry=by_id[record['zone_id']]['zone'].get('metric_geometry')
            record['geometry']=mapping(transform(transformer.transform,geometry)) if valid_geometry(geometry) else None
        limits=['Research profile limits remain unverified against authoritative operational specifications.',
            'Required footprint is two dimensional; obstacle heights and flight dynamics are unverified.',
            'One query-location weather snapshot is assessed only within declared spatial/time coverage.',
            'Uncertain opportunities are nearest-first exploratory evidence, without suitability scores.']
        result=RecommendationResult(repository.dataset_id,repository.region_id,request.to_dict(),request.profile,mission,
            len(zones),counts,json_safe(eligible),json_safe(uncertain),json_safe(excluded),limits,json_safe(metadata))
        result.eligible_count=sum(item['state']=='pass' for item in assessed)
        result.uncertain_count=uncertain_count;result.excluded_count=excluded_count;result.opportunity_counts=opportunity_counts
        result.research_candidates=json_safe(research)
        result.research_count=sum(item['state']!='fail' and valid_geometry(item['zone'].get('metric_geometry')) for item in assessed)
        result.distinct_opportunity_counts={**opportunity_counts,'research':len(research_all),
            'eligible':len(eligible_all)}
        result.verification_state='requires_verification' if research else 'no_research_candidates'
        emit('complete',1,1)
        return result
