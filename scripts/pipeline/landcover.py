"""Acquire cropped public WorldCover evidence and align categories to the reference grid."""
import json
import math
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import from_bounds
from scripts.pipeline.acquisition import digest, write_json


def acquire_worldcover(reference_path, output, log=print):
    output = Path(output); output.mkdir(parents=True,exist_ok=True)
    aligned_path = output/'worldcover_2021_aligned.tif'
    manifest_path = output/'worldcover_2021.json'
    reference_hash = digest(reference_path)
    if aligned_path.exists() and manifest_path.exists():
        metadata = json.loads(manifest_path.read_text())
        if metadata.get('reference_sha256') == reference_hash and metadata.get('sha256') == digest(aligned_path):
            log('Reusing verified aligned WorldCover'); return aligned_path,metadata
    with rasterio.open(reference_path) as reference:
        profile = reference.profile.copy()
        west,south,east,north = transform_bounds(reference.crs,4326,*reference.bounds)
        aligned = np.zeros((reference.height,reference.width),dtype='uint8')
        references = []
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
                          CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
                          GDAL_HTTP_CONNECTTIMEOUT='10',GDAL_HTTP_TIMEOUT='30',GDAL_HTTP_MAX_RETRY='1'):
            for lat in range(math.floor(south/3)*3, math.floor(north/3)*3+1,3):
                for lon in range(math.floor(west/3)*3, math.floor(east/3)*3+1,3):
                    tile = f'{"N" if lat >= 0 else "S"}{abs(lat):02d}{"E" if lon >= 0 else "W"}{abs(lon):03d}'
                    url = f'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif'
                    log(f'Reading WorldCover reference tile {tile}')
                    with rasterio.open(url) as src:
                        bounds = (max(west-.0002,src.bounds.left),max(south-.0002,src.bounds.bottom),
                                  min(east+.0002,src.bounds.right),min(north+.0002,src.bounds.top))
                        window = from_bounds(*bounds,transform=src.transform).round_offsets().round_lengths()
                        data = src.read(1,window=window)
                        transform = src.window_transform(window)
                        crop_path = output/f'worldcover_2021_{tile}_crop.tif'
                        crop_profile = src.profile.copy()
                        crop_profile.update(height=data.shape[0],width=data.shape[1],transform=transform,compress='deflate')
                        with rasterio.open(crop_path,'w',**crop_profile) as dst: dst.write(data,1)
                        reproject(data,aligned,src_transform=transform,src_crs=src.crs,
                                  dst_transform=reference.transform,dst_crs=reference.crs,
                                  src_nodata=0,dst_nodata=0,resampling=Resampling.nearest,init_dest_nodata=False)
                        references.append({'url':url,'crop_path':str(crop_path),'sha256':digest(crop_path)})
        profile.update(count=1,dtype='uint8',nodata=0,compress='deflate')
        temporary = aligned_path.with_suffix('.tmp.tif')
        with rasterio.open(temporary,'w',**profile) as dst: dst.write(aligned,1)
        temporary.replace(aligned_path)
    metadata = {'dataset':'ESA WorldCover v200','year':2021,'license':'CC BY 4.0',
                'reference_path':str(reference_path),'reference_sha256':reference_hash,
                'sources':references,'sha256':digest(aligned_path),
                'nonzero_pixels':int(np.count_nonzero(aligned)),
                'date_limit':'Historical supplementary evidence; not current clearance or ground truth.'}
    write_json(manifest_path,metadata)
    log(f'Aligned WorldCover: {metadata["nonzero_pixels"]:,} covered pixels')
    return aligned_path,metadata
