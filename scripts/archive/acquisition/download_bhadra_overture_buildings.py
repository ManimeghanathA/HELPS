from pathlib import Path
import subprocess

import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

AOI_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_entire_region.geojson"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "buildings"
)

RAW_OUTPUT = (
    OUTPUT_DIR
    / "bhadra_overture_buildings_bbox.geojson"
)

CLIPPED_OUTPUT = (
    OUTPUT_DIR
    / "bhadra_overture_buildings.geojson"
)


print("=" * 76)
print("HELPSs — OVERTURE BUILDING ACQUISITION")
print("=" * 76)


if not AOI_PATH.exists():
    raise FileNotFoundError(
        f"AOI not found:\n{AOI_PATH}"
    )


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# LOAD AOI
# ============================================================

aoi = gpd.read_file(
    AOI_PATH
)

if aoi.crs is None:
    raise ValueError(
        "AOI has no CRS."
    )

aoi_wgs84 = aoi.to_crs(
    4326
)


minx, miny, maxx, maxy = (
    aoi_wgs84.total_bounds
)


bbox = (
    f"{minx},{miny},{maxx},{maxy}"
)


print(f"AOI        : {AOI_PATH}")
print(f"BBox       : {bbox}")
print(f"Raw output : {RAW_OUTPUT}")
print()


# ============================================================
# OVERTURE DOWNLOAD
# ============================================================

command = [
    "overturemaps",
    "download",
    f"--bbox={bbox}",
    "-f",
    "geojson",
    "--type=building",
    "-o",
    str(RAW_OUTPUT),
]


print("Running Overture download...")
print()


subprocess.run(
    command,
    check=True,
)


# ============================================================
# LOAD DOWNLOADED BUILDINGS
# ============================================================

buildings = gpd.read_file(
    RAW_OUTPUT
)


print()
print(
    f"Downloaded bbox buildings : "
    f"{len(buildings):,}"
)


if buildings.empty:
    raise RuntimeError(
        "Overture returned zero buildings."
    )


# ============================================================
# CLIP TO EXACT BHADRA AOI
# ============================================================

if buildings.crs is None:

    buildings = buildings.set_crs(
        4326
    )


buildings = buildings.to_crs(
    aoi_wgs84.crs
)


clipped = gpd.clip(
    buildings,
    aoi_wgs84,
)


clipped = clipped[
    clipped.geometry.notna()
    & ~clipped.geometry.is_empty
].copy()


print(
    f"Buildings inside Bhadra   : "
    f"{len(clipped):,}"
)


# ============================================================
# SAVE
# ============================================================

clipped.to_file(
    CLIPPED_OUTPUT,
    driver="GeoJSON",
)


print()
print("=" * 76)
print("OVERTURE BUILDING ACQUISITION COMPLETE")
print("=" * 76)

print(
    f"Saved:\n{CLIPPED_OUTPUT}"
)

print("=" * 76)