import io
import json
import pytest
from flask import Flask


@pytest.mark.parametrize('source_layout',['build','enrichment','dated_scl_list'])
def test_workflow_reads_scan_and_enrichment_source_layouts_without_losing_chronology(tmp_path,monkeypatch,source_layout):
    from scripts.ui.api import register_api
    folder=tmp_path/'data/knowledge';folder.mkdir(parents=True)
    boundary=folder/'area.geojson';boundary.write_text('{"type":"FeatureCollection","features":[]}')
    scl=folder/'scl.tif';scl.write_bytes(b'fixture')
    (folder/'regions.json').write_text(json.dumps({'area':{'region_id':'area','name':'Area','aoi':{'source_id':'area','path':str(boundary),'kind':'aoi'}}}))
    sources={'scl':{'path':str(scl)}} if source_layout=='build' else ([{'source_id':'older-history','date':'2026-05-01','scl_path':str(scl)}] if source_layout=='enrichment' else [{'source_id':'scl','kind':'scl','date':'2026-06-01','path':str(scl)}])
    (folder/'manifest.json').write_text(json.dumps({'source_records':sources}))
    (folder/'registry.json').write_text(json.dumps({'selected':{'area':'current'},'datasets':{'current':{'region_id':'area','date':'2026-06-01','package_path':str(folder/'knowledge.gpkg')}}}))
    seen=[]
    def measure(root,aoi,path):seen.append(path);return {'qa_state':'measured','cloud_fraction':.1}
    monkeypatch.setattr('scripts.ui.inventory_qa.scl_inventory_quality',measure)
    app=Flask(__name__);app.config['TESTING']=True;register_api(app,tmp_path)
    response=app.test_client().get('/api/knowledge/workflow?region_id=area')
    assert response.status_code==200
    data=response.get_json();assert data['current_dataset_id']=='current' and data['minimum_new_date']=='2026-06-02'
    assert bool(seen)==(source_layout!='enrichment')  # Never measure May evidence as June QA.


@pytest.mark.parametrize('historical',[False,True])
def test_date_search_only_suggests_newer_dates_unless_explicit_history(tmp_path,monkeypatch,historical):
    from scripts.ui.api import register_api
    from time import sleep
    folder=tmp_path/'data/knowledge';folder.mkdir(parents=True)
    boundary=folder/'area.geojson';boundary.write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':{'type':'Polygon','coordinates':[[[75,13],[75.01,13],[75.01,13.01],[75,13.01],[75,13]]]}}]}))
    (folder/'regions.json').write_text(json.dumps({'area':{'region_id':'area','name':'Area','aoi':{'source_id':'area','path':str(boundary),'kind':'aoi'}}}))
    (folder/'registry.json').write_text(json.dumps({'selected':{'area':'current'},'datasets':{'current':{'region_id':'area','date':'2026-06-01'}}}))
    seen=[]
    def search(*args,**kwargs):seen.append(kwargs['start_date']);return {'status':'completed','months':[],'observations':[],'errors':[]}
    monkeypatch.setattr('scripts.pipeline.monthly.catalog_search',search)
    app=Flask(__name__);app.config['TESTING']=True;register_api(app,tmp_path);c=app.test_client()
    response=c.post('/api/knowledge/imagery-search',json={'region_id':'area','end_date':'2026-06-21','history_search':historical,'start_date':'2026-05-01'},headers={'X-HELPS-Role':'engineer'})
    assert response.status_code==202
    for _ in range(100):
        if seen:break
        sleep(.01)
    assert seen==['2026-05-01' if historical else '2026-06-02']


def client(root):
    from scripts.ui.unified_api import register_unified_api
    app=Flask(__name__); app.config['TESTING']=True
    register_unified_api(app,root)
    return app.test_client()


def test_credentials_masked_and_guarded(tmp_path,monkeypatch):
    monkeypatch.delenv('CDSE_CLIENT_SECRET',raising=False)
    c=client(tmp_path)
    assert c.post('/api/knowledge/credentials',json={'CDSE_CLIENT_SECRET':'private-value'}).status_code==403
    response=c.post('/api/knowledge/credentials',json={'CDSE_CLIENT_SECRET':'private-value'},headers={'X-HELPS-Role':'engineer'})
    assert response.status_code==200
    status=c.get('/api/knowledge/credentials').get_json()
    assert status['credentials']['CDSE_CLIENT_SECRET']['configured']
    assert 'private-value' not in json.dumps(status)
    assert 'private-value' in (tmp_path/'.env').read_text()


def test_register_real_boundary_and_reject_invalid(tmp_path):
    c=client(tmp_path)
    geometry={'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':{'type':'Polygon','coordinates':[[[75,13],[75.01,13],[75.01,13.01],[75,13.01],[75,13]]]}}]}
    response=c.post('/api/knowledge/regions',data={'name':'New test area','file':(io.BytesIO(json.dumps(geometry).encode()),'boundary.geojson')},headers={'X-HELPS-Role':'engineer'})
    assert response.status_code==201, response.get_json()
    region=response.get_json()['region']
    assert region['region_id']=='new-test-area'
    from scripts.ui.unified_api import region_catalog
    assert region_catalog(tmp_path,region['region_id'])['aoi']['kind']=='aoi'
    geometry['features'][0]['geometry']={'type':'Point','coordinates':[75,13]}
    assert c.post('/api/knowledge/regions',data={'name':'Bad','file':(io.BytesIO(json.dumps(geometry).encode()),'boundary.geojson')},headers={'X-HELPS-Role':'engineer'}).status_code==400


def test_month_range_truncates_first_month():
    from scripts.pipeline.monthly import month_buckets
    rows=month_buckets('2026-06-21',start_date='2026-03-17')
    assert len(rows)==4
    assert rows[0]['start_date']=='2026-03-17'
    assert rows[-1]['end_date']=='2026-06-21'


def test_completed_stage_progress_is_not_timer_based():
    from scripts.ui.jobs import JobManager
    manager=JobManager()
    job={'history':[],'progress':{'percent':None,'completed_stages':[],'total_stages':8,'indeterminate':True}}
    manager._event(job,'running','Downloading provider tile')
    assert job['progress']['percent'] is None
    manager._event(job,'running','sources: complete (0.03s)')
    manager._event(job,'running','sources: complete (0.03s)')
    assert job['progress']['percent']==12
    assert job['progress']['completed_stages']==['sources']


def test_new_region_workflow_has_no_baseline_sources_or_history(tmp_path):
    from scripts.ui.api import register_api
    from scripts.ui.unified_api import register_unified_api
    folder=tmp_path/'data/knowledge';folder.mkdir(parents=True)
    boundary=folder/'area.geojson';boundary.write_text('{"type":"FeatureCollection","features":[]}')
    (folder/'regions.json').write_text(json.dumps({'area':{'region_id':'area','name':'Area','aoi':{'source_id':'area','path':str(boundary),'kind':'aoi'}}}))
    app=Flask(__name__);register_api(app,tmp_path);register_unified_api(app,tmp_path)
    result=app.test_client().get('/api/knowledge/workflow?region_id=area').get_json()
    assert result['current_date'] is None
    assert result['history']==[]
    assert [s['slot'] for s in result['sources']]==['aoi']


def test_registered_region_build_uses_its_own_aoi_and_uploaded_dem(tmp_path,monkeypatch):
    from scripts.ui.api import register_api
    from scripts.ui.unified_api import register_unified_api
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    from time import sleep
    folder=tmp_path/'data/knowledge';folder.mkdir(parents=True)
    boundary=folder/'area.geojson'
    gpd.GeoDataFrame(geometry=[box(75,13,75.01,13.01)],crs=4326).to_file(boundary,driver='GeoJSON')
    (folder/'regions.json').write_text(json.dumps({'area':{'region_id':'area','name':'Area','aoi':{'source_id':'area','path':str(boundary),'kind':'aoi'}}}))
    dem=tmp_path/'dem.tif'
    with rasterio.open(dem,'w',driver='GTiff',width=14,height=14,count=1,dtype='float32',crs=4326,transform=from_origin(74.998,13.012,.001,.001)) as ds:ds.write(np.zeros((14,14),dtype='float32'),1)
    app=Flask(__name__);register_api(app,tmp_path);register_unified_api(app,tmp_path)
    c=app.test_client();headers={'X-HELPS-Role':'engineer'}
    with dem.open('rb') as stream:uploaded=c.post('/api/knowledge/sources',headers=headers,data={'kind':'dem','date':'2026-06-01','units':'m','file':(stream,'regional-dem.tif')}).get_json()
    seen=[]
    def acquire(root,region_id,aoi,day,**kwargs):
        seen.append(aoi.to_crs(4326).total_bounds.tolist());return {'overture':tmp_path/'mapped-buildings.geojson'},{'acquired_at':'2026-10-18T00:00:00Z'}
    def build(spec,log):
        assert spec.region_id=='area' and spec.dem.source_id==uploaded['asset_id']
        assert spec.sources['buildings'].date is None
        assert 'snapshot' in spec.sources['buildings'].metadata['date_status']
        return {'validation':{'valid':True}}
    monkeypatch.setattr('scripts.pipeline.region_inputs.resolve_region_inputs',acquire)
    monkeypatch.setattr('scripts.knowledge.build.build_knowledge',build)
    response=c.post('/api/knowledge/build',headers=headers,json={'region_id':'area','date':'2026-06-02','source_mode':'acquire','source_choices':{'dem':uploaded['asset_id']}})
    assert response.status_code==202,response.get_json()
    for _ in range(100):
        job=c.get('/api/knowledge/jobs/'+response.get_json()['job_id']).get_json()
        if job['status'] in ('completed','failed'):break
        sleep(.02)
    assert job['status']=='completed',job.get('error')
    assert seen==[[75,13,75.01,13.01]]
    assert not (folder/'registry.json').exists()


def test_canonical_history_root_wins_and_draft_uses_original_fallback(tmp_path):
    from scripts.ui.api import register_api
    def history(root,day):
        folder=root/'data/processed/Bhadra/sentinel2';folder.mkdir(parents=True)
        (folder/'history_dates.json').write_text(json.dumps({'history_dates':[],'current_reference_date':day}))
    history(tmp_path,'2026-01-01');draft=tmp_path/'draft';draft.mkdir()
    app=Flask(__name__);register_api(app,draft)
    assert app.test_client().get('/api/knowledge/workflow').get_json()['history'][0]['date']=='2026-01-01'
    history(draft,'2026-02-01')
    assert app.test_client().get('/api/knowledge/workflow').get_json()['history'][0]['date']=='2026-02-01'
    assert callable(app.extensions['helps_repository'])


def test_published_registered_regions_supply_real_operational_geometry(tmp_path):
    from scripts.ui.unified_api import registered_region_features
    import geopandas as gpd
    from shapely.geometry import box
    folder=tmp_path/'data/knowledge';folder.mkdir(parents=True)
    path=folder/'boundary.geojson';gpd.GeoDataFrame(geometry=[box(75,13,75.01,13.01)],crs=4326).to_file(path,driver='GeoJSON')
    (folder/'regions.json').write_text(json.dumps({'area':{'region_id':'area','name':'Area','aoi':{'path':str(path)}}}))
    (folder/'registry.json').write_text(json.dumps({'selected':{'area':'area-day'},'datasets':{'area-day':{'region_id':'area','date':'2026-06-01'}}}))
    features=registered_region_features(tmp_path)
    assert len(features)==1
    assert features[0]['properties']['region_id']=='area'
    assert features[0]['properties']['status']=='ready'
    assert features[0]['geometry']['type']=='Polygon'


def test_inventory_qa_measures_partial_and_nodata_support_and_caches(tmp_path,monkeypatch):
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box
    from scripts.ui.inventory_qa import scl_inventory_quality,_cache
    boundary=tmp_path/'aoi.geojson'
    gpd.GeoDataFrame(geometry=[box(0,0,4,2)],crs=32643).to_file(boundary,driver='GeoJSON')
    path=tmp_path/'scl.tif'
    with rasterio.open(path,'w',driver='GTiff',width=2,height=2,count=1,dtype='uint8',crs=32643,transform=from_origin(0,2,1,1),nodata=0) as ds:ds.write(np.array([[8,0],[4,5]],dtype='uint8'),1)
    source={'source_id':'aoi','path':str(boundary),'kind':'aoi'}
    actual=scl_inventory_quality(tmp_path,source,path)
    assert actual['qa_state']=='measured'
    assert actual['cloud_shadow_fraction']==.125
    assert actual['coverage_fraction']==.375
    assert actual['usable_support']==.25
    def fail(*args):raise AssertionError('Measurement should use cache')
    monkeypatch.setattr('scripts.pipeline.monthly.measure_scl_quality',fail)
    assert scl_inventory_quality(tmp_path,source,path)==actual
    _cache.clear()
    assert scl_inventory_quality(tmp_path,source,path)==actual
    assert scl_inventory_quality(tmp_path,source,tmp_path/'absent.tif')['qa_state']=='unknown'


@pytest.mark.parametrize('catalog_dem',[False,True])
def test_region_outline_can_build_with_automatic_dem(tmp_path,monkeypatch,catalog_dem):
    from scripts.ui.api import register_api
    from scripts.ui.unified_api import register_unified_api
    from scripts.knowledge.contracts import SourceAsset
    import geopandas as gpd
    from shapely.geometry import box
    from time import sleep
    folder=tmp_path/'data/knowledge';folder.mkdir(parents=True)
    boundary=folder/'region.geojson';gpd.GeoDataFrame(geometry=[box(75,13,75.01,13.01)],crs=4326).to_file(boundary)
    (folder/'regions.json').write_text(json.dumps({'area':{'region_id':'area','name':'Area','aoi':{'source_id':'area','path':str(boundary),'kind':'aoi'}}}))
    region_id='area'
    choices={}
    if catalog_dem:
        region_id='bhadra';choices={'dem':'automatic'}
        examples=tmp_path/'docs/examples';examples.mkdir(parents=True)
        (examples/'bhadra-retained-build.json').write_text(json.dumps({'aoi':{'source_id':'aoi','path':str(boundary),'kind':'aoi'},'dem':{'source_id':'old-dem','path':'unavailable-old-dem.tif','kind':'dem','units':'m'}}))
    seen=[]
    def elevation(self,selected=None,log=print):
        seen.append('elevation');return SourceAsset('automatic',tmp_path/'auto.tif',kind='dem',units='m')
    monkeypatch.setattr('scripts.pipeline.region_inputs.RegionInputs.resolve_dem',elevation)
    monkeypatch.setattr('scripts.pipeline.region_inputs.resolve_region_inputs',lambda *args,**kwargs:({},{}))
    monkeypatch.setattr('scripts.knowledge.build.build_knowledge',lambda spec,log:{'validation':{'valid':spec.dem.source_id=='automatic'}})
    app=Flask(__name__);register_api(app,tmp_path);register_unified_api(app,tmp_path);c=app.test_client()
    response=c.post('/api/knowledge/build',headers={'X-HELPS-Role':'engineer'},json={'region_id':region_id,'date':'2026-06-02','source_mode':'acquire','source_choices':choices})
    assert response.status_code==202,response.json
    for _ in range(100):
        job=c.get('/api/knowledge/jobs/'+response.json['job_id']).json
        if job['status'] in ('completed','failed'):break
        sleep(.01)
    assert job['status']=='completed',job.get('error')
    assert seen==['elevation'] and job['result']['validation']['valid']
