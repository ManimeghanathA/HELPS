import json

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

from scripts.pipeline.inputs import load_aoi, cache_key
from scripts.pipeline.processing import process_inputs
from scripts.processing.building_subtraction import subtract_buildings


def test_aoi_key_depends_on_geometry_and_date(tmp_path):
    path = tmp_path / 'aoi.geojson'
    path.write_text(json.dumps(mapping(box(75, 13, 75.01, 13.01))))
    aoi = load_aoi(path)
    assert cache_key(aoi, '2026-06-01') == cache_key(aoi.copy(), '2026-06-01')
    assert cache_key(aoi, '2026-06-01') != cache_key(aoi, '2026-06-02')
    other = gpd.GeoDataFrame(geometry=[box(76, 13, 76.01, 13.01)], crs=4326)
    assert cache_key(aoi, '2026-06-01') != cache_key(other, '2026-06-01')
    with pytest.raises(ValueError):
        cache_key(aoi, '../bad')


def test_reject_non_polygon_aoi(tmp_path):
    path = tmp_path / 'point.geojson'
    path.write_text('{"type":"Point","coordinates":[75,13]}')
    with pytest.raises(ValueError, match='Polygon'):
        load_aoi(path)


def test_buildings_can_remove_all_terrain():
    terrain = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100)], crs=32643)
    assert subtract_buildings(terrain, terrain).empty


@pytest.mark.parametrize('open_land', [True, False])
def test_pipeline_synthetic(tmp_path, open_land):
    transform = from_origin(500000, 1500200, 10, 10)
    spectral = np.zeros((6, 20, 20), dtype='float32')
    spectral[:] = np.array([.1, .1, .2, .3, .3, .2])[:, None, None]
    scl = np.full((1, 20, 20), 5 if open_land else 6, dtype='uint8')
    for name, array in [('spectral', spectral), ('scl', scl)]:
        with rasterio.open(tmp_path / f'{name}.tif', 'w', driver='GTiff', width=20,
                           height=20, count=len(array), dtype=array.dtype,
                           transform=transform, crs=32643) as dst:
            dst.write(array)
    aoi = gpd.GeoDataFrame(geometry=[box(500000,1500000,500200,1500200)], crs=32643)
    buildings = gpd.GeoDataFrame(geometry=[], crs=32643)
    summary = process_inputs(tmp_path/'spectral.tif', tmp_path/'scl.tif',
                             buildings, aoi, tmp_path/'result', 'test', lambda _: None)
    assert summary['final_zones'] == (1 if open_land else 0)
    assert summary['audits']['passed']
    assert (tmp_path/'result'/'final_zones.png').exists()
    assert (tmp_path/'result'/'final_zones.geojson').exists()
