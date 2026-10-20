"""Regressions found while tracing retained geometry versus fresh generation."""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from scripts.knowledge.contracts import SourceAsset, KnowledgeBuildSpec
from scripts.knowledge.sources import file_sha256


def new_spec(tmp_path):
    grid=from_origin(500000,1500200,10,10)
    for name,data in [('spectral',np.broadcast_to(np.array([.1,.1,.2,.28,.3,.2],dtype='float32')[:,None,None],(6,20,20))),('scl',np.full((1,20,20),5,dtype='uint8'))]:
        path=tmp_path/(name+'.tif')
        with rasterio.open(path,'w',driver='GTiff',width=20,height=20,count=len(data),dtype=data.dtype,crs=32643,transform=grid,nodata=-9999 if name=='spectral' else 0) as ds:ds.write(data)
    aoi=tmp_path/'aoi.geojson'
    gpd.GeoDataFrame(geometry=[box(500000,1500000,500200,1500200)],crs=32643).to_file(aoi)
    empty=tmp_path/'empty.geojson'
    gpd.GeoDataFrame(geometry=[],crs=32643).to_file(empty)
    dem=tmp_path/'dem.tif'
    with rasterio.open(dem,'w',driver='GTiff',width=12,height=12,count=1,dtype='float32',crs=32643,transform=from_origin(499920,1500280,30,30),nodata=-9999) as ds:ds.write(np.ones((12,12),dtype='float32')*600,1)
    sources={k:SourceAsset(k,empty) for k in ('buildings','water','industrial','facilities')}
    sources.update(spectral=SourceAsset('spectral',tmp_path/'spectral.tif',kind='spectral',date='2026-06-02',metadata={'band_map':{'blue':1,'green':2,'red':3,'nir':4}}),scl=SourceAsset('scl',tmp_path/'scl.tif',kind='scl',date='2026-06-02'))
    return KnowledgeBuildSpec('fresh','test','2026-06-02',SourceAsset('aoi',aoi),None,SourceAsset('dem',dem,kind='dem',units='m'),tmp_path/'output',sources=sources,source_mode='new',parameters={'slope_thresholds_deg':[0,2]})


def test_fresh_generation_respects_review_geometry_even_when_ids_change(tmp_path):
    from scripts.knowledge.build import _generate_new_seed
    spec=new_spec(tmp_path)
    rejected=box(500080,1500080,500120,1500120)
    accepted=box(500030,1500030,500070,1500070)
    review=tmp_path/'review.geojson'
    gpd.GeoDataFrame({'source_zone_id':['old-zone','accepted-zone'],'status':['quarantined','accepted']},geometry=[rejected,accepted],crs=32643).to_file(review)
    spec.reviewed_exclusions=SourceAsset('review',review)
    terrain,_=_generate_new_seed(spec,gpd.read_file(spec.aoi.path),spec.output_dir/'generated-candidates',lambda _:None)
    assert len(terrain)>0
    assert terrain.geometry.intersection(rejected).area.sum()<1e-4
    assert terrain.geometry.intersection(accepted).area.sum()>100
    summary=json.loads((spec.output_dir/'generated-candidates/summary.json').read_text())
    assert summary['audits']['passed']
    assert summary['exclusion_feature_counts']['reviewed']==1


def test_spectral_nodata_is_unknown_even_if_indices_look_open(tmp_path):
    from scripts.processing.open_land_detector import generate_possible_open_mask
    spec=new_spec(tmp_path)
    with rasterio.open(spec.sources['spectral'].path,'r+') as ds:
        red=ds.read(3);red[10,10]=-9999;ds.write(red,3)
    output=tmp_path/'classified.tif'
    generate_possible_open_mask(spec.sources['spectral'].path,spec.sources['scl'].path,output,cloud_buffer_pixels=0,screening_profile='conservative')
    with rasterio.open(output) as ds:
        assert ds.read(1)[10,10]==255
        assert ds.read(1)[9,9]==1


def test_algorithm_identity_includes_polygon_processing_code(monkeypatch):
    from scripts.knowledge.build import algorithm_fingerprint
    original=Path.read_bytes
    before=algorithm_fingerprint()
    def changed(path):
        value=original(path)
        return value+b'\n# changed polygon algorithm' if path.as_posix().endswith('/pipeline/processing.py') else value
    monkeypatch.setattr(Path,'read_bytes',changed)
    assert algorithm_fingerprint()!=before


def test_retained_observation_uses_same_cloud_margin_as_fresh_scan(tmp_path,monkeypatch):
    from scripts.knowledge.build import build_knowledge
    from scripts.processing import open_land_detector
    from test_knowledge_sources import fixture_spec
    spec=fixture_spec(tmp_path)
    fresh_dir=tmp_path/'imagery';fresh_dir.mkdir();fresh=new_spec(fresh_dir)
    spec.date=fresh.date;spec.sources={k:v for k,v in fresh.sources.items() if k in ('spectral','scl')}
    spec.parameters={'slope_thresholds_deg':[0]}
    real=open_land_detector.generate_possible_open_mask;seen=[]
    def capture(*args,**kwargs):
        seen.append(kwargs.get('cloud_buffer_pixels',1));return real(*args,**kwargs)
    monkeypatch.setattr(open_land_detector,'generate_possible_open_mask',capture)
    build_knowledge(spec,log=lambda _:None)
    assert seen==[3]


def test_knowledge_acquisition_prepares_landcover_for_its_actual_imagery(tmp_path,monkeypatch):
    from scripts.pipeline import acquisition,landcover
    spec=new_spec(tmp_path);cover=tmp_path/'aligned-cover.tif';cover.write_bytes(b'aligned-cover')
    seen=[]
    monkeypatch.setattr(acquisition,'acquire',lambda *args,**kwargs:({'spectral':spec.sources['spectral'].path,'scl':spec.sources['scl'].path},{'date':spec.date,'files':{}}))
    def prepare(reference,output,log):
        seen.append(reference);return cover,{'year':2021,'sha256':'test','reference_sha256':'reference'}
    monkeypatch.setattr(landcover,'acquire_worldcover',prepare)
    paths,manifest=acquisition.acquire_knowledge_inputs(gpd.read_file(spec.aoi.path),spec.date,log=lambda _:None)
    assert seen==[spec.sources['spectral'].path]
    assert paths['landcover']==cover and manifest['landcover']['year']==2021


def test_fresh_build_runs_from_pixels_through_slope_and_temporal_package(tmp_path):
    from scripts.knowledge.build import build_knowledge
    from scripts.knowledge.repository import KnowledgeRepository
    from scripts.knowledge.temporal import validate_history_raster
    spec=new_spec(tmp_path)
    review=tmp_path/'known-negative.geojson';negative=box(500080,1500080,500120,1500120)
    gpd.GeoDataFrame({'source_zone_id':['old-zone'],'status':['quarantined']},geometry=[negative],crs=32643).to_file(review)
    spec.reviewed_exclusions=SourceAsset('review',review)
    histories=[]
    for day in ('2026-04-01','2026-05-01'):
        path=tmp_path/(day+'.tif')
        with rasterio.open(path,'w',driver='GTiff',width=20,height=20,count=1,dtype='uint8',crs=32643,transform=from_origin(500000,1500200,10,10),nodata=255) as ds:ds.write(np.ones((20,20),dtype='uint8'),1)
        histories.append({'source_id':'history-'+day,'path':str(path),'date':day,'status':'available','provenance_state':'synthetic',**validate_history_raster(path)})
    spec.parameters['_history_sources']=histories
    result=build_knowledge(spec,log=lambda _:None)
    assert result.validation['valid'] and result.counts['terrain']>0 and result.counts['zones']>0
    repo=KnowledgeRepository(result.package_path)
    parents=repo.list_terrain()
    assert all(p['temporal_open_confidence']==pytest.approx(1) and p['history_date_count']==2 for p in parents)
    terrain=gpd.read_file(result.package_path,layer='terrain')
    assert terrain.geometry.intersection(negative).area.sum()<1e-4
    assert repo.get_metadata()['observation_source']['date']==spec.date
    assert repo.get_metadata()['observation_source']['spectral_sha256']==file_sha256(spec.sources['spectral'].path)
    manifest=json.loads(result.manifest_path.read_text())
    assert manifest['spec']['source_mode']=='new'
    assert set(('terrain','dem','characteristics','zones','environment','temporal','package'))<=set(manifest['stages'])
    assert not (tmp_path/'registry.json').exists()
