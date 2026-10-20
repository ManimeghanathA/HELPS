"""Acquisition tests use tiny on-disk provider rasters; no network traffic."""
import importlib
import json
from contextlib import contextmanager

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import box
from scripts.knowledge.contracts import SourceAsset


@pytest.fixture
def dem():
    return importlib.import_module('scripts.pipeline.elevation')


def aoi(bounds=(75.99, 13.99, 76.01, 14.01)):
    return gpd.GeoDataFrame(geometry=[box(*bounds)], crs=4326)


def raster(path, bounds, value=100, hole=False, crs=4326):
    path.parent.mkdir(parents=True, exist_ok=True)
    values = np.full((120, 120), value, dtype='float32')
    if hole:
        values[40:80, 40:80] = -9999
    with rasterio.open(path, 'w', driver='GTiff', width=120, height=120,
                       count=1, dtype='float32', crs=crs, nodata=-9999,
                       transform=from_bounds(*bounds, 120, 120)) as dst:
        dst.write(values, 1)
    return path


def provider(monkeypatch, dem, tmp_path, hole=False, fail=False):
    opened = []
    @contextmanager
    def open_tile(url):
        opened.append(url)
        if fail:
            raise OSError('private provider exception text')
        # Real GeoTIFFs with the provider's four neighboring geographic cells.
        import re
        lat, lon = re.search(r'_N(\d+)_00_E(\d+)_00_DEM', url).groups()
        lat, lon = int(lat), int(lon)
        path = raster(tmp_path / f'{lat}-{lon}.tif',
                      (lon, lat, lon+1, lat+1), 100+lon, hole=hole)
        with rasterio.open(path) as src:
            yield src
    monkeypatch.setattr(dem, '_open_remote', open_tile)
    return opened


def test_acquires_four_cells_and_reuses_verified_metric_cache(dem, tmp_path, monkeypatch):
    opened = provider(monkeypatch, dem, tmp_path)
    asset = dem.acquire_dem(aoi(), tmp_path, lambda _: None)
    assert len(opened) == 4
    assert asset.units == 'm' and asset.coverage_state == 'verified'
    assert asset.metadata['surface_type'] == 'DSM'
    assert asset.metadata['vertical_datum'] == 'EGM2008'
    with rasterio.open(asset.path) as src:
        assert src.crs.is_projected and src.res == (30, 30)
        assert np.isfinite(src.read(1, masked=True)).all()
        assert not np.ma.getmaskarray(src.read(1, masked=True)).any()
    again = dem.acquire_dem(aoi(), tmp_path, lambda _: None)
    assert len(opened) == 4 and again.sha256 == asset.sha256


def test_region_acquisition_preserves_native_provider_windows(dem,tmp_path,monkeypatch):
    opened=provider(monkeypatch,dem,tmp_path)
    raw=tmp_path/'data/raw/area/dem/native'
    dem.acquire_dem(aoi(),tmp_path,lambda _:None,raw_directory=raw)
    windows=list(raw.glob('*.tif'))
    assert len(windows)==len(opened)==4
    for path in windows:
        with rasterio.open(path) as src:
            assert src.crs.to_epsg()==4326
            assert src.tags()['source_window'].startswith('Native provider grid')


def test_corrupt_cache_is_rebuilt_and_manifest_matches(dem, tmp_path, monkeypatch):
    opened = provider(monkeypatch, dem, tmp_path)
    first = dem.acquire_dem(aoi(), tmp_path, lambda _: None)
    first.path.write_bytes(b'corrupt')
    repaired = dem.acquire_dem(aoi(), tmp_path, lambda _: None)
    assert len(opened) == 8 and repaired.sha256 == first.sha256
    manifest = json.loads(repaired.path.with_name('manifest.json').read_text())
    assert manifest['sha256'] == repaired.sha256


def test_holes_fail_without_publishing_completion_manifest(dem, tmp_path, monkeypatch):
    provider(monkeypatch, dem, tmp_path, hole=True)
    with pytest.raises(ValueError, match='coverage|nodata'):
        dem.acquire_dem(aoi((75.4, 13.4, 75.6, 13.6)), tmp_path, lambda _: None)
    assert not list((tmp_path/'data/cache/elevation').rglob('manifest.json'))


def test_provider_failure_is_not_empty_elevation_and_hides_exception_text(dem, tmp_path, monkeypatch):
    provider(monkeypatch, dem, tmp_path, fail=True)
    with pytest.raises(RuntimeError, match='DEM acquisition failed') as exc:
        dem.acquire_dem(aoi(), tmp_path, lambda _: None)
    assert 'private provider' not in str(exc.value)
    assert not list((tmp_path/'data/cache/elevation').rglob('manifest.json'))


def test_covering_local_fabdem_preferred_but_edge_without_halo_downloads(dem, tmp_path, monkeypatch):
    local = raster(tmp_path/'data/raw/DEM/FABDEM_N13E075.tif', (75,13,76,14), 77)
    monkeypatch.setattr(dem, 'KNOWN_FABDEM_SHA256', dem.file_sha256(local))
    opened = provider(monkeypatch, dem, tmp_path)
    asset = dem.acquire_dem(aoi((75.4,13.4,75.41,13.41)), tmp_path, lambda _: None)
    assert not opened and asset.source_id == 'fabdem-v1-2-n13e075'
    assert asset.metadata['original_path'] == str(local.resolve())
    assert asset.metadata['surface_type'] == 'DTM estimate'
    edge = dem.acquire_dem(aoi((75.9999,13.4,76,13.401)), tmp_path, lambda _: None)
    assert opened and edge.metadata['surface_type'] == 'DSM'


def test_local_nodata_is_not_reused(dem, tmp_path, monkeypatch):
    local = raster(tmp_path/'data/raw/DEM/FABDEM_N13E075.tif', (75,13,76,14), hole=True)
    monkeypatch.setattr(dem, 'KNOWN_FABDEM_SHA256', dem.file_sha256(local))
    opened = provider(monkeypatch, dem, tmp_path)
    asset = dem.acquire_dem(aoi((75.45,13.45,75.46,13.46)), tmp_path, lambda _: None)
    assert opened and asset.metadata['surface_type'] == 'DSM'


def test_bad_manifest_metadata_cannot_assert_units_or_coverage(dem, tmp_path, monkeypatch):
    opened = provider(monkeypatch, dem, tmp_path)
    asset = dem.acquire_dem(aoi(), tmp_path, lambda _: None)
    path = asset.path.with_name('manifest.json')
    manifest = json.loads(path.read_text())
    manifest['units'] = 'feet'
    path.write_text(json.dumps(manifest))
    dem.acquire_dem(aoi(), tmp_path, lambda _: None)
    assert len(opened) == 8


def test_oversize_or_invalid_aoi_rejected_before_remote_access(dem, tmp_path, monkeypatch):
    opened = provider(monkeypatch, dem, tmp_path)
    for frame in [aoi((60,10,80,30)), aoi().set_crs(None, allow_override=True)]:
        with pytest.raises(ValueError):
            dem.acquire_dem(frame, tmp_path, lambda _: None)
    assert not opened


@pytest.mark.parametrize('tamper', ['nodata', 'crs', 'surface_type'])
def test_rehashed_cache_still_requires_true_valid_grid_and_product(dem, tmp_path, monkeypatch, tamper):
    opened = provider(monkeypatch, dem, tmp_path)
    asset = dem.acquire_dem(aoi(), tmp_path, lambda _: None)
    path = asset.path.with_name('manifest.json')
    manifest = json.loads(path.read_text())
    if tamper == 'surface_type':
        manifest['metadata']['surface_type'] = 'surveyed bare earth'
    else:
        with rasterio.open(asset.path, 'r+') as src:
            if tamper == 'crs':
                src.crs = 'EPSG:32644'
            else:
                values = src.read(1)
                values[2,2] = np.nan
                src.write(values, 1)
        manifest['sha256'] = dem.file_sha256(asset.path)
    path.write_text(json.dumps(manifest))
    repaired = dem.acquire_dem(aoi(), tmp_path, lambda _: None)
    assert len(opened) == 8
    assert repaired.metadata['surface_type'] == 'DSM'


def test_southern_western_tile_names_and_bounded_network_environment(dem, monkeypatch):
    grid = dem._grid(aoi((-75.51,-13.51,-75.5,-13.5)))
    assert '_S14_00_W076_00_DEM/' in dem._tiles(grid)[0]
    observed = {}
    @contextmanager
    def env(**kwargs):
        observed.update(kwargs)
        yield
    @contextmanager
    def remote(path):
        observed['path'] = path
        yield object()
    monkeypatch.setattr(dem.rasterio, 'Env', env)
    monkeypatch.setattr(dem.rasterio, 'open', remote)
    with dem._open_remote('https://copernicus-dem-30m.s3.amazonaws.com/example.tif'):
        pass
    assert observed['path'].startswith('/vsicurl/https://')
    assert observed['GDAL_HTTP_TIMEOUT'] == '20'
    assert observed['GDAL_HTTP_MAX_RETRY'] == '1'
    assert observed['GDAL_DISABLE_READDIR_ON_OPEN'] == 'EMPTY_DIR'


def test_unrecognized_local_fabdem_hash_cannot_claim_known_product(dem, tmp_path, monkeypatch):
    raster(tmp_path/'data/raw/DEM/FABDEM_N13E075.tif', (75,13,76,14), 77)
    opened = provider(monkeypatch, dem, tmp_path)
    asset = dem.acquire_dem(aoi((75.4,13.4,75.41,13.41)), tmp_path, lambda _: None)
    assert opened and asset.metadata['surface_type'] == 'DSM'


def test_explicit_source_coverage_preflight_checks_units_hash_halo_and_nodata(dem, tmp_path):
    path = raster(tmp_path/'chosen.tif', (75,13,76,14), 77)
    chosen = SourceAsset('chosen',path,kind='raster',units='m',sha256=dem.file_sha256(path))
    assert dem.verify_dem_coverage(chosen,aoi((75.4,13.4,75.41,13.41))) is None
    with pytest.raises(ValueError,match='coverage|nodata'):
        dem.verify_dem_coverage(chosen,aoi((75.9999,13.4,76,13.401)))
    chosen.units = None
    with pytest.raises(ValueError,match='units'):
        dem.verify_dem_coverage(chosen,aoi((75.4,13.4,75.41,13.41)))
    chosen.units = 'ft'
    assert dem.verify_dem_coverage(chosen,aoi((75.4,13.4,75.41,13.41))) is None
    chosen.sha256 = '0'*64
    with pytest.raises(ValueError,match='checksum'):
        dem.verify_dem_coverage(chosen,aoi((75.4,13.4,75.41,13.41)))
    raster(path,(75,13,76,14),hole=True)
    chosen.sha256 = dem.file_sha256(path)
    with pytest.raises(ValueError,match='coverage|nodata'):
        dem.verify_dem_coverage(chosen,aoi((75.4,13.4,75.41,13.41)))
