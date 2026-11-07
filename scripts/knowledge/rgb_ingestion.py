"""Build reviewable HELPS knowledge from a dated RGB raster and GeoJSON."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path

import geopandas as gpd
import rasterio
from pyproj import Transformer
from rasterio.enums import ColorInterp, Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window
from shapely import union_all
from shapely.errors import GEOSException
from shapely.geometry import Polygon, shape
from shapely.ops import transform

from .chronology import validate_new_date
from .contracts import KnowledgeBuildSpec, SourceAsset
from .repository import _atomic_json
from .rgb_model import PILOT
from .rgb_tiles import CORE, HALO, SEED_CLASSES, prepare_tile, process_tile, tile_plan
from .slope_zones import generate_slope_zones, polygon_parts
from .sources import file_sha256

MAX_BOUNDARY_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 256 * 1024 * 1024
MAX_AREA_M2 = 4_000_000
MAX_SPAN_M = 8000
MAX_TILES = 32
SLOPE_LIMIT = 15
GEOMETRY_RULES = dict(min_area_m2=900, min_width_m=30, min_length_m=30,
                      min_clear_diameter_m=30, slope_tolerance_deg=0)


def valid_date(day, current=None):
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat()
    return validate_new_date(day, current_date=current, today=today)


def read_boundary(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict):
            raise ValueError()
        crs = data.get('crs')
        if crs and crs.get('properties', {}).get('name', '').upper() not in (
                'URN:OGC:DEF:CRS:OGC:1.3:CRS84', 'OGC:CRS84', 'EPSG:4326', 'URN:OGC:DEF:CRS:EPSG::4326'):
            raise ValueError()
        if data.get('type') == 'FeatureCollection':
            geometries = [shape(row['geometry']) for row in data['features']]
        elif data.get('type') == 'Feature':
            geometries = [shape(data['geometry'])]
        else:
            geometries = [shape(data)]
    except (AttributeError, GEOSException, KeyError, TypeError, ValueError) as exc:
        raise ValueError('Upload valid WGS84 GeoJSON with Polygon or MultiPolygon geometry.') from exc
    if not geometries or any(g.geom_type not in ('Polygon', 'MultiPolygon') or g.is_empty or not g.is_valid
                             for g in geometries):
        raise ValueError('The GeoJSON must contain valid, nonempty polygons.')
    geometry = union_all(geometries)
    west, south, east, north = geometry.bounds
    if not (-180 <= west < east <= 180 and -80 <= south < north <= 84
            and east-west < .5 and north-south < .5):
        raise ValueError('Use longitude and latitude in WGS84 and crop to a small area within UTM coverage.')
    frame = gpd.GeoDataFrame(geometry=[geometry], crs=4326)
    frame = frame.to_crs(frame.estimate_utm_crs())
    left, bottom, right, top = frame.total_bounds
    if frame.area.iloc[0] > MAX_AREA_M2 or max(right-left, top-bottom) > MAX_SPAN_M:
        raise ValueError('Use an area of at most 4 km² and no more than 8 km across.')
    return frame


def inspect_inputs(boundary, image, day, metres=None):
    aoi = read_boundary(boundary)
    geometry = aoi.geometry.iloc[0]
    try:
        with rasterio.open(image, GEOREF_SOURCES='INTERNAL') as src:
            if (src.driver != 'GTiff' or src.crs is None or src.count not in (3, 4)
                    or src.colorinterp[:3] != (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
                    or any(t != 'uint8' for t in src.dtypes)
                    or (src.count == 4 and src.colorinterp[3] not in (ColorInterp.alpha, ColorInterp.undefined))):
                raise ValueError('Upload an 8-bit georeferenced RGB GeoTIFF with optional alpha.')
            tags = {key.lower(): value for key, value in src.tags().items()}
            if any(tags[key][:10] != day for key in ('date', 'observation_date', 'acquisition_date', 'date_acquired')
                   if key in tags):
                raise ValueError('The capture date differs from the date recorded in the GeoTIFF.')
            transformer = Transformer.from_crs(src.crs, aoi.crs, always_xy=True)
            col, row = src.width/2, src.height/2
            center, x, y = (transformer.transform(*(src.transform * pixel))
                            for pixel in ((col, row), (col+1, row), (col, row+1)))
            native = max(math.dist(center, x), math.dist(center, y))
            if not math.isfinite(native) or native <= 0:
                raise ValueError('The image has an invalid native resolution.')
            if metres is None:
                metres = max(.5, min(2, round(native, 6)))
            if not math.isfinite(metres) or not .5 <= metres <= 2 or native > 2.02 or metres < native*.99:
                raise ValueError('Use RGB at 2 m or finer and choose a working resolution from 0.5 to 2 m without upsampling.')
            outline = Polygon([src.transform * p for p in (
                (0, 0), (src.width, 0), (src.width, src.height), (0, src.height))])
            step = max(src.bounds.right-src.bounds.left, src.bounds.top-src.bounds.bottom) / 256
            if not step or not outline.is_valid:
                raise ValueError('The RGB GeoTIFF has an invalid georeferenced extent.')
            footprint = transform(transformer.transform, outline.segmentize(step))
            if not footprint.is_valid:
                raise ValueError('The RGB footprint cannot be transformed to the study area grid.')
            if geometry.difference(footprint).area > .01:
                raise ValueError('The image footprint must cover the entire GeoJSON boundary.')
    except rasterio.errors.RasterioError as exc:
        raise ValueError('Could not read the RGB GeoTIFF.') from exc
    grid, width, height, tiles = tile_plan(geometry, metres)
    if not tiles or len(tiles) > MAX_TILES:
        raise ValueError('The boundary requires more than 32 tiles. Crop the area or choose a coarser supported resolution.')
    return aoi, metres, grid, width, height, tiles


@contextmanager
def open_grid(image, aoi, grid, width, height):
    padded = grid * rasterio.Affine.translation(-HALO, -HALO)
    with rasterio.open(image, GEOREF_SOURCES='INTERNAL') as src:
        alpha = {'src_alpha': 4} if src.count == 4 else {'add_alpha': True}
        with WarpedVRT(src, crs=aoi.crs, transform=padded, width=width+2*HALO,
                       height=height+2*HALO, resampling=Resampling.bilinear, **alpha) as vrt:
            yield vrt


def resolve_elevation(root, aoi, log):
    from dotenv import dotenv_values
    from scripts.pipeline.elevation import PROVIDER_METADATA, acquire_dem, verify_dem_coverage

    value = os.environ.get('HELPS_RGB_DEM') or dotenv_values(root / '.env').get('HELPS_RGB_DEM')
    if value:
        supplied = SourceAsset('rgb-configured-elevation', (root / value).resolve(), kind='dem', units='m')
        verify_dem_coverage(supplied, aoi)
        return supplied
    cached = root / PILOT / 'source_dsm_crop.tif'
    if cached.is_file():
        source = SourceAsset('copernicus-glo30-pilot-window', cached, kind='dem', units='m',
                             coverage_state='verified', metadata=PROVIDER_METADATA)
        try:
            verify_dem_coverage(source, aoi)
            return source
        except ValueError:
            pass
    return acquire_dem(aoi, root, log=log)


def build_rgb(root, folder, job, progress):
    from .build import build_knowledge
    from .dem import prepare_terrain_rasters

    image, boundary = folder / 'rgb.tif', folder / 'boundary.geojson'
    plan = json.loads((folder / 'rgb-plan.json').read_text(encoding='utf-8'))
    if any(file_sha256(path) != plan[key] for path, key in (
            (image, 'image_sha256'), (boundary, 'boundary_sha256'))):
        raise ValueError('An input changed after upload. Submit a new build.')
    completed = folder / 'manifest.json'
    if completed.is_file() and (folder / 'knowledge.gpkg').is_file():
        spec = json.loads(completed.read_text(encoding='utf-8'))['spec']
        if spec['dataset_id'] != job['dataset_id'] or spec['source_mode'] != 'retained':
            raise ValueError('Existing package does not match this RGB job.')
        return build_knowledge(spec, log=lambda message: progress(message, 96)).to_dict()
    progress('Checking RGB coverage', 4)
    aoi, metres, grid, width, height, tiles = inspect_inputs(boundary, image, job['date'], plan['resolution_m'])
    geometry = aoi.geometry.iloc[0]
    tile_folders = [folder / 'tiles' / f'r{row:07d}-c{col:07d}' for col, row, _, _ in tiles]
    with open_grid(image, aoi, grid, width, height) as vrt:
        covered_tiles = sum(prepare_tile(vrt, Window(*coords), geometry) is not None for coords in tiles)
        if not covered_tiles:
            raise ValueError('The boundary contains no complete RGB working pixels.')
    progress('Obtaining covering elevation', 9)
    dem = resolve_elevation(root, aoi, lambda message: progress(message, 9))
    with open_grid(image, aoi, grid, width, height) as vrt:
        for index, (coords, target) in enumerate(zip(tiles, tile_folders), 1):
            percent = 12 + round(60*(index-1)/len(tiles))
            progress(f'GeoSAM tile {index} of {len(tiles)}', percent)
            process_tile(root, vrt, geometry, Window(*coords), target,
                         lambda message: progress(f'Tile {index}/{len(tiles)} · {message}', percent))

    progress('Joining brown ground and low vegetation', 74)
    ground = []
    segments, masks = 0, 0
    for tile in tile_folders:
        record = json.loads((tile / 'complete.json').read_text(encoding='utf-8'))
        if record['state'] == 'no_pixels':
            continue
        layer = gpd.read_file(tile / 'classified.gpkg', layer='classified_segments')
        segments += len(layer)
        masks += record['mask_count']
        selection = layer.loc[layer.class_id.isin(SEED_CLASSES)]
        if not selection.empty:
            ground.append(selection.geometry.union_all())
    polygons = list(polygon_parts(union_all(ground)))
    parents = gpd.GeoDataFrame(
        {'terrain_id': [f'RGB-{i+1}' for i in range(len(polygons))],
         'dataset_id': [job['dataset_id']] * len(polygons)}, geometry=polygons, crs=aoi.crs)
    parents['source_zone_id'] = parents['terrain_id']
    progress('Calculating slope and applying the 15° limit', 79)
    assets = prepare_terrain_rasters(dem, aoi, folder / 'screening', resolution_m=30)
    zones, _, audit = generate_slope_zones(parents, assets, {}, thresholds=(SLOPE_LIMIT,),
                                           parameters=GEOMETRY_RULES)
    audit.to_csv(folder / 'screening-audit.csv', index=False)
    seeds = zones[['zone_id', 'geometry']].rename(columns={'zone_id': 'source_zone_id'})
    seed_path, aoi_path = folder / 'candidate-seed.gpkg', folder / 'boundary.gpkg'
    for path, frame in ((seed_path, seeds), (aoi_path, aoi)):
        staged = path.with_name(path.stem + '-pending.gpkg')
        staged.unlink(missing_ok=True)
        frame.to_file(staged, index=False)
        staged.replace(path)
    progress('Packaging candidates for review', 91)
    prefix = job['dataset_id']
    spec = KnowledgeBuildSpec(
        prefix, job['region_id'], job['date'], SourceAsset(prefix+'-boundary', aoi_path, kind='aoi'),
        SourceAsset(prefix+'-seed', seed_path, kind='candidate_seed', date=job['date']), dem, folder,
        sources={'rgb': SourceAsset(prefix+'-rgb', image, kind='rgb', date=job['date'],
                                     sha256=plan['image_sha256'], coverage_state='verified',
                                     metadata={'date_provenance': 'operator supplied'})},
        parameters={**GEOMETRY_RULES, 'resolution_m': 30, 'rgb_resolution_m': metres,
                    'rgb_seed_classes': list(SEED_CLASSES), 'slope_limit_degrees': SLOPE_LIMIT,
                    'region_name': job['region_name'], 'rgb_boundary_sha256': plan['boundary_sha256'],
                    'rgb_tiles': len(tiles), 'rgb_classified_polygons': segments, 'rgb_sam_masks': masks})
    return build_knowledge(spec, log=lambda message: progress(message, 93)).to_dict()
