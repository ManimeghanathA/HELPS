import geopandas as gpd
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
from shapely.geometry import box

from scripts.pipeline.monthly import acquire_scl_quality


def test_scl_shortlist_tiles_large_aoi_without_downsampling_or_grid_gaps(tmp_path):
    calls=[]
    class Response:
        def __init__(self,content):self.content=content
        def raise_for_status(self):pass
    class Session:
        def post(self,url,**kwargs):
            payload=kwargs['json'];w=payload['output']['width'];h=payload['output']['height']
            assert w<=2500 and h<=2500
            calls.append((w,h))
            crs='EPSG:'+payload['input']['bounds']['properties']['crs'].split('/')[-1]
            with MemoryFile() as mem:
                with mem.open(driver='GTiff',width=w,height=h,count=1,dtype='uint8',crs=crs,
                              transform=from_bounds(*payload['input']['bounds']['bbox'],w,h),nodata=0) as dst:
                    dst.write(np.full((h,w),5,dtype='uint8'),1)
                return Response(mem.read())
    aoi=gpd.GeoDataFrame(geometry=[box(500000,1500000,500080,1552020)],crs=32643)
    result=acquire_scl_quality(Session(),'fixture-token',aoi,'2026-10-12',tmp_path)
    assert len(calls)==2 and result['usable_support']>.999999
    assert result['measurement_resolution_m']==20
    again=acquire_scl_quality(Session(),'fixture-token',aoi,'2026-10-12',tmp_path)
    assert len(calls)==2 and again==result
