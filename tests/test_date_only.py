import json
from time import sleep
import geopandas as gpd
from flask import Flask
from shapely.geometry import box
from scripts.ui.api import register_api
from scripts.knowledge.contracts import SourceAsset


def test_date_only_defaults_to_bhadra_and_preserves_complete_build(tmp_path,monkeypatch):
    boundary=tmp_path/'data/boundary.geojson';boundary.parent.mkdir()
    gpd.GeoDataFrame(geometry=[box(75,13,75.01,13.01)],crs=4326).to_file(boundary)
    examples=tmp_path/'docs/examples';examples.mkdir(parents=True)
    (examples/'bhadra-retained-build.json').write_text(json.dumps({'aoi':{'source_id':'aoi','path':str(boundary),'kind':'aoi'}}))
    seen=[]
    def dem(self,selected=None,log=print,local_only=False):
        assert local_only;seen.append('local dem');return SourceAsset('local',tmp_path/'local.tif',kind='dem',units='m')
    def acquire(*args,**kwargs):
        assert args[1]=='bhadra' and kwargs['static_only'] is True
        assert kwargs['refresh'] is False;seen.append('sentinel only');return {},{}
    def build(spec,log):
        assert spec.parameters['static_inputs_only'] and spec.parameters['harmonize_history']
        assert spec.parameters['screening_profile']=='neha-236c34c'
        assert spec.source_mode=='new' and spec.parameters['min_clear_diameter_m']==30
        seen.append('full knowledge build');return {'validation':{'valid':True}}
    monkeypatch.setattr('scripts.pipeline.region_inputs.RegionInputs.resolve_dem',dem)
    monkeypatch.setattr('scripts.pipeline.region_inputs.resolve_region_inputs',acquire)
    monkeypatch.setattr('scripts.knowledge.build.build_knowledge',build)
    app=Flask(__name__);register_api(app,tmp_path);client=app.test_client();headers={'X-HELPS-Role':'engineer'}
    response=client.post('/api/knowledge/build',headers=headers,json={'source_mode':'date_only','date':'2026-10-12'})
    assert response.status_code==202,response.json
    for _ in range(100):
        job=client.get('/api/knowledge/jobs/'+response.json['job_id']).json
        if job['status'] in ('completed','failed'):break
        sleep(.01)
    assert job['status']=='completed',job.get('error')
    assert seen==['local dem','sentinel only','full knowledge build']
    assert not (tmp_path/'data/knowledge/registry.json').exists()
    for extra in ({'region_id':'another'},{'refresh_obstacles':True},{'source_choices':{'dem':'automatic'}}):
        assert client.post('/api/knowledge/build',headers=headers,json={'source_mode':'date_only','date':'2026-10-12',**extra}).status_code==400
