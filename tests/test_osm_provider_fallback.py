import geopandas as gpd
import requests
from shapely.geometry import box
from scripts.pipeline import acquisition


def test_independent_global_provider_is_available_as_fallback(monkeypatch):
    monkeypatch.setattr(acquisition,'OVERPASS_ENDPOINTS',tuple(sorted(acquisition.OVERPASS_ENDPOINTS,key=lambda u:'maps.mail.ru' in u)))
    class Response:
        def __init__(self,url):self.url=url
        def raise_for_status(self):
            if self.url!='https://maps.mail.ru/osm/tools/overpass/api/interpreter':raise requests.HTTPError('provider at capacity')
        def json(self):return {'elements':[{'type':'node','id':1,'lat':13,'lon':75}]}
    class Session:
        def post(self,url,**kwargs):return Response(url)
    aoi=gpd.GeoDataFrame(geometry=[box(75,13,75.001,13.001)],crs=4326)
    result=acquisition.fetch_osm_response(aoi,{'building':True},lambda _:None,session=Session())
    assert result['elements'][0]['id']==1
