"""Bounded automatic elevation acquisition; DSM is never labelled bare earth.

Public API: acquire_dem(GeoDataFrame, project_root, log=print) -> SourceAsset.
Only complete, finite metric coverage including the processing halo is published.
"""
import hashlib
import json
import math
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window, from_bounds
from rasterio.warp import reproject, transform_bounds, Resampling

from scripts.knowledge.contracts import SourceAsset
from scripts.knowledge.dem import metric_crs
from scripts.knowledge.sources import file_sha256

RESOLUTION_M = 30
HALO_CELLS = 3  # derivative cell, grid rounding and interpolation guard
MAX_PIXELS = 4_000_000
MAX_SOURCE_PIXELS = 8_000_000
MAX_TILES = 16
MAX_OUTPUT_BYTES = 32_000_000
KNOWN_FABDEM_SHA256 = 'a6d536e0b0e260efb99223e0b24498cf605275ad6800c0035dd61c7070230302'
LICENSE_URL = 'https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf'
PROVIDER_METADATA = {
    'product': 'Copernicus DEM GLO-30 Public, 2021 release',
    'provider': 'Sinergise / AWS Open Data',
    'surface_type': 'DSM',
    'vertical_datum': 'EGM2008',
    'native_resolution': '1 arcsecond latitude; longitude spacing varies by latitude',
    'license': LICENSE_URL,
    'attribution': 'Copernicus DEM GLO-30 / European Union, DLR and Airbus; distributed by Sinergise on AWS',
    'source_url': 'https://registry.opendata.aws/copernicus-dem/',
    'uncertainty': 'Surface includes vegetation, buildings and infrastructure; not surveyed landing terrain. Per-cell vertical accuracy unverified.',
    'reference_date_status': 'Product release 2021; per-cell observation dates unknown; not the imagery observation date',
}
FABDEM_METADATA = {
    'product': 'FABDEM v1-2', 'surface_type': 'DTM estimate',
    'license': 'CC BY-NC-SA 4.0',
    'attribution': 'University of Bristol / Fathom, forest and building removed Copernicus DEM',
    'source_url': 'https://research-information.bris.ac.uk/en/datasets/fabdem-v1-2/',
    'native_resolution': '1 arcsecond approximately 30m',
    'vertical_datum': 'unknown', 'vertical_datum_status': 'unknown',
    'reference_date_status': 'product edition known; per-cell observation dates unverified',
    'uncertainty': 'Modelled forest/building removal; not surveyed bare earth; per-cell vertical accuracy unknown',
}


@contextmanager
def _open_remote(url):
    # Fixed anonymous public HTTPS endpoint, no Earthdata/CDSE/AWS credentials.
    # /vsicurl/ uses HTTP range requests, not full-tile downloads. GDAL rejects
    # servers that ignore ranges. Disable sibling-file probing and directory lists.
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
                      CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
                      GDAL_HTTP_CONNECTTIMEOUT='5', GDAL_HTTP_TIMEOUT='20',
                      GDAL_HTTP_MAX_RETRY='1', GDAL_HTTP_RETRY_DELAY='1',
                      CPL_VSIL_CURL_CHUNK_SIZE='16384',
                      CPL_VSIL_CURL_CACHE_SIZE='16777216', VSI_CACHE=False,
                      GDAL_CACHEMAX=32 * 1024 * 1024):
        with rasterio.open('/vsicurl/' + url) as src:
            yield src


def _grid(aoi):
    if aoi.crs is None or aoi.empty or any(g is None or g.is_empty or not g.is_valid for g in aoi.geometry):
        raise ValueError('DEM requires a nonempty valid AOI with CRS')
    geographic = aoi.to_crs(4326).total_bounds
    if not np.isfinite(geographic).all() or geographic[0] < -180 or geographic[2] > 180 or geographic[1] < -80 or geographic[3] > 84 or geographic[2]-geographic[0] > 6:
        raise ValueError('DEM AOI exceeds supported local UTM latitude/longitude extent')
    crs = metric_crs(aoi)
    left, bottom, right, top = aoi.to_crs(crs).total_bounds
    left, bottom = [math.floor(v/RESOLUTION_M)*RESOLUTION_M-HALO_CELLS*RESOLUTION_M for v in (left,bottom)]
    right, top = [math.ceil(v/RESOLUTION_M)*RESOLUTION_M+HALO_CELLS*RESOLUTION_M for v in (right,top)]
    width, height = round((right-left)/RESOLUTION_M), round((top-bottom)/RESOLUTION_M)
    if min(width,height) < 1 or width*height > MAX_PIXELS:
        raise ValueError('DEM exceeds the four million pixel processing limit; select a smaller AOI')
    return {'crs': crs.to_string(), 'bounds': [left,bottom,right,top],
            'width': width, 'height': height, 'resolution_m': RESOLUTION_M,
            'halo_cells': HALO_CELLS, 'schema': 1}


def _tiles(grid):
    west,south,east,north = transform_bounds(grid['crs'],4326,*grid['bounds'],densify_pts=21)
    # Provider pixels are point-centred on degree boundaries; expand one source
    # pixel so that the half-pixel shared boundary cannot leave an unrequested tile.
    pad = 1/3600
    cells = [(lat,lon) for lat in range(max(-90,math.floor(south-pad)),min(90,math.ceil(north+pad)))
             for lon in range(max(-180,math.floor(west-pad)),min(180,math.ceil(east+pad)))]
    if len(cells) > MAX_TILES:
        raise ValueError('DEM exceeds the sixteen source tile limit')
    urls = []
    for lat,lon in cells:
        name = f'Copernicus_DSM_COG_10_{"N" if lat>=0 else "S"}{abs(lat):02d}_00_{"E" if lon>=0 else "W"}{abs(lon):03d}_00_DEM'
        urls.append(f'https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif')
    return urls


def _project_window(src, grid, raw_path=None):
    if src.crs is None or src.count != 1 or src.transform.b or src.transform.d or min(src.res)<=0:
        raise ValueError('DEM source has missing CRS or unsupported grid')
    bounds = transform_bounds(grid['crs'],src.crs,*grid['bounds'],densify_pts=21)
    window = from_bounds(*bounds, transform=src.transform)
    left,top = math.floor(window.col_off)-2,math.floor(window.row_off)-2
    right,bottom = math.ceil(window.col_off+window.width)+2,math.ceil(window.row_off+window.height)+2
    left,top,right,bottom = max(0,left),max(0,top),min(src.width,right),min(src.height,bottom)
    shape = (grid['height'],grid['width'])
    projected = np.full(shape,np.nan,dtype='float32')
    if right<=left or bottom<=top:
        return projected
    if (right-left)*(bottom-top) > MAX_SOURCE_PIXELS:
        raise ValueError('DEM source window exceeds bounded pixel limit')
    window = Window(left,top,right-left,bottom-top)
    native = src.read(1,window=window,masked=True)
    if raw_path is not None:
        raw_path=Path(raw_path);raw_path.parent.mkdir(parents=True,exist_ok=True)
        profile=src.profile.copy()
        profile.update(driver='GTiff',width=int(window.width),height=int(window.height),transform=src.window_transform(window),compress='deflate')
        with rasterio.open(raw_path,'w',**profile) as dst:
            dst.write(native.filled(src.nodata if src.nodata is not None else 0),1)
            if np.ma.getmaskarray(native).any():dst.write_mask((~np.ma.getmaskarray(native)).astype('uint8')*255)
            dst.update_tags(source_window='Native provider grid, before projection/resampling')
    source = native.astype('float32')
    valid = ~np.ma.getmaskarray(source)&np.isfinite(source.data)
    transform = from_origin(grid['bounds'][0],grid['bounds'][3],RESOLUTION_M,RESOLUTION_M)
    options = dict(src_transform=src.window_transform(window),src_crs=src.crs,
                   dst_transform=transform,dst_crs=grid['crs'],resampling=Resampling.bilinear)
    reproject(np.where(valid,source.data,np.nan),projected,src_nodata=np.nan,dst_nodata=np.nan,**options)
    support = np.zeros(shape,dtype='float32')
    reproject(valid.astype('float32'),support,dst_nodata=0,**options)
    projected[support<1-1e-6] = np.nan
    return projected


def _cache_asset(path, manifest, grid):
    if manifest.get('grid') != grid or manifest.get('units') != 'm' or manifest.get('coverage_state') != 'verified':
        raise ValueError('DEM cache identity/units/coverage mismatch')
    metadata = manifest.get('metadata',{})
    if metadata.get('product') not in (PROVIDER_METADATA['product'],FABDEM_METADATA['product']):
        raise ValueError('DEM cache product identity mismatch')
    baseline = PROVIDER_METADATA if metadata['product']==PROVIDER_METADATA['product'] else FABDEM_METADATA
    if any(metadata.get(key)!=value for key,value in baseline.items()) or metadata.get('grid')!=grid:
        raise ValueError('DEM cache provenance mismatch')
    expected_id = 'copernicus-glo30-public-2021' if baseline is PROVIDER_METADATA else 'fabdem-v1-2-n13e075'
    if manifest.get('source_id')!=expected_id:
        raise ValueError('DEM cache source identity mismatch')
    if baseline is PROVIDER_METADATA and [item['url'] for item in metadata.get('source_windows',[])]!=_tiles(grid):
        raise ValueError('DEM cache source tile identity mismatch')
    if path.stat().st_size > MAX_OUTPUT_BYTES or file_sha256(path) != manifest['sha256']:
        raise ValueError('DEM cache checksum/size mismatch')
    with rasterio.open(path) as src:
        expected = from_origin(grid['bounds'][0],grid['bounds'][3],RESOLUTION_M,RESOLUTION_M)
        if src.crs.to_string()!=grid['crs'] or src.transform!=expected or src.width!=grid['width'] or src.height!=grid['height'] or src.count!=1 or src.units[0]!='m':
            raise ValueError('DEM cache grid/unit mismatch')
        values = src.read(1,masked=True)
        if np.ma.getmaskarray(values).any() or not np.isfinite(values.data).all():
            raise ValueError('DEM cache nodata coverage incomplete')
    return SourceAsset(manifest['source_id'],path,kind='raster',sha256=manifest['sha256'],units='m',
                       coverage_state='verified',crs=grid['crs'],metadata=manifest['metadata'])


def verify_dem_coverage(asset, aoi):
    """Raise ValueError unless chosen source covers the complete AOI + metric halo.

    This is a read-only preflight, not a claim that supplied product provenance is
    verified. Feet are accepted because the terrain builder converts them to m.
    """
    if asset.units not in ('m','metre','meter','metres','meters','ft','feet','foot'):
        raise ValueError('DEM vertical units must be known metres or feet')
    grid = _grid(aoi)
    try:
        if asset.sha256 and file_sha256(asset.path).lower()!=asset.sha256.lower():
            raise ValueError('DEM source checksum mismatch')
        with rasterio.open(asset.path) as src:
            if src.crs is None:
                raise ValueError('DEM source CRS required')
            values = _project_window(src,grid)
        if not np.isfinite(values).all():
            raise ValueError('DEM coverage/nodata incomplete for AOI and required processing halo')
    except (OSError,rasterio.errors.RasterioError):
        raise ValueError('DEM source cannot be opened for coverage verification') from None


def acquire_dem(aoi, root, log=print, raw_directory=None):
    """Acquire complete metre elevations for AOI + 90m halo; raise on uncertainty.

    Returned source dates remain unknown; acquisition time is metadata only.
    Callers must preserve DSM limitations when presenting terrain evidence.
    """
    root = Path(root).resolve()
    grid = _grid(aoi)
    key = hashlib.sha256(json.dumps(grid,sort_keys=True).encode()).hexdigest()[:24]
    folder = root/'data/cache/elevation'/key
    path,manifest_path = folder/'dem.tif',folder/'manifest.json'
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        asset = _cache_asset(path,manifest,grid)
        log('Reusing verified elevation cache')
        return asset
    except (OSError,ValueError,KeyError,TypeError,AttributeError,rasterio.errors.RasterioError):
        pass
    folder.mkdir(parents=True,exist_ok=True)
    # An invalid old manifest must not advertise completion after a failed repair.
    manifest_path.unlink(missing_ok=True)
    if shutil.disk_usage(folder).free < MAX_OUTPUT_BYTES*2:
        raise ValueError('Insufficient disk space for bounded DEM cache')
    elevation = None
    local = root/'data/raw/DEM/FABDEM_N13E075.tif'
    if local.is_file() and file_sha256(local)==KNOWN_FABDEM_SHA256:
        try:
            with rasterio.open(local) as src:
                candidate = _project_window(src,grid)
            if np.isfinite(candidate).all():
                elevation = candidate
                metadata = {**FABDEM_METADATA,'original_path':str(local),'original_sha256':KNOWN_FABDEM_SHA256}
                source_id = 'fabdem-v1-2-n13e075'
                log('Using verified covering local FABDEM')
        except (ValueError,rasterio.errors.RasterioError):
            log('Local FABDEM lacks valid coverage; acquiring public DEM')
    if elevation is None:
        urls = _tiles(grid)
        elevation = np.full((grid['height'],grid['width']),np.nan,dtype='float32')
        windows = []
        for index,url in enumerate(urls):
            log(f'Acquiring public Copernicus GLO-30 DSM window {index+1}/{len(urls)}')
            try:
                with _open_remote(url) as src:
                    if src.units[0] not in (None,'m','metre','meter'):
                        raise ValueError('Public DEM reports incompatible vertical units')
                    raw_path=Path(raw_directory)/f'provider-window-{index+1}.tif' if raw_directory is not None else None
                    values = _project_window(src,grid,raw_path=raw_path)
                    windows.append({'url':url,'crs':src.crs.to_string(),'native_resolution':list(src.res),
                                    'projected_window_sha256':hashlib.sha256(values.tobytes()).hexdigest()})
            except (OSError,ValueError,rasterio.errors.RasterioError):
                raise RuntimeError('DEM acquisition failed: public tile unavailable or invalid; no complete elevation evidence published') from None
            take = ~np.isfinite(elevation)&np.isfinite(values)
            elevation[take] = values[take]
        metadata = {**PROVIDER_METADATA,'source_windows':windows}
        source_id = 'copernicus-glo30-public-2021'
    if not np.isfinite(elevation).all():
        raise ValueError('DEM coverage includes nodata in AOI or required processing halo; no complete elevation evidence published')
    metadata.update(acquired_at=datetime.now(timezone.utc).isoformat(),
                    processing_halo_m=HALO_CELLS*RESOLUTION_M,
                    resampling='bilinear; every contributing source cell must be valid',
                    coverage_check='all cells finite on complete aligned metric rectangle including halo',
                    grid=grid)
    with TemporaryDirectory(prefix='pending-',dir=folder) as temporary:
        staged = Path(temporary)/'dem.tif'
        with rasterio.open(staged,'w',driver='GTiff',width=grid['width'],height=grid['height'],
                           count=1,dtype='float32',crs=grid['crs'],
                           transform=from_origin(grid['bounds'][0],grid['bounds'][3],RESOLUTION_M,RESOLUTION_M),
                           nodata=np.nan,compress='deflate',tiled=True) as dst:
            dst.write(elevation,1)
            dst.set_band_unit(1,'m')
            dst.update_tags(product=metadata['product'],surface_type=metadata['surface_type'])
        manifest = {'source_id':source_id,'sha256':file_sha256(staged),'grid':grid,
                    'units':'m','coverage_state':'verified','metadata':metadata}
        _cache_asset(staged,manifest,grid)
        staged.replace(path)
        staged_manifest = Path(temporary)/'manifest.json'
        staged_manifest.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        staged_manifest.replace(manifest_path)
    return _cache_asset(path,manifest,grid)
