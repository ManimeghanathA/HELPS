from pathlib import Path

import geopandas as gpd

from scripts.processing.maximum_clearance import (
    measure_maximum_clearance,
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
    / "bhadra_candidate_open_lands.gpkg"
)

OUTPUT_PATH = (
    BASE_DIR
    / "bhadra_candidate_max_clearance.gpkg"
)

TOLERANCE_M = 0.5


print("=" * 80)
print("HELPSs — MAXIMUM CLEARANCE ANALYSIS")
print("=" * 80)

print(f"Input     : {INPUT_PATH}")
print(f"Tolerance : {TOLERANCE_M:.2f} m")
print()


# ============================================================
# LOAD CANDIDATES
# ============================================================

candidates = gpd.read_file(
    INPUT_PATH,
    layer="candidate_open_lands",
)

print(
    f"Candidates loaded : "
    f"{len(candidates):,}"
)


# ============================================================
# MEASURE MAXIMUM CLEARANCE
# ============================================================

centers = []
radii = []
diameters = []


for index, row in candidates.iterrows():

    result = measure_maximum_clearance(
        row.geometry,
        tolerance_m=TOLERANCE_M,
    )

    centers.append(
        result["center"]
    )

    radii.append(
        result["radius_m"]
    )

    diameters.append(
        result["diameter_m"]
    )


candidates["max_clear_radius_m"] = radii
candidates["max_clear_diameter_m"] = diameters


# ============================================================
# BUILD CENTER POINT LAYER
# ============================================================

center_records = []

for i, row in candidates.iterrows():

    center = centers[i]

    if center is None:
        continue

    center_records.append(
        {
            "candidate_id": row["candidate_id"],
            "max_clear_radius_m": row["max_clear_radius_m"],
            "max_clear_diameter_m": row["max_clear_diameter_m"],
            "geometry": center,
        }
    )


centers_gdf = gpd.GeoDataFrame(
    center_records,
    geometry="geometry",
    crs=candidates.crs,
)


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 80)
print("MAXIMUM CLEARANCE RESULT")
print("=" * 80)

print(
    f"Minimum clear diameter : "
    f"{candidates['max_clear_diameter_m'].min():.2f} m"
)

print(
    f"Median clear diameter  : "
    f"{candidates['max_clear_diameter_m'].median():.2f} m"
)

print(
    f"Mean clear diameter    : "
    f"{candidates['max_clear_diameter_m'].mean():.2f} m"
)

print(
    f"Maximum clear diameter : "
    f"{candidates['max_clear_diameter_m'].max():.2f} m"
)


# ============================================================
# DISTRIBUTION
# ============================================================

print()
print("=" * 80)
print("CLEAR DIAMETER DISTRIBUTION")
print("=" * 80)

for threshold in [
    30,
    40,
    50,
    75,
    100,
    150,
    200,
]:

    count = (
        candidates["max_clear_diameter_m"]
        >= threshold
    ).sum()

    print(
        f">= {threshold:3d} m : "
        f"{count:>6,}"
    )


# ============================================================
# SAVE
# ============================================================

if OUTPUT_PATH.exists():
    OUTPUT_PATH.unlink()


candidates.to_file(
    OUTPUT_PATH,
    layer="candidates_with_clearance",
    driver="GPKG",
)


centers_gdf.to_file(
    OUTPUT_PATH,
    layer="maximum_clearance_centers",
    driver="GPKG",
)


print()
print("=" * 80)
print("MAXIMUM CLEARANCE COMPLETE")
print("=" * 80)

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print()
print("Layers:")
print(
    "  candidates_with_clearance"
)

print(
    "  maximum_clearance_centers"
)

print("=" * 80)