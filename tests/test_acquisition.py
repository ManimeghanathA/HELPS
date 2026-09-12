import json

import geopandas as gpd
import pytest
from shapely.geometry import box

from scripts.pipeline import acquisition as acq


def test_cache_reuses_each_completed_source_and_repairs_corruption(tmp_path, monkeypatch):
    monkeypatch.setattr(acq,'ROOT',tmp_path)
    monkeypatch.setattr(acq,'legacy_inputs',lambda *_: None)
    calls = []
    def sentinel(aoi,date,folder,log):
        calls.append('sentinel')
        (folder/'spectral.tif').write_bytes(b'spectral')
        (folder/'scl.tif').write_bytes(b'scl')
    def osm(aoi,path,log):
        calls.append('osm')
        path.write_bytes(b'osm')
    def overture(aoi,path,log):
        calls.append('overture')
        path.write_bytes(b'overture')
    monkeypatch.setattr(acq,'sentinel',sentinel)
    monkeypatch.setattr(acq,'osm',osm)
    monkeypatch.setattr(acq,'overture',overture)
    aoi = gpd.GeoDataFrame(geometry=[box(75,13,75.01,13.01)],crs=4326)
    paths,_ = acq.acquire(aoi,'2026-06-01',lambda _:None)
    acq.acquire(aoi,'2026-06-01',lambda _:None)
    assert calls == ['sentinel','osm','overture']
    paths['osm'].write_bytes(b'broken')
    acq.acquire(aoi,'2026-06-01',lambda _:None)
    assert calls == ['sentinel','osm','overture','osm']


def test_completed_downloads_survive_later_provider_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(acq,'ROOT',tmp_path)
    monkeypatch.setattr(acq,'legacy_inputs',lambda *_:None)
    def sentinel(aoi,date,folder,log):
        (folder/'spectral.tif').write_bytes(b'spectral')
        (folder/'scl.tif').write_bytes(b'scl')
    def fail(*args):
        raise RuntimeError('Provider unavailable')
    monkeypatch.setattr(acq,'sentinel',sentinel)
    monkeypatch.setattr(acq,'osm',fail)
    aoi = gpd.GeoDataFrame(geometry=[box(75,13,75.01,13.01)],crs=4326)
    with pytest.raises(RuntimeError):
        acq.acquire(aoi,'2026-06-01',lambda _:None)
    manifests = list(tmp_path.rglob('manifest.json'))
    assert len(manifests) == 1
    assert set(json.loads(manifests[0].read_text())['files']) == {'spectral','scl'}
