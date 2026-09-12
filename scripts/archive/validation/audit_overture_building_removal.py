from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds


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

OSM_EMPTY_PATH = (
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


print("=" * 80)
print("HELPSs — OVERTURE BUILDING REMOVAL AUDIT")
print("=" * 80)


# ============================================================
# LOAD OSM-REFINED EMPTY MASK
# ============================================================

with rasterio.open(OSM_EMPTY_PATH) as src:

    empty = src.read(1)
    transform = src.transform
    crs = src.crs

    height = src.height
    width = src.width


# ============================================================
# LOAD BUILDINGS
# ============================================================

buildings = gpd.read_file(
    BUILDINGS_PATH
)

if buildings.crs is None:
    buildings = buildings.set_crs(4326)

buildings = buildings.to_crs(crs)

buildings = buildings[
    buildings.geometry.notna()
    & ~buildings.geometry.is_empty
].copy()


print(
    f"Buildings intersecting raw Sentinel possible-open : "
    f"{len(buildings):,}"
)


# ============================================================
# AUDIT EACH BUILDING
# ============================================================

buildings_touching_osm_empty = 0
buildings_removing_pixels = 0

total_building_pixel_hits = 0


with rasterio.open(OSM_EMPTY_PATH) as src:

    for geom in buildings.geometry:

        minx, miny, maxx, maxy = geom.bounds

        window = from_bounds(
            minx,
            miny,
            maxx,
            maxy,
            transform=src.transform,
        )

        window = window.round_offsets().round_lengths()

        # Clip window to raster
        row_off = max(0, int(window.row_off))
        col_off = max(0, int(window.col_off))

        row_end = min(
            height,
            row_off + max(1, int(window.height))
        )

        col_end = min(
            width,
            col_off + max(1, int(window.width))
        )

        if row_end <= row_off or col_end <= col_off:
            continue

        local_window = rasterio.windows.Window(
            col_off,
            row_off,
            col_end - col_off,
            row_end - row_off,
        )

        local_empty = src.read(
            1,
            window=local_window,
        )

        local_transform = src.window_transform(
            local_window
        )

        footprint_mask = geometry_mask(
            [geom],
            out_shape=local_empty.shape,
            transform=local_transform,
            invert=True,
            all_touched=True,
        )

        touched_empty = (
            footprint_mask
            & (local_empty == 1)
        )

        count = np.count_nonzero(
            touched_empty
        )

        if count > 0:

            buildings_touching_osm_empty += 1
            buildings_removing_pixels += 1

            total_building_pixel_hits += count


# ============================================================
# REPORT
# ============================================================

print()
print("=" * 80)
print("AUDIT RESULTS")
print("=" * 80)

print(
    f"Buildings intersecting raw Sentinel open land : "
    f"{len(buildings):,}"
)

print(
    f"Buildings touching OSM-refined empty land     : "
    f"{buildings_touching_osm_empty:,}"
)

print(
    f"Buildings capable of removing >=1 pixel       : "
    f"{buildings_removing_pixels:,}"
)

print()

print(
    f"Building-to-empty pixel hits "
    f"(before overlap deduplication) : "
    f"{total_building_pixel_hits:,}"
)

print()

print(
    "NOTE:"
)

print(
    "  Pixel hits can exceed final removed pixels because "
    "multiple buildings may touch the same 10 m pixel."
)

print("=" * 80)