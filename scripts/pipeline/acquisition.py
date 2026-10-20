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

# CHANGED: added 'industrial' group. Bare industrial ground (yards, tank farms,
# pavement, construction/quarry sites) has no building footprint to subtract and
# is spectrally indistinguishable from bare soil, so it was previously never
# excluded at all.
GROUPS = {'buildings': {'building': True}, 'roads': {'highway': True},
          'railways': {'railway': True}, 'power': {'power': True},
          'man_made': {'man_made': True}, 'barriers': {'barrier': True},
          'water': {'natural': 'water', 'waterway': True},
          'industrial': {'landuse': ['industrial', 'construction', 'quarry', 'landfill', 'farmyard']},
          'facilities': {'man_made': ['water_works', 'wastewater_plant', 'works', 'storage_tank',
                                     'reservoir_covered', 'water_tower'],
                         'power': ['plant', 'substation', 'generator']}}
REQUIRED_OSM_GROUPS = {'buildings', 'water', 'industrial', 'facilities'}
# All endpoints have documented global coverage; region-only mirrors are unsafe
# for India because a successful empty response would conceal missing evidence.
OVERPASS_ENDPOINTS = ('https://maps.mail.ru/osm/tools/overpass/api/interpreter',
                      'https://overpass.private.coffee/api/interpreter',
                      'https://overpass-api.de/api/interpreter')
HAZARD_QUERY_HALO_M = 30.0


def hazard_query_aoi(aoi):
    """Retain neighboring obstacles before metric exclusion margins are applied."""
    metric = aoi.to_crs(aoi.estimate_utm_crs())
    return gpd.GeoDataFrame(geometry=[metric.geometry.union_all().buffer(HAZARD_QUERY_HALO_M)],
                            crs=metric.crs).to_crs(4326)


def digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def osm_complete(path,include_context=False):
    try:
        import fiona
        existing_layers = fiona.listlayers(path)
        return (set(GROUPS) if include_context else REQUIRED_OSM_GROUPS) <= set(existing_layers)
    except Exception:
        return False


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def sentinel(aoi, date, folder, log):
    from .sentinel_requests import process_request
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
                identity=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
                checkpoint=tile.with_suffix('.request.json')
                def validate_tile(src):
                    if (src.count!=len(bands) or src.width!=w or src.height!=h or src.crs!=crs
                            or any(abs(a-b)>1e-4 for a,b in zip(src.bounds,(x,y-h*10,x+w*10,y)))
                            or set(src.dtypes)!={('float32' if kind=='spectral' else 'uint8')}
                            or src.nodata!=nodata):
                        raise ValueError('Sentinel response has an unexpected grid, type or band count.')
                try:
                    saved=json.loads(checkpoint.read_text(encoding='utf-8'))
                    if saved.get('request_sha256')==identity and saved.get('sha256')==digest(tile):
                        with rasterio.open(tile) as src:validate_tile(src)
                        paths[kind].append(tile);log(f'Sentinel tile {row+1},{col+1}: reusing verified {kind}');continue
                except (OSError,ValueError,rasterio.errors.RasterioError):pass
                log(f'Sentinel tile {row+1},{col+1}: downloading {kind}')
                response=process_request(session,payload,token,log)
                with MemoryFile(response.content) as mem, mem.open() as src:
                    validate_tile(src)
                staged=tile.with_suffix('.tif.partial');staged.write_bytes(response.content);staged.replace(tile)
                write_json(checkpoint,{'request_sha256':identity,'sha256':digest(tile)})
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


def fetch_osm_response(aoi, tags, log, session=None, cache_dir=None):
    """Bounded public-data acquisition; timeout/error responses are never empty evidence."""
    from .overpass_queries import fetch
    return fetch(aoi,tags,log,OVERPASS_ENDPOINTS,session=session,cache_dir=cache_dir)


def _write_osm_xml(payload, path):
    """Convert provider elements for OSMnx's public, offline XML parser."""
    from xml.etree.ElementTree import Element, SubElement, ElementTree
    root = Element('osm', version='0.6', generator='HELPS bounded acquisition')
    unique = {}
    for element in payload['elements']:
        unique.setdefault((element['type'],element['id']),element)
    for element in unique.values():
        kind = element['type']
        attrs = {'id':str(element['id'])}
        if kind == 'node':
            attrs.update(lat=str(element['lat']), lon=str(element['lon']))
        node = SubElement(root, kind, attrs)
        for ref in element.get('nodes', []):
            SubElement(node, 'nd', ref=str(ref))
        for member in element.get('members', []):
            SubElement(node, 'member', type=member['type'], ref=str(member['ref']), role=member.get('role',''))
        for key,value in element.get('tags', {}).items():
            SubElement(node, 'tag', k=key, v=str(value))
    ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def osm(aoi, path, log, include_context=False):
    from .osm_extract import acquire_from_extract,cached_snapshot
    path=Path(path)
    query=hazard_query_aoi(aoi).geometry.union_all()
    attempt=path.parent/'attempt.json'
    refresh=json.loads(attempt.read_text(encoding='utf-8')).get('refresh',False) if attempt.exists() else False
    if path.resolve().is_relative_to((ROOT/'data').resolve()) and cached_snapshot(ROOT,query):
        log('Refreshing the provider OSM extract' if refresh else 'Using verified local OSM extract; no Overpass query is needed')
        return acquire_from_extract(aoi,path,log,include_context)
    try:
        return _osm_overpass(aoi,path,log,include_context)
    except (requests.RequestException,ValueError,RuntimeError) as exc:
        log(f'OSM query service could not complete ({type(exc).__name__}); recovering from a regional extract')
        return acquire_from_extract(aoi,path,log,include_context)


def _osm_overpass(aoi, path, log, include_context=False):
    import osmnx as ox
    from osmnx._errors import InsufficientResponseError
    ox.settings.cache_folder = ROOT/'data/cache/osmnx'
    archive = path.parent/'archive'
    archive.mkdir(parents=True,exist_ok=True)
    query_aoi = hazard_query_aoi(aoi)
    for layer, tags in GROUPS.items():
        if not include_context and layer not in REQUIRED_OSM_GROUPS:
            continue
        log(f'Acquiring OSM {layer}')
        try:
            payload = fetch_osm_response(query_aoi, tags, log,cache_dir=archive/'queries')
            (archive/f'osm_{layer}.json').write_text(json.dumps(payload),encoding='utf-8')
            xml_path = archive/f'osm_{layer}.osm'
            _write_osm_xml(payload, xml_path)
            features = ox.features_from_xml(xml_path, polygon=query_aoi.geometry.iloc[0], tags=tags).reset_index()
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
    query_aoi = hazard_query_aoi(aoi)
    bbox = ','.join(str(v) for v in query_aoi.total_bounds)
    log('Acquiring Overture buildings')
    subprocess.run([sys.executable,'-m','overturemaps.cli','download',f'--bbox={bbox}',
                    '-f','geojson','--type=building','-o',str(raw)], check=True, timeout=1800)
    if not raw.exists() or raw.stat().st_size == 0:
        buildings = gpd.GeoDataFrame(geometry=[], crs=4326)
    else:
        buildings = gpd.read_file(raw)
    if buildings.crs is None:
        buildings = buildings.set_crs(4326)
    buildings.to_crs(4326).to_file(path, driver='GeoJSON')


def acquire(aoi, date, log=print, include_context=False):
    complete=lambda path:osm_complete(path,include_context=True) if include_context else osm_complete(path)
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
                if kind == 'osm' and not complete(path):
                    log('Cached osm.gpkg is missing required layers; re-acquiring')
                else:
                    paths[kind] = path
                    log(f'Reusing verified {kind}')
                    continue
        if not recorded and kind in legacy and legacy[kind].exists():
            if kind == 'osm' and not complete(legacy[kind]):
                log('Legacy Bhadra osm.gpkg is missing required layers; re-acquiring')
            else:
                paths[kind] = legacy[kind]
                log(f'Reusing existing Bhadra {kind}')
    def checkpoint():
        manifest['files'] = {k:{'path':str(p.relative_to(ROOT)), 'sha256':digest(p)} for k,p in paths.items()}
        manifest.setdefault('acquired_at', datetime.now(timezone.utc).isoformat())
        manifest['context_note'] = 'OSM and Overture are acquisition-time snapshots, not historical imagery-date snapshots.'
        manifest['required_osm_layers'] = sorted(GROUPS if include_context else REQUIRED_OSM_GROUPS)
        write_json(manifest_path, manifest)
    checkpoint()
    if 'spectral' not in paths or 'scl' not in paths:
        sentinel(aoi, date, folder, log)
        paths.update(spectral=folder/'spectral.tif', scl=folder/'scl.tif')
        checkpoint()
    if 'osm' not in paths:
        if include_context:osm(aoi, folder/'osm.gpkg', log,include_context=True)
        else:osm(aoi, folder/'osm.gpkg', log)
        if not complete(folder/'osm.gpkg'):
            raise ValueError('Acquired OSM package is missing required layers; processing stopped.')
        paths['osm'] = folder/'osm.gpkg'
        checkpoint()
    if 'overture' not in paths:
        overture(aoi, folder/'overture.geojson', log)
        paths['overture'] = folder/'overture.geojson'
        checkpoint()
    aoi.to_file(folder/'aoi.geojson', driver='GeoJSON')
    return paths, manifest


def acquire_knowledge_inputs(aoi, date, log=print):
    """Compatibility API for old acquisition callers.

    New region-aware UI/CLI builds use region_inputs.resolve_region_inputs.
    This preserves the older date-cache contract for external scripts.
    """
    from scripts.pipeline.landcover import acquire_worldcover
    paths,manifest=acquire(aoi,date,log=log,include_context=True)
    if 'spectral' in paths:
        cover,provenance=acquire_worldcover(paths['spectral'],paths['spectral'].parent/'landcover',log)
        paths['landcover']=cover
        manifest={**manifest,'landcover':provenance}
    return paths,manifest
