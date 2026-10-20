"""Bounded retry of required missing public OSM groups; never fabricate empty layers."""
import sys,json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[3]
DRAFT=ROOT/'HELPS - draft'
sys.path.insert(0,str(DRAFT/'.review-deps'));sys.path.insert(0,str(DRAFT))
import geopandas as gpd
import osmnx as ox
from scripts.pipeline.acquisition import fetch_osm_response,hazard_query_aoi,GROUPS,_write_osm_xml
from scripts.pipeline.inputs import load_aoi

class GetSession:
    def post(self,url,data,timeout,headers):
        return requests.get(url,params=data,timeout=timeout,headers=headers)

aoi=hazard_query_aoi(load_aoi(DRAFT/'data/raw/Bhadra/bhadra_entire_region.geojson'))
folder=DRAFT/'data/inputs/45295356fafbdae35c06ddec/2026-06-01'
for layer in ['industrial','facilities']:
    payload=fetch_osm_response(aoi,GROUPS[layer],lambda s:print(layer,s,flush=True),session=GetSession())
    (folder/'archive'/f'osm_{layer}.json').write_text(json.dumps(payload))
    xml=folder/'archive'/f'osm_{layer}.osm';_write_osm_xml(payload,xml)
    try:
        frame=ox.features_from_xml(xml,polygon=aoi.geometry.iloc[0],tags=GROUPS[layer]).reset_index()[['geometry']]
    except ox._errors.InsufficientResponseError as exc:
        if 'No matching features' not in str(exc):raise
        frame=gpd.GeoDataFrame(geometry=[],crs=4326)
    frame.to_file(folder/'fresh_exclusions.gpkg',layer=layer,driver='GPKG')
    print('SAVED',layer,len(frame),flush=True)
