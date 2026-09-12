import json

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
from shapely.geometry import box

from scripts.pipeline import acquisition as acq


def test_sentinel_request_and_preprocessing_share_grid(tmp_path, monkeypatch):
    requests = []
    class Response:
        def __init__(self, content=b''):
            self.content = content
        def raise_for_status(self):
            pass
        def json(self):
            return {'access_token':'test-token'}
    class Session:
        def post(self, url, **kwargs):
            if 'token' in url:
                return Response()
            body = kwargs['json']
            requests.append(body)
            w,h = body['output']['width'],body['output']['height']
            count = 1 if 'UINT8' in body['evalscript'] else 6
            crs = 'EPSG:'+body['input']['bounds']['properties']['crs'].split('/')[-1]
            dtype = 'uint8' if count == 1 else 'float32'
            with MemoryFile() as mem:
                with mem.open(driver='GTiff',width=w,height=h,count=count,dtype=dtype,
                              crs=crs,transform=from_bounds(*body['input']['bounds']['bbox'],w,h),
                              nodata=0 if count == 1 else -9999) as dst:
                    dst.write(np.full((count,h,w),5 if count == 1 else .2,dtype=dtype))
                return Response(mem.read())
    monkeypatch.setattr(acq.requests,'Session',Session)
    monkeypatch.setenv('CDSE_CLIENT_ID','test')
    monkeypatch.setenv('CDSE_CLIENT_SECRET','test')
    aoi = gpd.GeoDataFrame(geometry=[box(75,13,75.001,13.001)],crs=4326)
    acq.sentinel(aoi,'2026-06-01',tmp_path,lambda _:None)
    assert len(requests) == 2
    with rasterio.open(tmp_path/'spectral.tif') as spectral, rasterio.open(tmp_path/'scl.tif') as scl:
        assert spectral.transform == scl.transform
        assert spectral.crs == scl.crs
        assert spectral.res == (10,10)
        assert spectral.count == 6 and scl.count == 1
    assert requests[0]['input']['data'][0]['dataFilter']['timeRange']['from'] == '2026-06-01T00:00:00Z'
