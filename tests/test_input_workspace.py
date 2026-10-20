import io
import json
import geopandas as gpd
from flask import Flask
from shapely.geometry import box


def client(root):
    from scripts.ui.api import register_api
    from scripts.ui.unified_api import register_unified_api
    app=Flask(__name__);app.config['TESTING']=True
    register_api(app,root);register_unified_api(app,root)
    return app.test_client()


def add_region(c):
    frame=gpd.GeoDataFrame(geometry=[box(75.1,13.1,75.101,13.101)],crs=4326)
    return c.post('/api/knowledge/regions',headers={'X-HELPS-Role':'engineer'},data={'name':'Test Area','file':(io.BytesIO(frame.to_json().encode()),'aoi.geojson')})


def test_readiness_guard_read_only_region_storage_and_date(tmp_path):
    c=client(tmp_path);assert add_region(c).status_code==201
    payload={'region_id':'test-area','date':'2026-06-01'}
    assert c.post('/api/knowledge/input-readiness',json=payload).status_code==403
    result=c.post('/api/knowledge/input-readiness',headers={'X-HELPS-Role':'engineer'},json=payload)
    assert result.status_code==200,result.json
    assert len(result.json['inputs'])==5
    assert result.json['inputs'][0]['action']=='download'
    assert list((tmp_path/'data/raw/test-area/boundary').rglob('*.geojson'))
    assert list((tmp_path/'data/processed/test-area/boundary').rglob('*.geojson'))
    assert not (tmp_path/'data/raw/test-area/sentinel').exists()
    assert c.post('/api/knowledge/input-readiness',headers={'X-HELPS-Role':'engineer'},json={**payload,'date':'../bad'}).status_code==400


def test_download_rejects_arbitrary_paths_and_unregistered_evidence(tmp_path):
    c=client(tmp_path);add_region(c)
    assert c.get('/api/knowledge/input-file?path=.env',headers={'X-HELPS-Role':'engineer'}).status_code==400
    query='region_id=test-area&kind=osm&snapshot_id=missing&phase=processed&key=osm'
    assert c.get('/api/knowledge/input-file?'+query).status_code==403
    assert c.get('/api/knowledge/input-file?'+query,headers={'X-HELPS-Role':'engineer'}).status_code==400


def test_regional_upload_preserves_original_raw_and_exposes_processed_asset(tmp_path):
    c=client(tmp_path);add_region(c)
    content=gpd.GeoDataFrame(geometry=[box(75.1,13.1,75.1001,13.1001)],crs=4326).to_json().encode()
    result=c.post('/api/knowledge/sources',headers={'X-HELPS-Role':'engineer'},data={
        'region_id':'test-area','kind':'buildings','date':'2026-06-01','file':(io.BytesIO(content),'buildings.geojson')})
    assert result.status_code==201,result.json
    raw=list((tmp_path/'data/raw/test-area/overture').rglob('*.geojson'))
    processed=list((tmp_path/'data/processed/test-area/overture').rglob('*.geojson'))
    assert len(raw)==len(processed)==1 and raw[0].read_bytes()==content
    record=json.loads((tmp_path/'data/knowledge/sources'/(result.json['asset_id']+'.asset.json')).read_text())
    assert record['path']==str(processed[0])
    assert record['metadata']['region_id']=='test-area'
    assert record['metadata']['raw_sha256']==record['sha256']


def test_refresh_cannot_silently_ignore_explicit_obstacle_override(tmp_path):
    c=client(tmp_path);add_region(c)
    result=c.post('/api/knowledge/build',headers={'X-HELPS-Role':'engineer'},json={
        'region_id':'test-area','date':'2026-06-01','source_mode':'acquire',
        'refresh_obstacles':True,'source_choices':{'buildings':'a'*32}})
    assert result.status_code==400 and 'refresh' in result.json['error'].lower()
