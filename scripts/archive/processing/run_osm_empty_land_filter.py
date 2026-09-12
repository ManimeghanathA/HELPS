from pathlib import Path

import numpy as np
import rasterio

from scripts.processing.osm_obstacle_filter import (
    apply_obstacle_mask,
    build_osm_obstacle_mask,
)


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


POSSIBLE_OPEN_PATH = (
    BASE_DIR
    / "bhadra_possible_open_mask_v2.tif"
)


OSM_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "osm"
    / "bhadra_osm_context.gpkg"
)


OBSTACLE_OUTPUT = (
    BASE_DIR
    / "bhadra_osm_obstacle_mask.tif"
)


EMPTY_OUTPUT = (
    BASE_DIR
    / "bhadra_empty_land_mask.tif"
)


print("=" * 76)
print("HELPSs — OSM EMPTY-LAND FILTER")
print("=" * 76)

print(f"Date       : {DATE}")
print(f"Possible   : {POSSIBLE_OPEN_PATH}")
print(f"OSM        : {OSM_PATH}")
print()


# ============================================================
# BUILD OSM OBSTACLE MASK
# ============================================================

obstacle_mask, statistics = (
    build_osm_obstacle_mask(
        OSM_PATH,
        POSSIBLE_OPEN_PATH,
    )
)


# ============================================================
# LOAD SENTINEL POSSIBLE-OPEN MASK
# ============================================================

with rasterio.open(
    POSSIBLE_OPEN_PATH
) as src:

    possible_open = src.read(
        1
    )

    profile = src.profile.copy()

    pixel_area_m2 = (
        abs(src.transform.a)
        * abs(src.transform.e)
    )


# ============================================================
# APPLY OSM OBSTACLES
# ============================================================

empty_land = apply_obstacle_mask(
    possible_open,
    obstacle_mask,
)


# ============================================================
# SAVE OBSTACLE MASK
# ============================================================

obstacle_profile = profile.copy()

obstacle_profile.update(
    dtype="uint8",
    count=1,
    nodata=0,
    compress="lzw",
)


with rasterio.open(
    OBSTACLE_OUTPUT,
    "w",
    **obstacle_profile,
) as dst:

    dst.write(
        obstacle_mask,
        1,
    )


# ============================================================
# SAVE EMPTY LAND MASK
# ============================================================

empty_profile = profile.copy()

empty_profile.update(
    dtype="uint8",
    count=1,
    nodata=255,
    compress="lzw",
)


with rasterio.open(
    EMPTY_OUTPUT,
    "w",
    **empty_profile,
) as dst:

    dst.write(
        empty_land,
        1,
    )


# ============================================================
# STATISTICS
# ============================================================

before_pixels = np.count_nonzero(
    possible_open == 1
)

after_pixels = np.count_nonzero(
    empty_land == 1
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

after_area_km2 = (
    after_pixels
    * pixel_area_m2
    / 1_000_000
)

removed_area_km2 = (
    removed_pixels
    * pixel_area_m2
    / 1_000_000
)


print("=" * 76)
print("OSM OBSTACLE CONTRIBUTION")
print("=" * 76)

for name, info in statistics.items():

    print(
        f"{name:<12} "
        f"{info['pixels']:>10,} px   "
        f"{info['area_km2']:>8.3f} km²"
    )


print()
print("=" * 76)
print("EMPTY-LAND RESULT")
print("=" * 76)

print(
    f"Possible-open before OSM : "
    f"{before_pixels:,} pixels "
    f"({before_area_km2:.3f} km²)"
)

print(
    f"Removed by OSM           : "
    f"{removed_pixels:,} pixels "
    f"({removed_area_km2:.3f} km²)"
)

print(
    f"Remaining empty-land     : "
    f"{after_pixels:,} pixels "
    f"({after_area_km2:.3f} km²)"
)

print()

print(
    f"Obstacle mask :\n{OBSTACLE_OUTPUT}"
)

print()

print(
    f"Empty mask    :\n{EMPTY_OUTPUT}"
)

print("=" * 76)