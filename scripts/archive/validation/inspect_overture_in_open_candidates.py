from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape


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

OPEN_MASK_PATH = (
    BASE_DIR
    / "bhadra_possible_open_mask_v2.tif"
)

BUILDINGS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "buildings"
    / "bhadra_overture_buildings.geojson"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "buildings"
    / "bhadra_overture_buildings_in_possible_open.geojson"
)


print("=" * 80)
print("HELPSs — OVERTURE BUILDINGS INSIDE SENTINEL POSSIBLE-OPEN LAND")
print("=" * 80)


# ============================================================
# READ POSSIBLE-OPEN MASK
# ============================================================

with rasterio.open(OPEN_MASK_PATH) as src:

    state = src.read(1)

    transform = src.transform
    raster_crs = src.crs


open_binary = (
    state == 1
).astype(np.uint8)


# ============================================================
# POLYGONIZE ONLY POSSIBLE-OPEN REGIONS
# ============================================================

open_geometries = []

for geom, value in shapes(
    open_binary,
    mask=(open_binary == 1),
    transform=transform,
):

    if int(value) == 1:
        open_geometries.append(
            shape(geom)
        )


open_gdf = gpd.GeoDataFrame(
    geometry=open_geometries,
    crs=raster_crs,
)


print(
    f"Possible-open components : "
    f"{len(open_gdf):,}"
)


# Merge to speed up intersection
open_union = open_gdf.geometry.union_all()


# ============================================================
# READ OVERTURE BUILDINGS
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


print(
    f"Total Overture buildings : "
    f"{len(buildings):,}"
)


# ============================================================
# INTERSECT WITH POSSIBLE-OPEN LAND
# ============================================================

intersects = buildings.geometry.intersects(
    open_union
)


relevant = buildings[
    intersects
].copy()


print(
    f"Buildings intersecting "
    f"possible-open land      : "
    f"{len(relevant):,}"
)


# ============================================================
# FOOTPRINT AREA
# ============================================================

relevant["footprint_area_m2"] = (
    relevant.geometry.area
)


# ============================================================
# SAVE
# ============================================================

relevant.to_file(
    OUTPUT_PATH,
    driver="GeoJSON",
)


# ============================================================
# BASIC STATISTICS
# ============================================================

print()
print("=" * 80)
print("RELEVANT BUILDING STATISTICS")
print("=" * 80)


if len(relevant) > 0:

    print(
        f"Footprint area min    : "
        f"{relevant['footprint_area_m2'].min():.2f} m²"
    )

    print(
        f"Footprint area median : "
        f"{relevant['footprint_area_m2'].median():.2f} m²"
    )

    print(
        f"Footprint area mean   : "
        f"{relevant['footprint_area_m2'].mean():.2f} m²"
    )

    print(
        f"Footprint area max    : "
        f"{relevant['footprint_area_m2'].max():.2f} m²"
    )


# ============================================================
# ATTRIBUTE INSPECTION
# ============================================================

print()
print("=" * 80)
print("AVAILABLE ATTRIBUTE COLUMNS")
print("=" * 80)

for col in relevant.columns:
    if col != "geometry":
        print(f"  - {col}")


# ============================================================
# SEARCH FOR CONFIDENCE / SOURCE COLUMNS
# ============================================================

interesting_columns = []

for col in relevant.columns:

    lower = col.lower()

    if (
        "confidence" in lower
        or "source" in lower
        or "provider" in lower
    ):
        interesting_columns.append(
            col
        )


print()
print("=" * 80)
print("SOURCE / CONFIDENCE FIELDS")
print("=" * 80)


if not interesting_columns:

    print(
        "No obvious source/confidence columns "
        "found in flattened GeoJSON."
    )

else:

    for col in interesting_columns:

        print()
        print(f"Column: {col}")

        values = (
            relevant[col]
            .dropna()
            .astype(str)
            .value_counts()
            .head(30)
        )

        for value, count in values.items():

            print(
                f"  {value:<50} "
                f"{count:,}"
            )


print()
print("=" * 80)
print("OUTPUT")
print("=" * 80)

print(
    f"Saved relevant buildings:\n"
    f"{OUTPUT_PATH}"
)

print("=" * 80)