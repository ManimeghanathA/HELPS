from app import app

def test_empty_registry_is_honest_and_unknown_dataset_missing():
    c=app.test_client();d=c.get('/api/datasets');assert d.status_code==200
    assert isinstance(d.json['datasets'],list)
    assert c.get('/api/datasets/nonexistent/terrain').status_code==404

def test_job_rejects_paths_missing_fields_and_foreign_origin():
    c=app.test_client();h={'X-HELPS-Role':'engineer'}
    assert c.post('/api/knowledge/jobs',headers=h,json={'dataset_id':'../bad'}).status_code==400
    assert c.post('/api/knowledge/jobs',headers=h,json={'dataset_id':'valid'}).status_code==400
    assert c.post('/api/knowledge/sources/register',headers=h,json={'catalog_id':'../../app.py'}).status_code==400
    assert c.post('/api/knowledge/jobs',headers={**h,'Origin':'https://evil.example'},json={}).status_code==403

def test_profile_ids_come_from_real_engine_profiles():
    from helicopter_profiles import HELICOPTER_FLEET,MISSION_CONTEXTS,get_ui_profiles
    d=app.test_client().get('/api/profiles').json
    assert d['aircraft']=={p['id']:p for p in get_ui_profiles()}
    assert len(d['aircraft'])==3 and set(d['aircraft']).issubset(HELICOPTER_FLEET)
    assert set(d['missions'])==set(MISSION_CONTEXTS)

def test_invalid_input_shapes_and_wrong_raster_kind_are_useful_errors():
    from io import BytesIO
    c=app.test_client();h={'X-HELPS-Role':'engineer'}
    assert c.post('/api/knowledge/jobs',headers=h,json=['wrong']).status_code==400
    assert c.post('/api/knowledge/sources/register',headers=h,json=['wrong']).status_code==400
    response=c.post('/api/knowledge/sources',headers=h,data={'kind':'dem','date':'2026-06-01','units':'metre','file':(BytesIO(b'{}'),'dem.geojson')})
    assert response.status_code==400 and 'GeoTIFF' in response.json['error']
    assert c.post('/api/reload-zones').status_code==403

def test_corrupt_raster_upload_returns_json400_and_keeps_registry(tmp_path, monkeypatch):
    from io import BytesIO
    from flask import Flask
    from scripts.ui.api import register_api
    isolated=Flask(__name__);register_api(isolated,tmp_path)
    registry=tmp_path/'data/knowledge/registry.json';registry.parent.mkdir(parents=True)
    registry.write_text('{"datasets":{},"selected":{"bhadra":"previous"}}')
    before=registry.read_bytes()
    response=isolated.test_client().post('/api/knowledge/sources',headers={'X-HELPS-Role':'engineer'},data={'kind':'dem','date':'2026-06-01','units':'metre','file':(BytesIO(b'not a TIFF'),'bad.tif')})
    assert response.status_code==400 and response.is_json
    assert 'Cannot read' in response.json['error']
    assert registry.read_bytes()==before


def test_activation_checks_immutable_package_hash_not_only_valid_geometry(tmp_path):
    import json,sqlite3
    from flask import Flask
    from scripts.ui.api import register_api
    from scripts.knowledge.build import build_knowledge
    from scripts.knowledge.repository import register_dataset
    from test_knowledge_sources import fixture_spec
    spec=fixture_spec(tmp_path)
    spec.output_dir=tmp_path/'data/knowledge/test'
    result=build_knowledge(spec,log=lambda m:None)
    registry=tmp_path/'data/knowledge/registry.json'
    register_dataset('test',result.package_path,registry)
    data=json.loads(registry.read_text());data['selected']={'test':'previous'};registry.write_text(json.dumps(data))
    before=registry.read_bytes()
    with sqlite3.connect(result.package_path) as db:
        value=json.loads(db.execute("SELECT value FROM package_metadata WHERE key='metadata'").fetchone()[0]);value['unexpected_edit']=True
        db.execute("UPDATE package_metadata SET value=? WHERE key='metadata'",(json.dumps(value),))
    isolated=Flask(__name__);register_api(isolated,tmp_path)
    response=isolated.test_client().post('/api/datasets/test/activate',headers={'X-HELPS-Role':'engineer'})
    assert response.status_code==400 and 'hash mismatch' in response.json['error']
    assert registry.read_bytes()==before


def test_reviewed_catalog_registration_returns_real_geospatial_validation(tmp_path):
    import json
    import geopandas as gpd
    from shapely.geometry import box
    from flask import Flask
    from scripts.ui.api import register_api
    source=tmp_path/'aoi.geojson';gpd.GeoDataFrame(geometry=[box(75,13,75.1,13.1)],crs=4326).to_file(source)
    folder=tmp_path/'docs/examples';folder.mkdir(parents=True)
    (folder/'bhadra-retained-build.json').write_text(json.dumps({'aoi':{'source_id':'aoi','path':'aoi.geojson','kind':'aoi','coverage_state':'supplied'}}))
    isolated=Flask(__name__);register_api(isolated,tmp_path)
    response=isolated.test_client().post('/api/knowledge/sources/register',headers={'X-HELPS-Role':'engineer'},json={'catalog_id':'aoi'})
    assert response.status_code==201
    assert response.json['validation']['crs']=='EPSG:4326'
    assert response.json['validation']['count']==1
