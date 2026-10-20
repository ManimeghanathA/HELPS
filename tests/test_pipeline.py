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
@pytest.mark.parametrize('tree_cover', [True,False])
@pytest.mark.parametrize('screening_profile',['conservative','calibrated'])
def test_pipeline_synthetic(tmp_path, open_land, tree_cover, screening_profile):
    transform = from_origin(500000, 1500200, 10, 10)
    spectral = np.zeros((6, 20, 20), dtype='float32')
    spectral[:] = np.array([.1, .1, .2, .28, .3, .2])[:, None, None]
    scl = np.full((1, 20, 20), 5 if open_land else 6, dtype='uint8')
    for name, array in [('spectral', spectral), ('scl', scl)]:
        with rasterio.open(tmp_path / f'{name}.tif', 'w', driver='GTiff', width=20,
                           height=20, count=len(array), dtype=array.dtype,
                           transform=transform, crs=32643) as dst:
            dst.write(array)
    aoi = gpd.GeoDataFrame(geometry=[box(500000,1500000,500200,1500200)], crs=32643)
    buildings = gpd.GeoDataFrame(geometry=[], crs=32643)
    cover_path=None
    if tree_cover:
        cover_path=tmp_path/'landcover.tif'
        with rasterio.open(cover_path,'w',driver='GTiff',width=20,height=20,count=1,
                           dtype='uint8',transform=transform,crs=32643) as dst:
            dst.write(np.full((20,20),10,dtype='uint8'),1)
    summary = process_inputs(tmp_path/'spectral.tif', tmp_path/'scl.tif',
                             buildings, {key:buildings.copy() for key in ['water','industrial','facilities']},
                             aoi, tmp_path/'result', 'test', lambda _: None,landcover_path=cover_path,screening_profile=screening_profile)
    survives=open_land and (not tree_cover or screening_profile=='calibrated')
    assert summary['final_zones'] == (1 if survives else 0)
    assert summary['audits']['passed']
    if tree_cover:
        assert summary['landcover']['applied_as_exclusion']==(screening_profile=='conservative')
    if survives:
        zones = gpd.read_file(tmp_path/'result'/'final_zones.gpkg')
        assert zones.geometry.difference(aoi.geometry.iloc[0].buffer(-30 if screening_profile=='conservative' else 0)).area.sum() < 1e-4
    assert (tmp_path/'result'/'final_zones.png').exists()
    assert (tmp_path/'result'/'final_zones.geojson').exists()
