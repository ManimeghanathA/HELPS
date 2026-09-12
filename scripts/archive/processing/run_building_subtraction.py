from pathlib import Path

import geopandas as gpd
import pandas as pd

from scripts.processing.building_subtraction import (
    subtract_buildings,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATE = "2026-06-01"

SENTINEL_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "sentinel2"
    / DATE
)

OPEN_COMPONENTS_PATH = (
    SENTINEL_DIR
    / "bhadra_sentinel_open_components.gpkg"
)

OSM_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "osm"
    / "bhadra_osm_context.gpkg"
)

OVERTURE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "buildings"
    / "bhadra_overture_buildings_in_possible_open.geojson"
)

OUTPUT_PATH = (
    SENTINEL_DIR
    / "bhadra_open_components_buildings_removed.gpkg"
)


print("=" * 80)
print("HELPSs — BUILDING SUBTRACTION")
print("=" * 80)


# ============================================================
# LOAD SENTINEL OPEN COMPONENTS
# ============================================================

open_land = gpd.read_file(
    OPEN_COMPONENTS_PATH,
    layer="sentinel_open_components",
)


print(
    f"Sentinel open components : "
    f"{len(open_land):,}"
)

before_area_m2 = (
    open_land.geometry.area.sum()
)

print(
    f"Sentinel open area       : "
    f"{before_area_m2 / 1_000_000:.3f} km²"
)


# ============================================================
# LOAD OSM BUILDINGS ONLY
# ============================================================

osm_buildings = gpd.read_file(
    OSM_PATH,
    layer="buildings",
)

if osm_buildings.crs != open_land.crs:

    osm_buildings = osm_buildings.to_crs(
        open_land.crs
    )


osm_buildings = osm_buildings[
    osm_buildings.geometry.notna()
    & ~osm_buildings.geometry.is_empty
].copy()


print(
    f"OSM buildings            : "
    f"{len(osm_buildings):,}"
)


# ============================================================
# LOAD OVERTURE BUILDINGS
# ============================================================

overture_buildings = gpd.read_file(
    OVERTURE_PATH
)

if overture_buildings.crs != open_land.crs:

    overture_buildings = overture_buildings.to_crs(
        open_land.crs
    )


overture_buildings = overture_buildings[
    overture_buildings.geometry.notna()
    & ~overture_buildings.geometry.is_empty
].copy()


print(
    f"Overture buildings       : "
    f"{len(overture_buildings):,}"
)


# ============================================================
# COMBINE BUILDING SOURCES
# ============================================================

osm_for_merge = osm_buildings[
    ["geometry"]
].copy()

osm_for_merge["building_source"] = "OSM"


overture_for_merge = overture_buildings[
    ["geometry"]
].copy()

overture_for_merge["building_source"] = "Overture"


all_buildings = gpd.GeoDataFrame(
    pd.concat(
        [
            osm_for_merge,
            overture_for_merge,
        ],
        ignore_index=True,
    ),
    geometry="geometry",
    crs=open_land.crs,
)


print(
    f"Combined building records: "
    f"{len(all_buildings):,}"
)


# ============================================================
# SUBTRACT BUILDINGS
# ============================================================

print()
print("Subtracting building footprints...")
print()


cleaned = subtract_buildings(
    open_land,
    all_buildings,
)


# ============================================================
# REBUILD IDS + GEOMETRY ATTRIBUTES
# ============================================================

cleaned = cleaned.reset_index(
    drop=True
)

cleaned["open_fragment_id"] = (
    range(
        1,
        len(cleaned) + 1,
    )
)

cleaned["area_m2"] = (
    cleaned.geometry.area
)

cleaned["area_km2"] = (
    cleaned["area_m2"]
    / 1_000_000
)


# ============================================================
# STATISTICS
# ============================================================

after_area_m2 = (
    cleaned.geometry.area.sum()
)

removed_area_m2 = (
    before_area_m2
    - after_area_m2
)


print("=" * 80)
print("BUILDING SUBTRACTION RESULT")
print("=" * 80)

print(
    f"Components before        : "
    f"{len(open_land):,}"
)

print(
    f"Fragments after          : "
    f"{len(cleaned):,}"
)

print()

print(
    f"Open area before         : "
    f"{before_area_m2 / 1_000_000:.3f} km²"
)

print(
    f"Building area removed    : "
    f"{removed_area_m2 / 1_000_000:.3f} km²"
)

print(
    f"Open area remaining      : "
    f"{after_area_m2 / 1_000_000:.3f} km²"
)

if before_area_m2 > 0:

    print(
        f"Fraction removed         : "
        f"{removed_area_m2 / before_area_m2 * 100:.2f}%"
    )


# ============================================================
# SAVE
# ============================================================

cleaned.to_file(
    OUTPUT_PATH,
    layer="building_cleaned_open_land",
    driver="GPKG",
)


print()
print("=" * 80)
print("BUILDING SUBTRACTION COMPLETE")
print("=" * 80)

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print()
print(
    "These polygons have Sentinel-open surface evidence "
    "with OSM + Overture building footprints removed."
)

print(
    "Geometry size filtering has NOT been applied yet."
)

print("=" * 80)