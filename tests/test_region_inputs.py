import json
from contextlib import contextmanager

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import box

from scripts.pipeline.region_inputs import RegionInputs


def aoi():return gpd.GeoDataFrame(geometry=[box(75.1,13.1,75.101,13.101)],crs=4326)


def raster(path,count=1,value=5):
    with rasterio.open(path,'w',driver='GTiff',crs=4326,width=20,height=20,count=count,dtype='float32',transform=from_bounds(75.09,13.09,75.11,13.11,20,20)) as ds:
        ds.write(np.full((count,20,20),value,dtype='float32'))


def providers(monkeypatch,calls):
    from scripts.pipeline import acquisition as acq
    def sentinel(aoi,date,folder,log):
        calls.append(('sentinel',date));raster(folder/'spectral.tif',6,.2);raster(folder/'scl.tif')
        (folder/'archive').mkdir();(folder/'archive/provider-response.txt').write_text('provider evidence')
    def osm(aoi,path,log,include_context=False):
        calls.append(('osm',None))
        for layer in acq.GROUPS:gpd.GeoDataFrame(geometry=[],crs=4326).to_file(path,layer=layer,driver='GPKG')
    def overture(aoi,path,log):
        calls.append(('overture',None));gpd.GeoDataFrame(geometry=[box(75.1,13.1,75.1001,13.1001)],crs=4326).to_file(path,driver='GeoJSON')
    monkeypatch.setattr(acq,'sentinel',sentinel);monkeypatch.setattr(acq,'osm',osm);monkeypatch.setattr(acq,'overture',overture)


def test_context_is_shared_across_dates_but_sentinel_is_not(tmp_path,monkeypatch):
    calls=[];providers(monkeypatch,calls);service=RegionInputs(tmp_path,'area',aoi())
    first=service.resolve_context('2026-06-01',log=lambda _:None)
    again=service.resolve_context('2026-06-02',log=lambda _:None)
    assert calls==[('sentinel','2026-06-01'),('osm',None),('overture',None),('sentinel','2026-06-02')]
    assert first['osm']['snapshot_id']==again['osm']['snapshot_id']
    assert first['overture']['metadata']['date_status'].startswith('acquisition-time')
    assert first['sentinel']['paths']['spectral']!=again['sentinel']['paths']['spectral']
    assert list((tmp_path/'data/raw/area/sentinel').rglob('provider-response.txt'))
    first['osm']['paths']['osm'].write_bytes(b'broken')
    repaired=service.resolve_context('2026-06-02',log=lambda _:None)
    assert calls.count(('osm',None))==1
    assert repaired['osm']['snapshot_id']!=first['osm']['snapshot_id']


def test_refresh_only_fetches_obstacles_and_bad_layers_do_not_publish(tmp_path,monkeypatch):
    calls=[];providers(monkeypatch,calls);service=RegionInputs(tmp_path,'area',aoi())
    service.resolve_context('2026-06-01',log=lambda _:None)
    service.resolve_context('2026-06-01',refresh=True,log=lambda _:None)
    assert calls.count(('sentinel','2026-06-01'))==1
    assert calls.count(('osm',None))==2 and calls.count(('overture',None))==2
    from scripts.pipeline import acquisition as acq
    def incomplete(aoi,path,log,include_context=False):
        gpd.GeoDataFrame(geometry=[],crs=4326).to_file(path,layer='buildings',driver='GPKG')
    monkeypatch.setattr(acq,'osm',incomplete)
    with pytest.raises(ValueError,match='layers'):service.resolve_context('2026-06-02',refresh=True,log=lambda _:None)


def test_wrong_date_grid_and_invalid_geometry_are_not_accepted(tmp_path,monkeypatch):
    calls=[];providers(monkeypatch,calls);service=RegionInputs(tmp_path,'area',aoi())
    paths={};folder=tmp_path/'data/processed/evidence';folder.mkdir(parents=True)
    for kind in ('spectral','scl'):
        paths[kind]=folder/(kind+'.tif');raster(paths[kind],6 if kind=='spectral' else 1)
    with rasterio.open(paths['spectral'],'r+') as ds:ds.update_tags(observation_date='2026-06-02')
    with pytest.raises(ValueError,match='date'):service.validate('sentinel','2026-06-01')(paths,{})


def test_readiness_does_not_download_and_registered_files_stay_in_data(tmp_path,monkeypatch):
    calls=[];providers(monkeypatch,calls);service=RegionInputs(tmp_path,'area',aoi())
    rows=service.readiness('2026-06-01')
    assert calls==[] and all(r['action']=='download' for r in rows)
    assert all('/data/raw/area/' in r['raw_directory'].replace('\\','/') for r in rows)


def test_landcover_realigns_raw_evidence_when_reference_grid_changes(tmp_path,monkeypatch):
    service=RegionInputs(tmp_path,'area',aoi());calls=[]
    folder=tmp_path/'references';folder.mkdir()
    first=folder/'one.tif';second=folder/'two.tif';raster(first,6)
    with rasterio.open(second,'w',driver='GTiff',crs=4326,width=40,height=40,count=6,dtype='float32',transform=from_bounds(75.09,13.09,75.11,13.11,40,40)) as dst:dst.write(np.ones((6,40,40),dtype='float32'))
    def acquire(reference,output,log):
        calls.append(reference)
        with rasterio.open(reference) as src:
            profile=src.profile.copy();profile.update(count=1,dtype='uint8')
            for name in ('worldcover_2021_aligned.tif','worldcover_2021_native_crop.tif'):
                with rasterio.open(output/name,'w',**profile) as dst:dst.write(np.full(src.shape,40,dtype='uint8'),1)
        return output/'worldcover_2021_aligned.tif',{'year':2021}
    monkeypatch.setattr('scripts.pipeline.landcover.acquire_worldcover',acquire)
    one=service.resolve_landcover(first,log=lambda _:None)
    two=service.resolve_landcover(second,log=lambda _:None)
    assert len(calls)==1 and one['snapshot_id']!=two['snapshot_id']
    with rasterio.open(two['paths']['landcover']) as cover,rasterio.open(second) as ref:
        assert cover.shape==ref.shape and cover.transform==ref.transform


def test_unreadable_vectors_are_validation_errors_not_uncaught_reader_errors(tmp_path):
    service=RegionInputs(tmp_path,'area',aoi());path=tmp_path/'bad.geojson';path.write_text('not JSON')
    with pytest.raises(ValueError,match='read'):service.validate('overture')({'overture':path},{})


def test_explicit_buildings_skip_unused_overture_acquisition(tmp_path,monkeypatch):
    calls=[];providers(monkeypatch,calls);service=RegionInputs(tmp_path,'area',aoi())
    results=service.resolve_context('2026-06-01',required=('sentinel','osm'),log=lambda _:None)
    assert set(results)=={'sentinel','osm'} and not any(c[0]=='overture' for c in calls)


def test_date_only_downloads_sentinel_and_never_static_inputs(tmp_path,monkeypatch):
    calls=[];providers(monkeypatch,calls);service=RegionInputs(tmp_path,'area',aoi())
    service.resolve_context('2026-06-01',log=lambda _:None)
    calls.clear()
    service.resolve_context('2026-06-02',local_only=True,log=lambda _:None)
    assert calls==[('sentinel','2026-06-02')]
    with pytest.raises(ValueError,match='local OSM'):
        RegionInputs(tmp_path,'missing',aoi()).resolve_context('2026-06-02',local_only=True,log=lambda _:None)
    assert calls==[('sentinel','2026-06-02')]
