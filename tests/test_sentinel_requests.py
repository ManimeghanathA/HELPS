import requests
import pytest

def test_process_rate_limit_waits_provider_milliseconds_and_retries(monkeypatch):
    from scripts.pipeline import sentinel_requests as transport
    waits=[];logs=[]
    monkeypatch.setattr(transport.time,'sleep',waits.append)
    class Session:
        def __init__(self):self.responses=iter([429,200]);self.calls=0
        def post(self,*args,**kwargs):
            self.calls+=1;r=requests.Response();r.status_code=next(self.responses);r.headers['Retry-After']='3398';r._content=b'';r._content_consumed=True;return r
    session=Session();response=transport.process_request(session,{},'token',logs.append)
    assert response.status_code==200 and session.calls==2
    assert any(wait>=3.398 for wait in waits) and any('rate limit' in line.lower() for line in logs)

def test_process_rate_limit_is_bounded_and_bad_requests_are_not_retried(monkeypatch):
    from scripts.pipeline import sentinel_requests as transport
    monkeypatch.setattr(transport.time,'sleep',lambda _:None)
    class Session:
        def __init__(self,status):self.status=status;self.calls=0
        def post(self,*args,**kwargs):self.calls+=1;r=requests.Response();r.status_code=self.status;r._content=b'';r._content_consumed=True;return r
    session=Session(429)
    with pytest.raises(requests.HTTPError,match='rate limit'):transport.process_request(session,{},'token',lambda _:None,max_attempts=3)
    assert session.calls==3
    session=Session(400)
    with pytest.raises(requests.HTTPError):transport.process_request(session,{},'token',lambda _:None)
    assert session.calls==1

def test_sentinel_resume_reuses_validated_tile_and_rejects_changed_bytes(tmp_path,monkeypatch):
    from scripts.pipeline import acquisition as acq
    import geopandas as gpd
    import numpy as np
    from shapely.geometry import box
    from rasterio.io import MemoryFile
    from rasterio.transform import from_bounds
    monkeypatch.setenv('CDSE_CLIENT_ID','test-client');monkeypatch.setenv('CDSE_CLIENT_SECRET','test-secret')
    calls=[];fail=[True]
    class Response:
        status_code=200
        def __init__(self,content=b''):self.content=content
        def raise_for_status(self):pass
        def json(self):return {'access_token':'test-token'}
    class Session:
        def post(self,url,**kwargs):
            if 'openid-connect' in url:return Response()
            p=kwargs['json'];kind='spectral' if 'B02' in p['evalscript'] else 'scl';calls.append(kind)
            if kind=='scl' and fail[0]:raise requests.HTTPError('fixture interruption')
            w,h=p['output']['width'],p['output']['height'];count,dtype,value=(6,'float32',.1) if kind=='spectral' else (1,'uint8',5)
            with MemoryFile() as mem:
                with mem.open(driver='GTiff',width=w,height=h,count=count,dtype=dtype,crs='EPSG:'+p['input']['bounds']['properties']['crs'].split('/')[-1],transform=from_bounds(*p['input']['bounds']['bbox'],w,h),nodata=-9999 if kind=='spectral' else 0) as dst:dst.write(np.full((count,h,w),value,dtype=dtype))
                return Response(mem.read())
    monkeypatch.setattr(acq.requests,'Session',Session)
    aoi=gpd.GeoDataFrame(geometry=[box(500000,1500000,500040,1500040)],crs=32643)
    with pytest.raises(requests.HTTPError):acq.sentinel(aoi,'2026-10-12',tmp_path,lambda _:None)
    fail[0]=False;acq.sentinel(aoi,'2026-10-12',tmp_path,lambda _:None)
    assert calls==['spectral','scl','scl']
    acq.sentinel(aoi,'2026-10-12',tmp_path,lambda _:None);assert calls==['spectral','scl','scl']
    (tmp_path/'archive/tiles/0_0_spectral.tif').write_bytes(b'corrupt')
    acq.sentinel(aoi,'2026-10-12',tmp_path,lambda _:None);assert calls[-1]=='spectral' and len(calls)==4
    acq.sentinel(aoi,'2026-10-13',tmp_path,lambda _:None);assert calls[-2:]==['spectral','scl'] and len(calls)==6
