from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATE = "2026-06-01"

BASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "sentinel2"
    / DATE
)

CURRENT_EMPTY_MASK = (
    BASE_DIR
    / "bhadra_empty_land_mask.tif"
)

BUILDINGS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "buildings"
    / "bhadra_overture_buildings_in_possible_open.geojson"
)

BUILDING_MASK_OUTPUT = (
    BASE_DIR
    / "bhadra_overture_building_mask.tif"
)

REFINED_EMPTY_OUTPUT = (
    BASE_DIR
    / "bhadra_empty_land_mask_osm_overture.tif"
)


NOT_OPEN = 0
EMPTY = 1
UNKNOWN = 255


print("=" * 80)
print("HELPSs — OVERTURE BUILDING FILTER")
print("=" * 80)

print(f"Input empty mask : {CURRENT_EMPTY_MASK}")
print(f"Buildings        : {BUILDINGS_PATH}")
print()


# ============================================================
# READ CURRENT EMPTY-LAND MASK
# ============================================================

with rasterio.open(CURRENT_EMPTY_MASK) as src:

    empty_state = src.read(1)

    profile = src.profile.copy()

    raster_crs = src.crs
    transform = src.transform

    raster_shape = (
        src.height,
        src.width,
    )

    pixel_area_m2 = (
        abs(src.transform.a)
        * abs(src.transform.e)
    )


# ============================================================
# READ RELEVANT OVERTURE BUILDINGS
# ============================================================

buildings = gpd.read_file(
    BUILDINGS_PATH
)

if buildings.crs is None:
    buildings = buildings.set_crs(
        4326
    )

buildings = buildings.to_crs(
    raster_crs
)

buildings = buildings[
    buildings.geometry.notna()
    & ~buildings.geometry.is_empty
].copy()


print(
    f"Relevant building footprints : "
    f"{len(buildings):,}"
)


# ============================================================
# RASTERIZE BUILDINGS
# ============================================================

building_mask = rasterize(
    (
        (geom, 1)
        for geom in buildings.geometry
    ),
    out_shape=raster_shape,
    transform=transform,
    fill=0,
    dtype="uint8",

    # Conservative at 10 m:
    # any raster cell touched by a building footprint is marked.
    all_touched=True,
)


# ============================================================
# CALCULATE INTERSECTION WITH CURRENT EMPTY LAND
# ============================================================

building_pixels_total = np.count_nonzero(
    building_mask == 1
)

building_pixels_on_empty = np.count_nonzero(
    (building_mask == 1)
    & (empty_state == EMPTY)
)


# ============================================================
# APPLY BUILDING EXCLUSION
# ============================================================

refined_empty = empty_state.copy()

refined_empty[
    (building_mask == 1)
    & (refined_empty == EMPTY)
] = NOT_OPEN


# ============================================================
# SAVE BUILDING MASK
# ============================================================

building_profile = profile.copy()

building_profile.update(
    count=1,
    dtype="uint8",
    nodata=0,
    compress="lzw",
)

with rasterio.open(
    BUILDING_MASK_OUTPUT,
    "w",
    **building_profile,
) as dst:

    dst.write(
        building_mask,
        1,
    )


# ============================================================
# SAVE REFINED EMPTY-LAND MASK
# ============================================================

empty_profile = profile.copy()

empty_profile.update(
    count=1,
    dtype="uint8",
    nodata=UNKNOWN,
    compress="lzw",
)

with rasterio.open(
    REFINED_EMPTY_OUTPUT,
    "w",
    **empty_profile,
) as dst:

    dst.write(
        refined_empty,
        1,
    )


# ============================================================
# STATISTICS
# ============================================================

before_pixels = np.count_nonzero(
    empty_state == EMPTY
)

after_pixels = np.count_nonzero(
    refined_empty == EMPTY
)

removed_pixels = (
    before_pixels
    - after_pixels
)


before_area_km2 = (
    before_pixels
    * pixel_area_m2
    / 1_000_000
)

removed_area_km2 = (
    removed_pixels
    * pixel_area_m2
    / 1_000_000
)

after_area_km2 = (
    after_pixels
    * pixel_area_m2
    / 1_000_000
)


print()
print("=" * 80)
print("OVERTURE BUILDING FILTER SUMMARY")
print("=" * 80)

print(
    f"Building raster pixels total    : "
    f"{building_pixels_total:,}"
)

print(
    f"Building pixels on empty land   : "
    f"{building_pixels_on_empty:,}"
)

print()

print(
    f"Empty land before buildings     : "
    f"{before_pixels:,} px "
    f"({before_area_km2:.3f} km²)"
)

print(
    f"Removed by Overture buildings   : "
    f"{removed_pixels:,} px "
    f"({removed_area_km2:.3f} km²)"
)

print(
    f"Empty land after buildings      : "
    f"{after_pixels:,} px "
    f"({after_area_km2:.3f} km²)"
)

print()

if before_pixels > 0:

    print(
        f"Fraction removed from empty land: "
        f"{removed_pixels / before_pixels * 100:.2f}%"
    )


print()
print(
    f"Building mask:\n"
    f"{BUILDING_MASK_OUTPUT}"
)

print()

print(
    f"Refined empty mask:\n"
    f"{REFINED_EMPTY_OUTPUT}"
)

print("=" * 80)