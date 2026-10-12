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
    monkeypatch.setattr(acq,'osm_complete',lambda path: path.exists() and path.read_bytes() == b'osm')
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


def test_osm_complete_detects_missing_layers(tmp_path):
    p = tmp_path / 'test_osm.gpkg'
    assert not acq.osm_complete(p)
    layers = list(acq.GROUPS.keys())
    for layer in layers[:-1]:
        gpd.GeoDataFrame(geometry=[], crs=4326).to_file(p, layer=layer, driver='GPKG')
    assert not acq.osm_complete(p)
    gpd.GeoDataFrame(geometry=[], crs=4326).to_file(p, layer=layers[-1], driver='GPKG')
    assert acq.osm_complete(p)


def test_acquire_reacquires_osm_when_cached_file_lacks_required_layers(tmp_path, monkeypatch):
    monkeypatch.setattr(acq, 'ROOT', tmp_path)
    monkeypatch.setattr(acq, 'legacy_inputs', lambda *_: None)
    calls = []
    def sentinel(aoi, date, folder, log):
        (folder/'spectral.tif').write_bytes(b'spectral')
        (folder/'scl.tif').write_bytes(b'scl')
    def osm(aoi, path, log):
        calls.append('osm')
        path.write_bytes(b'osm_data')
    def overture(aoi, path, log):
        path.write_bytes(b'overture')
    monkeypatch.setattr(acq, 'sentinel', sentinel)
    monkeypatch.setattr(acq, 'osm', osm)
    monkeypatch.setattr(acq, 'overture', overture)
    # Simulate osm_complete returning False for incomplete cache
    monkeypatch.setattr(acq, 'osm_complete', lambda path: False)
    aoi = gpd.GeoDataFrame(geometry=[box(75, 13, 75.01, 13.01)], crs=4326)
    acq.acquire(aoi, '2026-06-01', lambda _: None)
    assert calls == ['osm']
    # Second acquire call: hash matches in manifest, but osm_complete is False -> must re-acquire
    acq.acquire(aoi, '2026-06-01', lambda _: None)
    assert calls == ['osm', 'osm']


def test_acquire_skips_legacy_osm_when_incomplete(tmp_path, monkeypatch):
    legacy_osm = tmp_path / 'legacy_osm.gpkg'
    legacy_osm.write_bytes(b'legacy_incomplete')
    monkeypatch.setattr(acq, 'ROOT', tmp_path)
    monkeypatch.setattr(acq, 'legacy_inputs', lambda *_: {'osm': legacy_osm})
    calls = []
    def sentinel(aoi, date, folder, log):
        (folder/'spectral.tif').write_bytes(b'spectral')
        (folder/'scl.tif').write_bytes(b'scl')
    def osm(aoi, path, log):
        calls.append('osm')
        path.write_bytes(b'fresh_osm')
    def overture(aoi, path, log):
        path.write_bytes(b'overture')
    monkeypatch.setattr(acq, 'sentinel', sentinel)
    monkeypatch.setattr(acq, 'osm', osm)
    monkeypatch.setattr(acq, 'overture', overture)
    # Legacy file is incomplete, fresh file is complete
    monkeypatch.setattr(acq, 'osm_complete', lambda path: path.read_bytes() != b'legacy_incomplete')
    aoi = gpd.GeoDataFrame(geometry=[box(75, 13, 75.01, 13.01)], crs=4326)
    paths, _ = acq.acquire(aoi, '2026-06-01', lambda _: None)
    assert calls == ['osm']
    assert paths['osm'] != legacy_osm

