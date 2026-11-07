"""Windowed RGB validation and overlap-aware segmentation checkpoints."""
import json
import math
from uuid import uuid4

import geopandas as gpd
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.windows import Window, bounds
from shapely.geometry import box

from .rgb_model import run_segmentation
from .repository import _atomic_json
from .slope_zones import polygon_parts
from .sources import file_sha256

CORE = 896
HALO = 64
SEED_CLASSES = (3, 4)


def tile_plan(aoi, metres):
    west, south, east, north = aoi.bounds
    left = math.floor(west/metres)*metres
    top = math.ceil(north/metres)*metres
    width, height = math.ceil((east-left)/metres), math.ceil((top-south)/metres)
    grid = from_origin(left, top, metres, metres)
    tiles = []
    for row in range(0, height, CORE):
        for col in range(0, width, CORE):
            window = Window(col, row, min(CORE, width-col), min(CORE, height-row))
            if aoi.intersection(box(*bounds(window, grid))).area > 0:
                tiles.append([int(x) for x in window.flatten()])
    return grid, width, height, tiles


def prepare_tile(vrt, core, aoi, target=None):
    read_window = Window(core.col_off, core.row_off, core.width + 2*HALO, core.height + 2*HALO)
    # VRT origin includes the halo. Core is offset by HALO within this read.
    tile_transform = vrt.window_transform(read_window)
    core_transform = vrt.window_transform(Window(core.col_off+HALO, core.row_off+HALO, core.width, core.height))
    clip = aoi.intersection(box(*bounds(Window(0, 0, core.width, core.height), core_transform)))
    inside = geometry_mask([clip], (int(core.height), int(core.width)), core_transform, invert=True)
    if not inside.any():
        return None
    valid = (vrt.dataset_mask(window=read_window) > 0)
    if vrt.count == 4:
        valid &= vrt.read(4, window=read_window) == 255
    core_valid = valid[HALO:HALO+int(core.height), HALO:HALO+int(core.width)]
    if not core_valid[inside].all():
        raise ValueError(f'RGB has uncovered or transparent pixels in tile at row {core.row_off:g}, column {core.col_off:g}.')
    if target is None:
        return clip
    rgb = vrt.read((1, 2, 3), window=read_window)
    rgb[:, ~valid] = 0
    with rasterio.open(target, 'w', driver='GTiff', count=3, width=rgb.shape[2], height=rgb.shape[1],
                       dtype='uint8', transform=tile_transform, crs=vrt.crs, photometric='RGB',
                       compress='deflate') as out:
        out.write(rgb)
    return clip


def process_tile(root, vrt, aoi, core, folder, log):
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'classified.gpkg'
    marker = folder / 'complete.json'
    if marker.is_file():
        saved = json.loads(marker.read_text(encoding='utf-8'))
        if saved['state'] == 'no_pixels' or (target.is_file() and file_sha256(target) == saved['sha256']):
            return
    attempt = folder / 'attempts' / uuid4().hex
    attempt.mkdir(parents=True)
    clip = prepare_tile(vrt, core, aoi, attempt / 'rgb.tif')
    if clip is None:
        _atomic_json(marker, {'state': 'no_pixels'})
        return
    metrics = run_segmentation(root, attempt, log)
    regions = gpd.read_file(attempt / 'segmentation.gpkg', layer='classified_segments')
    rows = []
    for region in regions.itertuples(index=False):
        for part in polygon_parts(region.geometry.intersection(clip)):
            rows.append(dict(class_id=int(region.class_id), class_name=region.class_name,
                             is_seed=int(region.class_id) in SEED_CLASSES, geometry=part))
    result = gpd.GeoDataFrame(rows if rows else {'class_id': [], 'class_name': [], 'is_seed': [], 'geometry': []},
                              geometry='geometry', crs=vrt.crs)
    pending = folder / 'classified-pending.gpkg'
    pending.unlink(missing_ok=True)
    result.to_file(pending, layer='classified_segments', index=False)
    pending.replace(target)
    _atomic_json(marker, dict(state='complete', sha256=file_sha256(target), **metrics))
    for name in ('sam-masks.npz', 'rgb.tif', 'segmentation.gpkg'):
        (attempt / name).unlink(missing_ok=True)
