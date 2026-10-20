import numpy as np
import geopandas as gpd
import rasterio
from shapely.geometry import box
from scripts.knowledge.dem import compute_derivatives, prepare_terrain_rasters
from scripts.knowledge.contracts import SourceAsset


def test_four_degree_plane_and_invalid_outer_edge():
    x=np.arange(5,dtype='float32')*30
    z=np.tile(x*np.tan(np.deg2rad(4)),(5,1))
    slope,rough,valid=compute_derivatives(z,np.ones(z.shape,bool),30,30)
    assert valid[1:-1,1:-1].all() and not valid[0].any()
    assert np.allclose(slope[valid],4,atol=1e-4)
    assert rough[valid].max()<1e-4
    assert np.isnan(slope[~valid]).all()


def test_flat_and_xy_plane_and_nodata_neighborhood():
    y,x=np.indices((7,7)); z=x*3+y*6
    valid=np.ones(z.shape,bool); valid[3,3]=False
    slope,rough,observed=compute_derivatives(z,valid,30,30)
    assert not observed[2:5,2:5].any()
    assert np.allclose(slope[observed],np.degrees(np.arctan(np.sqrt(.1**2+.2**2))))
    assert rough[observed].max()<1e-5
    slope,rough,observed=compute_derivatives(z*0,np.ones(z.shape,bool),30,30)
    assert np.max(slope[observed])==0


def test_prepare_converts_feet_preserves_fraction_and_reports_cropped_support(tmp_path):
    source=tmp_path/'feet.tif'
    with rasterio.open(source,'w',driver='GTiff',width=10,height=10,count=1,dtype='float32',crs=32643,transform=rasterio.transform.from_origin(0,300,30,30),nodata=-9999) as ds:
        ds.write(np.full((10,10),100.25/0.3048,dtype='float32'),1)
    aoi=gpd.GeoDataFrame(geometry=[box(-60,-60,360,360)],crs=32643)
    assets=prepare_terrain_rasters(SourceAsset('dem',source,units='ft'),aoi,tmp_path/'out')
    with rasterio.open(assets.elevation_path) as ds:
        array=ds.read(1,masked=True)
        assert ds.dtypes[0]=='float32'
        assert np.allclose(array.compressed(),100.25,atol=1e-4)
    assert assets.manifest['aoi_elevation_valid_fraction']<1
    assert assets.manifest['derivative_halo_cells']==1
