import json
import pytest
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box
from scripts.knowledge.chronology import validate_new_date
from scripts.knowledge.temporal import measure_overlap, aggregate_observations, validate_history_raster
from scripts.pipeline.monthly import month_buckets, group_monthly


def test_chronology_rejects_equal_older_future():
    for day in ('2026-06-01','2026-05-31','2099-01-01'):
        with pytest.raises(ValueError):validate_new_date(day,'2026-06-01',today='2026-10-14')
    assert validate_new_date('2026-06-02','2026-06-01',today='2026-10-14')=='2026-06-02'


def raster(tmp_path,values,crs=32643):
    path=tmp_path/'state.tif'
    with rasterio.open(path,'w',driver='GTiff',width=2,height=2,count=1,dtype='uint8',crs=crs,transform=from_origin(0,2,1,1),nodata=255) as ds:ds.write(np.array(values,dtype='uint8'),1)
    return path


def test_overlap_exact_fraction_hole_and_outside_support(tmp_path):
    path=raster(tmp_path,[[1,0],[255,1]])
    geom=box(-1,0,2,2).difference(box(0.5,1.5,1,2))
    row=measure_overlap(geom,32643,path)
    assert row['open_area_m2']==pytest.approx(1.75)
    assert row['valid_area_m2']==pytest.approx(2.75)
    assert row['unknown_area_m2']==pytest.approx(3)
    assert row['valid_area_m2']+row['unknown_area_m2']==pytest.approx(geom.area)


def test_invalid_encoding_crs_and_zero_valid(tmp_path):
    with pytest.raises(ValueError,match='class'):validate_history_raster(raster(tmp_path,[[3,0],[1,255]]))
    with pytest.raises(ValueError,match='metric'):validate_history_raster(raster(tmp_path,[[1,0],[1,255]],4326))
    result=aggregate_observations(100,[{'date':'2026-01-01','source_id':'x','open_area_m2':0,'valid_area_m2':0,'unknown_area_m2':100}])
    assert result['temporal_open_confidence'] is None and result['temporal_support']==0


def test_history_date_duplicate_rejected():
    rows=[{'date':'2026-01-01','source_id':s,'open_area_m2':1,'valid_area_m2':2,'unknown_area_m2':0} for s in ('a','b')]
    with pytest.raises(ValueError,match='date'):aggregate_observations(2,rows)


def test_months_missing_and_same_day_grouping():
    buckets=month_buckets('2026-10-14')
    assert len(buckets)==12 and buckets[0]['month']=='2025-11' and buckets[-1]['end_date']=='2026-10-14'
    products=[{'id':'b','date':'2026-10-01','cloud_fraction':.1,'coverage_fraction':.4},{'id':'a','date':'2026-10-01','cloud_fraction':.2,'coverage_fraction':.7}]
    months=group_monthly(buckets,products)
    assert months[0]['status']=='missing'
    assert months[-1]['observations'][0]['product_ids']==['a','b']
    assert months[-1]['observations'][0]['qa_state']=='metadata_only'

def test_activation_race_and_publication_recheck_preserve_pointer(tmp_path):
    from test_knowledge_repository import package_data
    from scripts.knowledge.repository import write_package,register_dataset,activate_dataset
    registry=tmp_path/'registry.json'
    for identity,day in [('baseline','2026-06-01'),('stale','2026-07-01'),('newest','2026-08-01')]:
        data=package_data();data['metadata'].update(dataset_id=identity,date=day)
        for frame in (data['terrain'],data['zones']):frame['dataset_id']=identity
        path=tmp_path/(identity+'.gpkg');write_package(data,path);register_dataset(identity,path,registry)
    activate_dataset('baseline',registry);activate_dataset('newest',registry)
    before=registry.read_bytes()
    with pytest.raises(ValueError,match='later than current'):activate_dataset('stale',registry)
    with pytest.raises(ValueError,match='later than current'):register_dataset('stale',tmp_path/'stale.gpkg',registry,require_forward=True)
    assert before==registry.read_bytes()


def test_normalized_temporal_parent_child_repository_roundtrip(tmp_path):
    from test_knowledge_repository import package_data
    from scripts.knowledge.repository import write_package,KnowledgeRepository
    data=package_data()
    row={'dataset_id':'d','date':'2026-01-01','source_id':'history','open_area_m2':50,'valid_area_m2':100,'unknown_area_m2':14300,'coverage_fraction':1,'qa_state':'measured'}
    data['sources']['history']={'source_id':'history','sha256':'historyhash'}
    data['temporal_observations']=[dict(row,entity_type='terrain',entity_id='p'),dict(row,entity_type='zones',entity_id='z',unknown_area_m2=9900)]
    data['temporal_aggregates']=[{'dataset_id':'d','entity_type':kind,'entity_id':identity,**aggregate_observations(area,[row])} for kind,identity,area in [('terrain','p',14400),('zones','z',10000)]]
    path=tmp_path/'temporal.gpkg';write_package(data,path);repo=KnowledgeRepository(path)
    assert repo.get_terrain('p')['temporal_open_confidence']==.5
    assert repo.get_zone('z')['temporal_support']==.01
    assert len(repo.temporal_observations('zones','z'))==1


def test_workflow_and_named_build_reject_old_dates_paths_and_preserve_current(tmp_path):
    from flask import Flask
    from scripts.ui.api import register_api
    registry=tmp_path/'data/knowledge/registry.json';registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({'selected':{'bhadra':'current'},'datasets':{'current':{'region_id':'bhadra','date':'2026-06-01'}}}))
    app=Flask(__name__);register_api(app,tmp_path);client=app.test_client();before=registry.read_bytes()
    metadata=client.get('/api/knowledge/workflow?region_id=bhadra').json
    assert metadata['minimum_new_date']=='2026-06-02' and metadata['current_dataset_id']=='current'
    for day in ('2026-06-01','2026-01-01','2099-01-01'):
        response=client.post('/api/knowledge/build',headers={'X-HELPS-Role':'engineer'},json={'region_id':'bhadra','date':day,'source_choices':{}})
        assert response.status_code==400
    response=client.post('/api/knowledge/build',headers={'X-HELPS-Role':'engineer'},json={'region_id':'bhadra','date':'2026-08-01','source_choices':{'aoi':'../../secret'}})
    assert response.status_code==400
    assert before==registry.read_bytes()


def test_scl_quality_measured_area_and_cloud_unknown(tmp_path):
    from scripts.pipeline.monthly import measure_scl_quality
    import geopandas as gpd
    path=raster(tmp_path,[[4,8],[0,5]])
    region=gpd.GeoDataFrame(geometry=[box(0,0,2,2)],crs=32643)
    qa=measure_scl_quality(path,region)
    assert qa['qa_state']=='measured' and qa['usable_support']==.5
    assert qa['cloud_shadow_fraction']==.25 and qa['coverage_fraction']==.75

def test_cross_crs_overlap_uses_current_entity_area_basis(tmp_path):
    from pyproj import Transformer
    from shapely.ops import transform
    path=raster(tmp_path,[[1,0],[1,0]],3857)
    entity=transform(Transformer.from_crs(3857,32643,always_xy=True).transform,box(0,0,2,2))
    row=measure_overlap(entity,32643,path)
    assert row['valid_area_m2']+row['unknown_area_m2']==pytest.approx(entity.area)
    # Both states are valid. All support is measured on the entity's own CRS.
    result=aggregate_observations(entity.area,[dict(row,date='2026-01-01',source_id='cross')])
    assert result['temporal_support']==pytest.approx(1,abs=1e-6)
    assert result['temporal_open_confidence']==pytest.approx(.5,abs=1e-6)


def test_managed_classification_rolls_into_next_version_history(tmp_path):
    from scripts.knowledge.temporal import discover_managed_history,register_observation
    from scripts.knowledge.repository import write_package,register_dataset,activate_dataset
    from test_knowledge_repository import package_data
    import shutil
    folder=tmp_path/'data/knowledge/july';folder.mkdir(parents=True)
    original=raster(tmp_path,[[1,0],[1,255]]);path=folder/'classification.tif';shutil.copyfile(original,path)
    source={'source_id':'july-classification','region_id':'r','date':'2026-07-01','path':str(path),'status':'available','provenance_state':'generated_from_date_validated_sources',**validate_history_raster(path)}
    data=package_data();data['metadata'].update(date='2026-07-01',observation_source=source)
    package=folder/'knowledge.gpkg';write_package(data,package);registry=tmp_path/'data/knowledge/registry.json';register_dataset('d',package,registry);activate_dataset('d',registry)
    history=discover_managed_history(tmp_path,json.loads(registry.read_text()),'r','2026-08-01')
    assert len(history)==1 and history[0]['date']=='2026-07-01' and history[0]['path']==str(path)
    assert history[0]['sha256']==source['sha256']
    assert discover_managed_history(tmp_path,json.loads(registry.read_text()),'r','2026-07-01')==[]

def test_monthly_provider_errors_bounded_and_no_fake_observations(tmp_path,monkeypatch):
    from scripts.pipeline.monthly import catalog_search
    import geopandas as gpd
    import requests
    monkeypatch.setenv('CDSE_CLIENT_ID','fixture-client');monkeypatch.setenv('CDSE_CLIENT_SECRET','fixture-secret')
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'access_token':'fixture-token'}
    class Session:
        def __init__(self):self.calls=[]
        def post(self,url,**kwargs):
            self.calls.append(url)
            if url.endswith('token'):return Response()
            raise requests.Timeout('fixture provider timeout')
    session=Session();region=gpd.GeoDataFrame(geometry=[box(75,13,75.01,13.01)],crs=4326)
    result=catalog_search(region,'2026-10-14',tmp_path,session=session,measure_shortlist=False)
    assert len(session.calls)==13 and len(result['months'])==12 and len(result['errors'])==12
    assert result['status']=='partial' and result['observations']==[]
    assert all(month['status']=='failed' for month in result['months'])
    assert 'fixture-secret' not in json.dumps(result)


def test_metadata_footprint_mosaic_counts_overlap_once():
    from shapely.geometry import mapping
    products=[{'id':identity,'date':'2026-10-01','cloud_fraction':.1,'geometry':mapping(geom)} for identity,geom in [('a',box(75,13,75.007,13.01)),('b',box(75.003,13,75.01,13.01))]]
    month=group_monthly(month_buckets('2026-10-14'),products,box(75,13,75.01,13.01))[-1]
    row=month['observations'][0]
    assert row['coverage_fraction']==pytest.approx(1) and row['qa_state']=='metadata_only'
    assert row['usable_support'] is None


def test_nonconserving_temporal_rows_cannot_publish(tmp_path):
    from test_knowledge_repository import package_data
    from scripts.knowledge.repository import write_package
    data=package_data();data['sources']['history']={'source_id':'history','sha256':'historyhash'}
    data['temporal_observations']=[{'dataset_id':'d','entity_type':'terrain','entity_id':'p','date':'2026-01-01','source_id':'history','open_area_m2':50,'valid_area_m2':100,'unknown_area_m2':0}]
    with pytest.raises(ValueError,match='conserve'):write_package(data,tmp_path/'bad.gpkg')

def test_two_actual_builds_reuse_previous_current_classification(tmp_path):
    from test_knowledge_sources import fixture_spec
    from scripts.knowledge.contracts import SourceAsset
    from scripts.knowledge.build import build_knowledge
    from scripts.knowledge.repository import register_dataset,activate_dataset,KnowledgeRepository
    from scripts.knowledge.temporal import discover_managed_history
    from rasterio.transform import from_origin
    registry_path=tmp_path/'data/knowledge/registry.json'
    def dated_spec(identity,day):
        inputs=tmp_path/identity;inputs.mkdir()
        spec=fixture_spec(inputs);spec.dataset_id=identity;spec.region_id='r';spec.date=day;spec.output_dir=tmp_path/'data/knowledge'/identity
        spec.parameters={'resolution_m':30,'min_area_m2':0,'min_width_m':0,'min_length_m':0,'min_clear_radius_m':0,'slope_thresholds_deg':[0]}
        spectral=inputs/'spectral.tif';scl=inputs/'scl.tif';profile={'driver':'GTiff','width':60,'height':60,'crs':32643,'transform':from_origin(-100,300,10,10),'nodata':0}
        with rasterio.open(spectral,'w',count=6,dtype='float32',**profile) as ds:
            ds.write(np.full((6,60,60),.2,dtype='float32'));ds.update_tags(observation_date=day)
        with rasterio.open(scl,'w',count=1,dtype='uint8',**profile) as ds:
            ds.write(np.full((60,60),5,dtype='uint8'),1);ds.update_tags(observation_date=day)
        spec.sources={'spectral':SourceAsset(identity+'-spectral',spectral,kind='spectral',date=day,metadata={'band_map':{'blue':1,'green':2,'red':3,'nir':4}}),'scl':SourceAsset(identity+'-scl',scl,kind='scl',date=day)}
        return spec
    first=build_knowledge(dated_spec('july','2026-07-01'),log=lambda message:None)
    register_dataset('july',first.package_path,registry_path);activate_dataset('july',registry_path)
    second_spec=dated_spec('august','2026-08-01')
    second_spec.parameters['_history_sources']=discover_managed_history(tmp_path,json.loads(registry_path.read_text()),'r',second_spec.date)
    second=build_knowledge(second_spec,log=lambda message:None)
    repo=KnowledgeRepository(second.package_path)
    assert repo.get_terrain('a')['history_dates']==['2026-07-01']
    assert repo.get_terrain('a')['temporal_support']==pytest.approx(1)
    assert repo.temporal_observations('terrain','a')[0]['source_id']=='july-classification'
    register_dataset('august',second.package_path,registry_path,require_forward=True);activate_dataset('august',registry_path)
    assert json.loads(registry_path.read_text())['selected']['r']=='august'
    assert KnowledgeRepository(first.package_path).get_terrain('a')['history_dates']==[]

def test_activation_rejects_stale_temporal_snapshot_even_when_date_is_newer(tmp_path):
    from test_knowledge_repository import package_data
    from scripts.knowledge.repository import write_package,register_dataset,activate_dataset
    folder=tmp_path/'data/knowledge/july';folder.mkdir(parents=True)
    state=raster(tmp_path,[[1,0],[1,255]])
    source={'source_id':'july-classification','region_id':'r','date':'2026-07-01','path':str(state),'status':'available','provenance_state':'fixture',**validate_history_raster(state)}
    registry=tmp_path/'data/knowledge/registry.json'
    for identity,day in [('july','2026-07-01'),('august','2026-08-01')]:
        data=package_data();data['metadata'].update(dataset_id=identity,date=day)
        for frame in (data['terrain'],data['zones']):frame['dataset_id']=identity
        if identity=='july':data['metadata']['observation_source']=source
        path=tmp_path/(identity+'.gpkg');write_package(data,path);register_dataset(identity,path,registry)
    activate_dataset('july',registry);before=registry.read_bytes()
    with pytest.raises(ValueError,match='History changed since build'):activate_dataset('august',registry)
    with pytest.raises(ValueError,match='History changed since build'):register_dataset('august',tmp_path/'august.gpkg',registry,require_forward=True)
    assert registry.read_bytes()==before

def test_concurrent_activations_preserve_newest_observation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from test_knowledge_repository import package_data
    from scripts.knowledge.repository import write_package,register_dataset,activate_dataset
    registry=tmp_path/'registry.json'
    for identity,day in [('july','2026-07-01'),('august','2026-08-01')]:
        data=package_data();data['metadata'].update(dataset_id=identity,date=day)
        for frame in (data['terrain'],data['zones']):frame['dataset_id']=identity
        path=tmp_path/(identity+'.gpkg');write_package(data,path);register_dataset(identity,path,registry)
    def activate(identity):
        try:return activate_dataset(identity,registry)
        except ValueError as exc:return str(exc)
    with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(activate,['august','july']))
    assert json.loads(registry.read_text())['selected']['r']=='august'
    assert any(isinstance(result,dict) and result['dataset_id']=='august' for result in results)

def test_scl_water_and_unclassified_never_gain_ground_support(tmp_path):
    from scripts.pipeline.monthly import measure_scl_quality
    import geopandas as gpd
    path=raster(tmp_path,[[6,7],[0,5]])
    region=gpd.GeoDataFrame(geometry=[box(0,0,2,2)],crs=32643)
    row=measure_scl_quality(path,region)
    assert row['usable_support']==.25 and row['coverage_fraction']==.75
