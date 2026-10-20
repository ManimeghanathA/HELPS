from datetime import datetime,timezone
from copy import deepcopy
import json
import pytest
from shapely.geometry import box
from scripts.recommendation.inputs import validate_request,InputError

NOW=datetime.now(timezone.utc)
class Repository:
    dataset_id='synthetic';region_id='bhadra';crs='EPSG:32643';metadata={'source':'synthetic-test-only','date':'2026-10-13'}
    def __init__(self,records):self.records=records;self.queries=[]
    def query_zones(self,**kwargs):self.queries.append(kwargs);return deepcopy(self.records)
    def get_terrain(self,identity):return {}
    def get_environment(self,identity):return {}

def zone(identity='z'):
    return dict(zone_id=identity,terrain_id='t',latitude=13.5,longitude=75.5,area_m2=1600,
        max_clear_diameter_m=40,max_slope_deg=2,slope_threshold_deg=4,dem_valid_fraction=1,
        poi_easting=550000,poi_northing=1490000,metric_geometry=box(549980,1489980,550020,1490020),
        surface_type='Grass',surface_verified=True,restriction_state='verified_clear')
def request(**kw):
    p=dict(dataset_id='synthetic',region_id='bhadra',latitude=13.5,longitude=75.5,model_id='hal_dhruv',
        mission='medevac',requested_at=NOW.isoformat(),policy=dict(heading_deg=270));p.update(kw);return validate_request(p)
class Weather:
    def get_or_fetch(self,location,at,policy):
        return dict(location=dict(latitude=location[0],longitude=location[1]),observation_time_utc=at.isoformat(),
            wind=dict(speed_kt=10,gust_kt=15,direction_deg=270),visibility_m=5000,precipitation=dict(current_hour_mm=0),
            source=dict(provider='fixture',model='forecast',retrieved_at_utc=NOW.isoformat()))

def test_engine_uses_index_query_and_exports_exact_geometry_identity():
    from scripts.recommendation.engine import RecommendationEngine
    repo=Repository([zone()]);result=RecommendationEngine(repo,Weather()).recommend(request()).to_dict()
    assert repo.queries[0]['radius_m']==20000
    assert repo.queries[0]['internal'] is True
    assert result['candidate_count']==1
    assert result['eligible_spots'][0]['geometry']['type']=='Polygon'
    assert result['eligible_spots'][0]['dataset_id']=='synthetic'
    assert result['dataset']['source']=='synthetic-test-only'
    json.dumps(result,allow_nan=False)

def test_failed_unknown_and_empty_are_explained_separately():
    from scripts.recommendation.engine import RecommendationEngine
    fail=zone('fail');fail['max_slope_deg']=30
    unknown=zone('unknown');unknown['surface_verified']=False
    engine=RecommendationEngine(Repository([fail,unknown]),Weather())
    result=engine.recommend(request()).to_dict()
    assert not result['eligible_spots']
    assert result['excluded'][0]['zone_id']=='fail'
    assert result['uncertain'][0]['zone_id']=='unknown'
    assert 'score' not in result['uncertain'][0]
    assert RecommendationEngine(Repository([]),Weather()).recommend(request()).candidate_count==0

def test_wrong_dataset_and_failed_reload_preserve_snapshot():
    from scripts.recommendation.engine import RecommendationEngine
    engine=RecommendationEngine(Repository([zone()]),Weather())
    with pytest.raises(InputError):engine.recommend(request(dataset_id='other'))
    with pytest.raises(ValueError):engine.reload(Repository([{'zone_id':'bad'}]))
    assert engine.recommend(request()).eligible_spots[0]['zone_id']=='z'

def test_client_weather_cannot_claim_provider_provenance():
    from scripts.recommendation.engine import RecommendationEngine
    weather=Weather().get_or_fetch((13.5,75.5),NOW,{})
    result=RecommendationEngine(Repository([zone()]),Weather()).recommend(request(weather=weather)).to_dict()
    evidence=result['eligible_spots'][0]['gates']['weather']['evidence']
    assert evidence['source']['provider']=='user-supplied'
    assert evidence['source']['verification']=='unverified_client_input'

def test_client_archive_classification_survives_provenance_relabeling():
    from scripts.recommendation.engine import RecommendationEngine
    weather=Weather().get_or_fetch((13.5,75.5),NOW,{})
    weather['source']['model']='archive ERA5 reanalysis'
    result=RecommendationEngine(Repository([zone()]),Weather()).recommend(request(weather=weather)).to_dict()
    assert not result['eligible_spots']
    evidence=result['uncertain'][0]['gates']['weather']['evidence']
    assert evidence['historical'] is True
    assert evidence['source']['provider']=='user-supplied'
    assert evidence['source']['supplied_model_claim']=='archive ERA5 reanalysis'

def test_weather_coverage_does_not_extend_to_entire_region():
    from scripts.recommendation.engine import RecommendationEngine
    distant=zone();distant['latitude']=13.6
    result=RecommendationEngine(Repository([distant]),Weather()).recommend(request()).to_dict()
    assert not result['eligible_spots']
    assert 'weather_location_not_covered' in result['uncertain'][0]['reason_codes']

def test_exploratory_geometry_is_deduplicated_bounded_with_total_counts():
    from scripts.recommendation.engine import RecommendationEngine
    records=[]
    for i in range(12):
        z=zone(str(i));z['surface_verified']=False;records.append(z)
    result=RecommendationEngine(Repository(records),Weather()).recommend(request(top_k=2)).to_dict()
    assert result['uncertain_count']==12
    assert len(result['uncertain'])==1
    assert len(result['uncertain'][0]['deduplicated_zone_ids'])==11
    assert 'source' not in result['uncertain'][0]['source_identity']

def test_real_package_index_geometry_and_measured_factor_integration(tmp_path):
    import geopandas as gpd
    import pandas as pd
    from pyproj import Transformer
    from shapely.geometry import Polygon,Point
    from scripts.knowledge.repository import write_package,KnowledgeRepository
    from scripts.recommendation.engine import RecommendationEngine
    outer=box(500010,1500010,500110,1500110)
    hole=box(500068,1500058,500070,1500062)
    holey=Polygon(outer.exterior.coords,[hole.exterior.coords])
    reverse=Transformer.from_crs(32643,4326,always_xy=True)
    lon,lat=reverse.transform(500060,1500060)
    rows=[]
    for identity,geometry,x in [('pass',outer,500060),('hole',holey,500060),('outside-radius',box(502010,1500010,502110,1500110),502060)]:
        longitude,latitude=reverse.transform(x,1500060)
        rows.append(dict(zone_id=identity,terrain_id='p',dataset_id='synthetic',slope_threshold_deg=6 if identity=='hole' else 4,
            area_m2=geometry.area,max_clear_diameter_m=100,max_slope_deg=2,dem_valid_fraction=1,
            mean_roughness_m=.2,poi_easting=x,poi_northing=1500060,longitude=longitude,latitude=latitude,geometry=geometry))
    data=dict(metadata=dict(dataset_id='synthetic',region_id='bhadra',date='2026-10-13'),
        terrain=gpd.GeoDataFrame([dict(terrain_id='p',source_zone_id='p',dataset_id='synthetic',geometry=box(500000,1500000,503000,1501000))],crs=32643),
        zones=gpd.GeoDataFrame(rows,crs=32643),
        characteristics=pd.DataFrame([dict(terrain_id='p',surface_type='Grass',surface_verified=True,mean_roughness_m=8)]),
        environment=pd.DataFrame([dict(zone_id=r['zone_id'],restriction_state='verified_clear',openness_score=.8,context_coverage_state='verified',road_distance_m=25) for r in rows]),
        sources={'dem':dict(source_id='synthetic-dem',sha256='test-only',crs='EPSG:32643')})
    package=tmp_path/'knowledge.gpkg';write_package(data,package);repo=KnowledgeRepository(package)
    indexed=repo.query_zones(latitude=lat,longitude=lon,radius_m=200,internal=True)
    brute=[r for r in repo.list_zones(internal=True) if r['metric_geometry'].distance(Point(500060,1500060))<=200]
    assert {r['zone_id'] for r in indexed}=={r['zone_id'] for r in brute}=={'pass','hole'}
    result=RecommendationEngine(repo,Weather()).recommend(request(latitude=lat,longitude=lon,radius_km=.2,
        mission='safest_landing',weather=Weather().get_or_fetch((lat,lon),NOW,{}))).to_dict()
    assert result['candidate_count']==2
    assert result['eligible_spots'][0]['zone_id']=='pass'
    assert result['eligible_spots'][0]['score_factors']['roughness']==pytest.approx(1/1.2)
    assert result['eligible_spots'][0]['score_factors']['openness']==.8
    assert len(result['excluded'][0]['geometry']['coordinates'])==2
    assert 'footprint_crosses_boundary' in result['excluded'][0]['reason_codes']
    assert result['dataset']['dataset_id']=='synthetic'
    json.dumps(result,allow_nan=False)

def test_full_offline_build_keeps_unknown_evidence_separate_from_recommendations(tmp_path):
    from test_knowledge_sources import fixture_spec
    from scripts.knowledge.build import build_knowledge
    from scripts.knowledge.repository import KnowledgeRepository
    from scripts.recommendation.engine import RecommendationEngine
    spec=fixture_spec(tmp_path)
    spec.parameters={'min_area_m2':0,'min_width_m':0,'min_length_m':0,'min_clear_radius_m':0,'slope_thresholds_deg':[0,2,4]}
    build=build_knowledge(spec);repo=KnowledgeRepository(build.package_path)
    first=repo.list_zones()[0]
    result=RecommendationEngine(repo,Weather()).recommend(request(dataset_id=repo.dataset_id,region_id=repo.region_id,
        latitude=first['latitude'],longitude=first['longitude'])).to_dict()
    assert result['candidate_count']==6
    assert not result['eligible_spots']
    assert result['gate_counts']['surface']['unknown_count']==6
    assert result['gate_counts']['restrictions']['unknown_count']==6
    assert result['uncertain']
    assert result['uncertain'][0]['source_identity']['dataset_id']==repo.dataset_id


def test_observed_progress_preserves_full_scoring_gates_and_geometry(monkeypatch):
    import scripts.recommendation.weather_policy as weather_policy
    class FixedClock(datetime):
        @classmethod
        def now(cls,tz=None):return NOW
    monkeypatch.setattr(weather_policy,'datetime',FixedClock)
    from scripts.recommendation.engine import RecommendationEngine
    fail=zone('excluded');fail['max_slope_deg']=30
    records=[zone(),fail]
    baseline=RecommendationEngine(Repository(records),Weather()).recommend(request()).to_dict()
    observed=[]
    result=RecommendationEngine(Repository(records),Weather()).recommend(request(),progress=observed.append).to_dict()
    assert result==baseline
    assert {'retrieval','weather','hard_checks','ranking','geometry','complete'}<=set(r['phase'] for r in observed)
    checks=[r for r in observed if r['phase']=='hard_checks']
    assert checks[-1]['completed']==checks[-1]['total']==2
