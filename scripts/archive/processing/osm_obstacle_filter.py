from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize


NOT_OPEN = 0
POSSIBLE_OPEN = 1
UNKNOWN = 255


# ============================================================
# ROAD CLASSES
# ============================================================

EXCLUDED_ROAD_CLASSES = {
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "unclassified",
    "service",
}


# ============================================================
# OBSTACLE POLICY
# ============================================================

# These are candidate-generation buffers.
# They are NOT helicopter clearance requirements.

BUILDING_BUFFER_M = 10.0
ROAD_BUFFER_M = 10.0
POWER_BUFFER_M = 10.0
MAN_MADE_BUFFER_M = 10.0
BARRIER_BUFFER_M = 5.0
WATER_BUFFER_M = 0.0


# ============================================================
# BASIC MASK SUBTRACTION
# ============================================================

def apply_obstacle_mask(
    possible_open,
    obstacle_mask,
):
    """
    Remove known permanent obstacles from Sentinel possible-open terrain.

    possible_open values:

        0   = NOT_OPEN
        1   = POSSIBLE_OPEN
        255 = UNKNOWN

    obstacle_mask values:

        0 = no mapped obstacle
        1 = obstacle present
    """

    if possible_open.shape != obstacle_mask.shape:
        raise ValueError(
            "Possible-open and obstacle masks must have identical shapes."
        )

    result = possible_open.copy()

    removable = (
        (result == POSSIBLE_OPEN)
        & (obstacle_mask == 1)
    )

    result[removable] = NOT_OPEN

    return result


# ============================================================
# GEOMETRY PREPARATION
# ============================================================

def _prepare_geometries(
    gdf,
    target_crs,
    buffer_m=0.0,
):
    if gdf.empty:
        return []

    gdf = gdf[
        gdf.geometry.notna()
        & ~gdf.geometry.is_empty
    ].copy()

    if gdf.empty:
        return []

    gdf = gdf.to_crs(
        target_crs
    )

    if buffer_m > 0:
        gdf["geometry"] = gdf.geometry.buffer(
            buffer_m
        )

    return [
        geom
        for geom in gdf.geometry
        if geom is not None
        and not geom.is_empty
    ]


# ============================================================
# RASTERIZATION
# ============================================================

def _rasterize_geometries(
    geometries,
    shape,
    transform,
):
    if not geometries:
        return np.zeros(
            shape,
            dtype=np.uint8,
        )

    return rasterize(
        (
            (geom, 1)
            for geom in geometries
        ),
        out_shape=shape,
        transform=transform,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )


# ============================================================
# BUILDINGS
# ============================================================

def _load_buildings(
    gpkg_path,
    target_crs,
):
    gdf = gpd.read_file(
        gpkg_path,
        layer="buildings",
    )

    return _prepare_geometries(
        gdf,
        target_crs,
        BUILDING_BUFFER_M,
    )


# ============================================================
# ROADS
# ============================================================

def _load_roads(
    gpkg_path,
    target_crs,
):
    gdf = gpd.read_file(
        gpkg_path,
        layer="roads",
    )

    if "highway" not in gdf.columns:
        return []

    gdf = gdf[
        gdf["highway"]
        .astype(str)
        .isin(EXCLUDED_ROAD_CLASSES)
    ].copy()

    return _prepare_geometries(
        gdf,
        target_crs,
        ROAD_BUFFER_M,
    )


# ============================================================
# POWER
# ============================================================

def _load_power(
    gpkg_path,
    target_crs,
):
    gdf = gpd.read_file(
        gpkg_path,
        layer="power",
    )

    return _prepare_geometries(
        gdf,
        target_crs,
        POWER_BUFFER_M,
    )


# ============================================================
# MAN-MADE
# ============================================================

def _load_man_made(
    gpkg_path,
    target_crs,
):
    gdf = gpd.read_file(
        gpkg_path,
        layer="man_made",
    )

    return _prepare_geometries(
        gdf,
        target_crs,
        MAN_MADE_BUFFER_M,
    )


# ============================================================
# BARRIERS
# ============================================================

def _load_barriers(
    gpkg_path,
    target_crs,
):
    gdf = gpd.read_file(
        gpkg_path,
        layer="barriers",
    )

    return _prepare_geometries(
        gdf,
        target_crs,
        BARRIER_BUFFER_M,
    )


# ============================================================
# WATER
# ============================================================

def _load_water(
    gpkg_path,
    target_crs,
):
    gdf = gpd.read_file(
        gpkg_path,
        layer="water_polygons",
    )

    return _prepare_geometries(
        gdf,
        target_crs,
        WATER_BUFFER_M,
    )


# ============================================================
# BUILD FULL OBSTACLE MASK
# ============================================================

def build_osm_obstacle_mask(
    gpkg_path,
    reference_raster_path,
):
    """
    Rasterize known OSM obstacles onto the Sentinel grid.

    Returns:

        obstacle_mask
        statistics
    """

    gpkg_path = Path(gpkg_path)
    reference_raster_path = Path(
        reference_raster_path
    )

    with rasterio.open(
        reference_raster_path
    ) as src:

        shape = (
            src.height,
            src.width,
        )

        transform = src.transform
        target_crs = src.crs

        pixel_area_m2 = (
            abs(src.transform.a)
            * abs(src.transform.e)
        )

    groups = {
        "buildings": _load_buildings(
            gpkg_path,
            target_crs,
        ),

        "roads": _load_roads(
            gpkg_path,
            target_crs,
        ),

        "power": _load_power(
            gpkg_path,
            target_crs,
        ),

        "man_made": _load_man_made(
            gpkg_path,
            target_crs,
        ),

        "barriers": _load_barriers(
            gpkg_path,
            target_crs,
        ),

        "water": _load_water(
            gpkg_path,
            target_crs,
        ),
    }

    combined = np.zeros(
        shape,
        dtype=np.uint8,
    )

    statistics = {}

    for group_name, geometries in groups.items():

        group_mask = _rasterize_geometries(
            geometries,
            shape,
            transform,
        )

        pixel_count = np.count_nonzero(
            group_mask == 1
        )

        area_km2 = (
            pixel_count
            * pixel_area_m2
            / 1_000_000
        )

        statistics[group_name] = {
            "pixels": int(pixel_count),
            "area_km2": float(area_km2),
        }

        combined[
            group_mask == 1
        ] = 1

    return (
        combined,
        statistics,
    )