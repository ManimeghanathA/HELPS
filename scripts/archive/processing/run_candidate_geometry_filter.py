from pathlib import Path

import geopandas as gpd

from scripts.processing.candidate_geometry_filter import (
    measure_candidate_geometry,
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

INPUT_PATH = (
    BASE_DIR
    / "bhadra_open_components_buildings_removed.gpkg"
)

OUTPUT_PATH = (
    BASE_DIR
    / "bhadra_candidate_open_lands.gpkg"
)


MIN_AREA_M2 = 900.0
MIN_LENGTH_M = 30.0
MIN_WIDTH_M = 30.0


print("=" * 80)
print("HELPSs — CANDIDATE OPEN-LAND GEOMETRY FILTER")
print("=" * 80)

print(f"Input              : {INPUT_PATH}")
print(f"Minimum area       : {MIN_AREA_M2:.0f} m²")
print(f"Minimum length     : {MIN_LENGTH_M:.0f} m")
print(f"Minimum width      : {MIN_WIDTH_M:.0f} m")
print()


# ============================================================
# LOAD BUILDING-CLEANED OPEN LAND
# ============================================================

gdf = gpd.read_file(
    INPUT_PATH,
    layer="building_cleaned_open_land",
)

print(
    f"Fragments loaded   : "
    f"{len(gdf):,}"
)


# ============================================================
# MEASURE GEOMETRY
# ============================================================

measurements = gdf.geometry.apply(
    measure_candidate_geometry
)

gdf["area_m2"] = measurements.apply(
    lambda x: x["area_m2"]
)

gdf["length_m"] = measurements.apply(
    lambda x: x["length_m"]
)

gdf["width_m"] = measurements.apply(
    lambda x: x["width_m"]
)


# ============================================================
# INDIVIDUAL GATE FLAGS
# ============================================================

gdf["passes_area"] = (
    gdf["area_m2"]
    >= MIN_AREA_M2
)

gdf["passes_length"] = (
    gdf["length_m"]
    >= MIN_LENGTH_M
)

gdf["passes_width"] = (
    gdf["width_m"]
    >= MIN_WIDTH_M
)


gdf["passes_geometry_gate"] = (
    gdf["passes_area"]
    & gdf["passes_length"]
    & gdf["passes_width"]
)


# ============================================================
# EXTRACT CANDIDATES
# ============================================================

candidates = gdf[
    gdf["passes_geometry_gate"]
].copy()

candidates = candidates.reset_index(
    drop=True
)

candidates["candidate_id"] = [
    f"BHADRA_{DATE.replace('-', '')}_{i:06d}"
    for i in range(
        1,
        len(candidates) + 1,
    )
]


# ============================================================
# STATISTICS
# ============================================================

total = len(gdf)

failed_area = (
    ~gdf["passes_area"]
).sum()

failed_length = (
    ~gdf["passes_length"]
).sum()

failed_width = (
    ~gdf["passes_width"]
).sum()

passed = len(candidates)


input_area_km2 = (
    gdf.geometry.area.sum()
    / 1_000_000
)

candidate_area_km2 = (
    candidates.geometry.area.sum()
    / 1_000_000
)


print()
print("=" * 80)
print("GEOMETRY FILTER RESULT")
print("=" * 80)

print(
    f"Input fragments           : "
    f"{total:,}"
)

print(
    f"Fail area < 900 m²        : "
    f"{failed_area:,}"
)

print(
    f"Fail length < 30 m        : "
    f"{failed_length:,}"
)

print(
    f"Fail width < 30 m         : "
    f"{failed_width:,}"
)

print()

print(
    f"PASS ALL THREE            : "
    f"{passed:,}"
)

print(
    f"Rejected                  : "
    f"{total - passed:,}"
)

if total > 0:

    print(
        f"Candidate retention       : "
        f"{passed / total * 100:.2f}%"
    )

print()

print(
    f"Input open area           : "
    f"{input_area_km2:.3f} km²"
)

print(
    f"Candidate area            : "
    f"{candidate_area_km2:.3f} km²"
)


# ============================================================
# CANDIDATE SIZE STATISTICS
# ============================================================

if len(candidates) > 0:

    print()
    print("=" * 80)
    print("SURVIVING CANDIDATE STATISTICS")
    print("=" * 80)

    print(
        f"Median area               : "
        f"{candidates['area_m2'].median():.2f} m²"
    )

    print(
        f"Median length             : "
        f"{candidates['length_m'].median():.2f} m"
    )

    print(
        f"Median width              : "
        f"{candidates['width_m'].median():.2f} m"
    )

    print(
        f"Largest candidate         : "
        f"{candidates['area_m2'].max() / 1_000_000:.3f} km²"
    )


# ============================================================
# SAVE BOTH AUDIT + FINAL CANDIDATES
# ============================================================

if OUTPUT_PATH.exists():
    OUTPUT_PATH.unlink()


gdf.to_file(
    OUTPUT_PATH,
    layer="geometry_evaluated",
    driver="GPKG",
)


candidates.to_file(
    OUTPUT_PATH,
    layer="candidate_open_lands",
    driver="GPKG",
)


print()
print("=" * 80)
print("GEOMETRY FILTER COMPLETE")
print("=" * 80)

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print()
print("Layers:")
print("  geometry_evaluated   = all fragments + measurements")
print("  candidate_open_lands = fragments passing all thresholds")

print("=" * 80)