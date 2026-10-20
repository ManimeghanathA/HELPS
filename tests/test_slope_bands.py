import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, Polygon


def write_slope(path, values):
    values=np.asarray(values,dtype='float32')
    with rasterio.open(path,'w',driver='GTiff',height=values.shape[0],width=values.shape[1],count=1,
                       dtype='float32',crs='EPSG:32643',transform=from_origin(500000,1500030,30,30),nodata=-9999) as ds:
        ds.write(values,1)
    return path


def test_exact_interval_edges_are_not_cumulative():
    from scripts.ui.slope_layers import classify_slope
    values=np.array([0,.01,2,2.01,4,4.01,6,6.01,8,10,12,15,15.01,np.nan,-9999])
    assert classify_slope(values).tolist()==[0,1,1,2,2,3,3,4,4,5,5,6,7,8,8]


def test_bands_partition_actual_boundary_preserving_hole_and_unknown(tmp_path):
    from scripts.ui.slope_layers import compute_slope_bands
    raster=write_slope(tmp_path/'slope.tif',[[0,2,4,6],[8,10,15,-9999]])
    outer=box(500010,1499975,500110,1500025)
    hole=box(500040,1499995,500050,1500005)
    parent=Polygon(outer.exterior.coords,[hole.exterior.coords])
    bands=compute_slope_bands([parent],'EPSG:32643',raster)
    assert sum(row['geometry'].area for row in bands)==pytest.approx(parent.area,abs=1e-6)
    assert next(row for row in bands if row['evidence']=='unknown')['geometry'].area>0
    for i,row in enumerate(bands):
        assert parent.covers(row['geometry'])
        assert row['geometry'].intersection(hole).area==0
        for other in bands[i+1:]:
            assert row['geometry'].intersection(other['geometry']).area==pytest.approx(0,abs=1e-6)
    # The 0 degree band uses a single clipped source cell, not the entire parent.
    assert next(row for row in bands if row['band_id']==0)['geometry'].area<parent.area


def test_outside_raster_support_is_unknown_not_flat(tmp_path):
    from scripts.ui.slope_layers import compute_slope_bands
    raster=write_slope(tmp_path/'slope.tif',[[0]])
    parent=box(500000,1500000,500060,1500030)
    bands=compute_slope_bands([parent],'EPSG:32643',raster)
    areas={row['band_id']:row['geometry'].area for row in bands}
    assert areas=={0:900,8:900}


def test_requested_single_ceiling_labels_preserve_overflow_and_unknown():
    from scripts.ui.slope_layers import BREAKS,band_properties,classify_slope
    assert BREAKS==(0,2,4,6,8,12,15)
    assert [band_properties(i)['label'] for i in range(7)]==['0°','2°','4°','6°','8°','12°','15°']
    above,unknown=classify_slope(np.array([16,np.nan]))
    assert band_properties(int(above))['evidence']=='measured'
    assert band_properties(int(above))['label']=='>15°'
    assert band_properties(int(unknown))['evidence']=='unknown'
    assert above!=unknown


def test_enriched_package_reuses_preserved_raster_without_own_raster_folder(tmp_path):
    import geopandas as gpd
    from scripts.ui.slope_layers import cached_slope_bands
    package=tmp_path/'enriched.gpkg'
    gpd.GeoDataFrame(geometry=[box(500000,1500000,500030,1500030)],crs=32643).to_file(package,layer='terrain')
    original=write_slope(tmp_path/'original-slope.tif',[[0]])
    other=write_slope(tmp_path/'other-slope.tif',[[4]])
    first=cached_slope_bands(str(package),package.stat().st_mtime_ns,1,str(original))
    second=cached_slope_bands(str(package),package.stat().st_mtime_ns,1,str(other))
    assert first['features'][0]['properties']['band_id']==0
    assert second['features'][0]['properties']['band_id']==2
    assert first['features'][0]['properties']['area_m2']==pytest.approx(900)
