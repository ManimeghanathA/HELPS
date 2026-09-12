"""Validate AOIs and locate inputs by geometry, never by display name."""
import hashlib
from datetime import date
from pathlib import Path

import geopandas as gpd
import shapely

ROOT = Path(__file__).resolve().parents[2]


def data_directory(path):
    """Keep active data and sibling archives consistent for future runs too."""
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    base = ROOT/'data'
    if path.is_relative_to(base):
        for directory in [path, *path.parents]:
            if not directory.is_relative_to(base):
                break
            if 'archive' not in directory.relative_to(base).parts:
                (directory/'archive').mkdir(exist_ok=True)
    else:
        (path/'archive').mkdir(exist_ok=True)
    return path


def load_aoi(path):
    aoi = gpd.read_file(path)
    if aoi.empty or aoi.crs is None:
        raise ValueError('AOI must contain geometry and a coordinate reference system.')
    if not aoi.geometry.geom_type.isin(['Polygon', 'MultiPolygon']).all():
        raise ValueError('AOI must contain only Polygon or MultiPolygon features.')
    if aoi.geometry.isna().any() or aoi.geometry.is_empty.any() or not aoi.is_valid.all():
        raise ValueError('AOI contains empty or invalid geometry; repair it before running.')
    aoi = aoi.to_crs(4326)
    west, south, east, north = aoi.total_bounds
    if not (-180 <= west < east <= 180 and -80 <= south < north <= 84):
        raise ValueError('AOI must be within longitude bounds and the UTM latitude range.')
    if east - west > 6 or north - south > 6:
        raise ValueError('Use a regional AOI spanning at most 6 degrees in either direction.')
    return gpd.GeoDataFrame(geometry=[aoi.geometry.union_all()], crs=4326)


def cache_key(aoi, observation_date):
    parsed = date.fromisoformat(observation_date)
    if parsed.isoformat() != observation_date:
        raise ValueError('Date must use YYYY-MM-DD.')
    geom = shapely.normalize(aoi.to_crs(4326).geometry.union_all())
    return hashlib.sha256(geom.wkb + observation_date.encode()).hexdigest()[:24]


def legacy_inputs(aoi, observation_date):
    source = ROOT / 'data/raw/Bhadra/bhadra_entire_region.geojson'
    if observation_date != '2026-06-01' or not source.exists():
        return None
    if not aoi.geometry.union_all().equals(load_aoi(source).geometry.union_all()):
        return None
    base = ROOT / 'data/processed/Bhadra'
    imagery = base / 'sentinel2/2026-06-01'
    paths = {'spectral': imagery/'bhadra_spectral.tif', 'scl': imagery/'bhadra_scl.tif',
             'osm': base/'osm/bhadra_osm_context.gpkg',
             'overture': base/'buildings/bhadra_overture_buildings.geojson'}
    return paths
