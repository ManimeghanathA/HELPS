import json
import requests
import geopandas as gpd
import pytest
from shapely.geometry import box

from scripts.pipeline.acquisition import fetch_osm_response


@pytest.fixture(autouse=True)
def two_test_providers(monkeypatch):
    monkeypatch.setattr('scripts.pipeline.acquisition.OVERPASS_ENDPOINTS',('https://one.invalid','https://two.invalid'))


def test_failed_large_query_subdivides_and_deduplicates_nodes(tmp_path):
    queries=[]
    class Response:
        def __init__(self,fail):self.fail=fail
        def raise_for_status(self):
            if self.fail:raise requests.HTTPError('provider failed')
        def json(self):return {'elements':[{'type':'node','id':1,'lat':13,'lon':75}]}
    class Session:
        def post(self,url,**kwargs):
            queries.append(kwargs['data']['data'])
            return Response(len(queries)<=2)
    aoi=gpd.GeoDataFrame(geometry=[box(75,13,75.2,13.2)],crs=4326)
    result=fetch_osm_response(aoi,{'building':True},lambda _:None,session=Session())
    assert len(queries)>2 and len(result['elements'])==1
    assert 'subqueries' in result['helps_acquisition']


def test_failed_subdivision_never_becomes_empty_success():
    class Session:
        def post(self,*args,**kwargs):raise requests.Timeout('unavailable')
    aoi=gpd.GeoDataFrame(geometry=[box(75,13,75.001,13.001)],crs=4326)
    with pytest.raises(RuntimeError,match='OSM acquisition failed'):
        fetch_osm_response(aoi,{'building':True},lambda _:None,session=Session())


def test_subdivision_preserves_tagged_features_when_later_cells_return_skeletons():
    calls=[]
    class Response:
        def raise_for_status(self):
            if len(calls)<=2:raise requests.HTTPError('large query')
        def json(self):
            element={'type':'way','id':1,'nodes':[10,11,10]}
            if len(calls)==3:element['tags']={'building':'yes'}
            return {'elements':[element]}
    class Session:
        def post(self,*args,**kwargs):calls.append(1);return Response()
    aoi=gpd.GeoDataFrame(geometry=[box(75,13,75.2,13.2)],crs=4326)
    result=fetch_osm_response(aoi,{'building':True},lambda _:None,session=Session())
    assert result['elements'][0]['tags']=={'building':'yes'}
