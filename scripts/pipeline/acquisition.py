"""AOI-scoped acquisition. Completion manifests distinguish data from partial downloads."""
import hashlib
import json
import math
import os
import subprocess
import sys
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import rasterio
import requests
from dotenv import load_dotenv
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge

from scripts.pipeline.inputs import ROOT, cache_key, legacy_inputs, data_directory

GROUPS = {'buildings': {'building': True}, 'roads': {'highway': True},
          'railways': {'railway': True}, 'power': {'power': True},
          'man_made': {'man_made': True}, 'barriers': {'barrier': True},
          'water': {'natural': 'water', 'waterway': True}}


def digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def sentinel(aoi, date, folder, log):
    load_dotenv(ROOT/'.env')
    client, secret = os.getenv('CDSE_CLIENT_ID'), os.getenv('CDSE_CLIENT_SECRET')
    if not client or not secret:
        raise ValueError('Set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET in .env to download Sentinel imagery.')
    crs = aoi.estimate_utm_crs()
    bounds = aoi.to_crs(crs).total_bounds
    left, bottom = [math.floor(v/10)*10 for v in bounds[:2]]
    right, top = [math.ceil(v/10)*10 for v in bounds[2:]]
    width, height = int((right-left)/10), int((top-bottom)/10)
    if width*height > 40_000_000:
        raise ValueError('AOI exceeds the 40 million pixel local processing limit; use a smaller region.')
    tiles = folder/'archive'/'tiles'
    tiles.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    token_response = session.post('https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token',
        data={'grant_type':'client_credentials','client_id':client,'client_secret':secret}, timeout=60)
    token_response.raise_for_status()
    token = token_response.json()['access_token']
    paths = {'spectral': [], 'scl': []}
    for row in range(math.ceil(height/2400)):
        for col in range(math.ceil(width/2400)):
            w, h = min(2400,width-col*2400), min(2400,height-row*2400)
            x, y = left+col*24000, top-row*24000
            for kind, bands, sample, nodata in [
                ('spectral',['B02','B03','B04','B08','B11','B12'],'FLOAT32',-9999),
                ('scl',['SCL'],'UINT8',0)]:
                tile = tiles/f'{row}_{col}_{kind}.tif'
                log(f'Sentinel tile {row+1},{col+1}: {kind}')
                setup = {'input':[{'bands':bands}], 'output':{'bands':len(bands),'sampleType':sample,'nodataValue':nodata}}
                if kind == 'spectral':
                    setup['input'][0]['units'] = 'REFLECTANCE'
                script = '//VERSION=3\nfunction setup(){return '+json.dumps(setup)+';}\n'
                script += 'function evaluatePixel(s){return ['+','.join('s.'+b for b in bands)+'];}'
                payload = {'input':{'bounds':{'bbox':[x,y-h*10,x+w*10,y],
                    'properties':{'crs':f'http://www.opengis.net/def/crs/EPSG/0/{crs.to_epsg()}'}},
                    'data':[{'type':'sentinel-2-l2a','dataFilter':{'timeRange':{
                        'from':date+'T00:00:00Z','to':date+'T23:59:59Z'},'mosaickingOrder':'leastCC'}}]},
                    'output':{'width':w,'height':h,'responses':[{'identifier':'default','format':{'type':'image/tiff'}}]},
                    'evalscript':script}
                response = session.post('https://sh.dataspace.copernicus.eu/api/v1/process', json=payload,
                    headers={'Authorization':'Bearer '+token,'Accept':'image/tiff'}, timeout=180)
                response.raise_for_status()
                with MemoryFile(response.content) as mem, mem.open() as src:
                    if src.count != len(bands) or src.width != w or src.height != h or src.crs != crs:
                        raise ValueError('Sentinel response has an unexpected grid or band count.')
                tile.write_bytes(response.content)
                paths[kind].append(tile)
    for kind, tile_paths in paths.items():
        with ExitStack() as stack:
            sources = [stack.enter_context(rasterio.open(p)) for p in tile_paths]
            data, transform = merge(sources)
            profile = sources[0].profile.copy()
            profile.update(height=data.shape[1], width=data.shape[2], transform=transform, compress='deflate')
            with MemoryFile() as mem:
                with mem.open(**profile) as dst:
                    dst.write(data)
                with mem.open() as src:
                    clipped, clipped_transform = mask(src, aoi.to_crs(crs).geometry, crop=True)
                profile.update(height=clipped.shape[1],width=clipped.shape[2],transform=clipped_transform)
                with rasterio.open(folder/f'{kind}.tif', 'w', **profile) as dst:
                    dst.write(clipped)


def osm(aoi, path, log):
    import osmnx as ox
    from osmnx._errors import InsufficientResponseError
    ox.settings.cache_folder = ROOT/'data/cache/osmnx'
    for layer, tags in GROUPS.items():
        log(f'Acquiring OSM {layer}')
        try:
            features = ox.features_from_polygon(aoi.geometry.iloc[0], tags).reset_index()
            features = gpd.clip(features, aoi)
        except InsufficientResponseError as exc:
            if 'No matching features' not in str(exc):
                raise
            features = gpd.GeoDataFrame(geometry=[], crs=4326)
        # Preserve provider attributes as JSON to avoid mixed OSM tag types in GPKG.
        attrs = features.drop(columns='geometry').to_json(orient='records')
        frame = gpd.GeoDataFrame({'attributes':[json.dumps(v) for v in json.loads(attrs)]},
                                 geometry=features.geometry.reset_index(drop=True), crs=4326)
        frame.to_file(path, layer=layer, driver='GPKG')


def overture(aoi, path, log):
    raw = path.parent/'archive'/'overture_bbox.geojson'
    raw.parent.mkdir(exist_ok=True)
    raw.unlink(missing_ok=True)
    bbox = ','.join(str(v) for v in aoi.total_bounds)
    log('Acquiring Overture buildings')
    subprocess.run([sys.executable,'-m','overturemaps.cli','download',f'--bbox={bbox}',
                    '-f','geojson','--type=building','-o',str(raw)], check=True, timeout=1800)
    if not raw.exists() or raw.stat().st_size == 0:
        buildings = gpd.GeoDataFrame(geometry=[], crs=4326)
    else:
        buildings = gpd.read_file(raw)
    if buildings.crs is None:
        buildings = buildings.set_crs(4326)
    clipped = gpd.clip(buildings.to_crs(4326), aoi) if len(buildings) else buildings
    clipped.to_file(path, driver='GeoJSON')


def acquire(aoi, date, log=print):
    key = cache_key(aoi, date)
    folder = ROOT/'data'/'inputs'/key/date
    data_directory(folder)
    manifest_path = folder/'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'key':key,'date':date,'files':{}}
    legacy = legacy_inputs(aoi, date) or {}
    paths = {}
    names = {'spectral':'spectral.tif','scl':'scl.tif','osm':'osm.gpkg','overture':'overture.geojson'}
    for kind, filename in names.items():
        recorded = manifest['files'].get(kind)
        if recorded:
            path = ROOT/recorded['path']
            if path.exists() and digest(path) == recorded['sha256']:
                paths[kind] = path
                log(f'Reusing verified {kind}')
                continue
        if not recorded and kind in legacy and legacy[kind].exists():
            paths[kind] = legacy[kind]
            log(f'Reusing existing Bhadra {kind}')
    def checkpoint():
        manifest['files'] = {k:{'path':str(p.relative_to(ROOT)), 'sha256':digest(p)} for k,p in paths.items()}
        manifest.setdefault('acquired_at', datetime.now(timezone.utc).isoformat())
        manifest['context_note'] = 'OSM and Overture are acquisition-time snapshots, not historical imagery-date snapshots.'
        write_json(manifest_path, manifest)
    checkpoint()
    if 'spectral' not in paths or 'scl' not in paths:
        sentinel(aoi, date, folder, log)
        paths.update(spectral=folder/'spectral.tif', scl=folder/'scl.tif')
        checkpoint()
    if 'osm' not in paths:
        osm(aoi, folder/'osm.gpkg', log)
        paths['osm'] = folder/'osm.gpkg'
        checkpoint()
    if 'overture' not in paths:
        overture(aoi, folder/'overture.geojson', log)
        paths['overture'] = folder/'overture.geojson'
        checkpoint()
    aoi.to_file(folder/'aoi.geojson', driver='GeoJSON')
    return paths, manifest
