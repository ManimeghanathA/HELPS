from pathlib import Path

import geopandas as gpd

from scripts.processing.clearance_analysis import (
    extract_clearance_cores,
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
    / "bhadra_clearance_analysis.gpkg"
)

CLEARANCE_RADIUS_M = 15.0


print("=" * 80)
print("HELPSs — CLEARANCE / NARROW-NECK ANALYSIS")
print("=" * 80)

print(f"Input             : {INPUT_PATH}")
print(f"Clearance radius  : {CLEARANCE_RADIUS_M:.1f} m")
print(f"Equivalent width  : {CLEARANCE_RADIUS_M * 2:.1f} m")
print()


# ============================================================
# LOAD CURRENT CANDIDATES
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
# RUN CLEARANCE ANALYSIS
# ============================================================

core_records = []

candidate_results = []

disappeared = 0
single_core = 0
split_candidates = 0


for _, row in candidates.iterrows():

    candidate_id = row["candidate_id"]
    polygon = row.geometry

    cores = extract_clearance_cores(
        polygon,
        clearance_radius_m=CLEARANCE_RADIUS_M,
    )

    core_count = len(cores)

    if core_count == 0:
        disappeared += 1

    elif core_count == 1:
        single_core += 1

    else:
        split_candidates += 1

    candidate_results.append(
        {
            "candidate_id": candidate_id,
            "core_count": core_count,
            "split_by_clearance": core_count > 1,
            "survives_clearance": core_count > 0,
            "geometry": polygon,
        }
    )

    for core_number, core in enumerate(
        cores,
        start=1,
    ):

        core_records.append(
            {
                "candidate_id": candidate_id,
                "core_id": (
                    f"{candidate_id}_CORE_{core_number:03d}"
                ),
                "core_number": core_number,
                "core_area_m2": core.area,
                "geometry": core,
            }
        )


# ============================================================
# BUILD OUTPUT GEODATAFRAMES
# ============================================================

candidate_audit = gpd.GeoDataFrame(
    candidate_results,
    geometry="geometry",
    crs=candidates.crs,
)

clearance_cores = gpd.GeoDataFrame(
    core_records,
    geometry="geometry",
    crs=candidates.crs,
)


# ============================================================
# SUMMARY
# ============================================================

total_candidates = len(candidates)
total_cores = len(clearance_cores)

surviving_candidates = (
    single_core
    + split_candidates
)


print()
print("=" * 80)
print("CLEARANCE ANALYSIS RESULT")
print("=" * 80)

print(
    f"Input candidates              : "
    f"{total_candidates:,}"
)

print(
    f"Disappear completely          : "
    f"{disappeared:,}"
)

print(
    f"Remain as one clearance core  : "
    f"{single_core:,}"
)

print(
    f"Split into multiple cores     : "
    f"{split_candidates:,}"
)

print()

print(
    f"Candidates surviving clearance: "
    f"{surviving_candidates:,}"
)

print(
    f"Total clearance cores         : "
    f"{total_cores:,}"
)


if total_candidates > 0:

    print()

    print(
        f"Disappear rate                : "
        f"{disappeared / total_candidates * 100:.2f}%"
    )

    print(
        f"Split rate                    : "
        f"{split_candidates / total_candidates * 100:.2f}%"
    )


# ============================================================
# CORE COUNT DISTRIBUTION
# ============================================================

if not candidate_audit.empty:

    print()
    print("=" * 80)
    print("CORE COUNT DISTRIBUTION")
    print("=" * 80)

    distribution = (
        candidate_audit["core_count"]
        .value_counts()
        .sort_index()
    )

    for core_count, count in distribution.items():

        print(
            f"{core_count:>3} cores : "
            f"{count:>6,} candidates"
        )


# ============================================================
# CORE AREA STATISTICS
# ============================================================

if not clearance_cores.empty:

    print()
    print("=" * 80)
    print("CLEARANCE CORE AREA STATISTICS")
    print("=" * 80)

    print(
        f"Minimum : "
        f"{clearance_cores['core_area_m2'].min():.2f} m²"
    )

    print(
        f"Median  : "
        f"{clearance_cores['core_area_m2'].median():.2f} m²"
    )

    print(
        f"Mean    : "
        f"{clearance_cores['core_area_m2'].mean():.2f} m²"
    )

    print(
        f"Maximum : "
        f"{clearance_cores['core_area_m2'].max():.2f} m²"
    )


# ============================================================
# SAVE
# ============================================================

if OUTPUT_PATH.exists():
    OUTPUT_PATH.unlink()


candidate_audit.to_file(
    OUTPUT_PATH,
    layer="candidate_clearance_audit",
    driver="GPKG",
)


if not clearance_cores.empty:

    clearance_cores.to_file(
        OUTPUT_PATH,
        layer="clearance_cores",
        driver="GPKG",
    )


print()
print("=" * 80)
print("CLEARANCE ANALYSIS COMPLETE")
print("=" * 80)

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print()
print("Layers:")
print(
    "  candidate_clearance_audit = "
    "original candidates + core counts"
)

print(
    "  clearance_cores          = "
    "15 m inward clearance cores"
)

print()
print(
    "NOTE: Clearance cores are analytical geometries."
)

print(
    "They do NOT yet replace the original candidate polygons."
)

print("=" * 80)