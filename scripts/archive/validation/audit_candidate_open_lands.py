from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


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

CANDIDATE_PATH = (
    BASE_DIR
    / "bhadra_candidate_open_lands.gpkg"
)

OVERTURE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "buildings"
    / "bhadra_overture_buildings_in_possible_open.geojson"
)

OSM_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "osm"
    / "bhadra_osm_context.gpkg"
)


MIN_AREA_M2 = 900.0
MIN_LENGTH_M = 30.0
MIN_WIDTH_M = 30.0


print("=" * 84)
print("HELPSs — CANDIDATE OPEN-LAND DEEP AUDIT")
print("=" * 84)


# ============================================================
# LOAD CANDIDATES
# ============================================================

candidates = gpd.read_file(
    CANDIDATE_PATH,
    layer="candidate_open_lands",
)

print(f"Candidates loaded : {len(candidates):,}")
print(f"CRS               : {candidates.crs}")


# ============================================================
# 1. BASIC GEOMETRY VALIDITY
# ============================================================

print()
print("=" * 84)
print("1. GEOMETRY VALIDITY")
print("=" * 84)

null_geometry = candidates.geometry.isna().sum()
empty_geometry = candidates.geometry.is_empty.sum()
invalid_geometry = (~candidates.geometry.is_valid).sum()

geometry_types = (
    candidates.geometry.geom_type
    .value_counts()
)

print(f"Null geometries    : {null_geometry:,}")
print(f"Empty geometries   : {empty_geometry:,}")
print(f"Invalid geometries : {invalid_geometry:,}")

print()
print("Geometry types:")

for geom_type, count in geometry_types.items():
    print(f"  {geom_type:<20} {count:,}")


# ============================================================
# 2. ID CHECK
# ============================================================

print()
print("=" * 84)
print("2. CANDIDATE ID CHECK")
print("=" * 84)

duplicate_ids = (
    candidates["candidate_id"]
    .duplicated()
    .sum()
)

missing_ids = (
    candidates["candidate_id"]
    .isna()
    .sum()
)

print(f"Missing IDs   : {missing_ids:,}")
print(f"Duplicate IDs : {duplicate_ids:,}")


# ============================================================
# 3. THRESHOLD INVARIANTS
# ============================================================

print()
print("=" * 84)
print("3. GEOMETRY GATE INVARIANTS")
print("=" * 84)

fail_area = (
    candidates["area_m2"] < MIN_AREA_M2
).sum()

fail_length = (
    candidates["length_m"] < MIN_LENGTH_M
).sum()

fail_width = (
    candidates["width_m"] < MIN_WIDTH_M
).sum()

print(f"Area failures   : {fail_area:,}")
print(f"Length failures : {fail_length:,}")
print(f"Width failures  : {fail_width:,}")

print()

print(
    f"Minimum stored area   : "
    f"{candidates['area_m2'].min():.2f} m²"
)

print(
    f"Minimum stored length : "
    f"{candidates['length_m'].min():.2f} m"
)

print(
    f"Minimum stored width  : "
    f"{candidates['width_m'].min():.2f} m"
)


# ============================================================
# 4. RECOMPUTE AREA
# ============================================================

print()
print("=" * 84)
print("4. STORED AREA VS REAL GEOMETRY AREA")
print("=" * 84)

real_area = candidates.geometry.area

area_difference = np.abs(
    real_area
    - candidates["area_m2"]
)

print(
    f"Maximum area discrepancy : "
    f"{area_difference.max():.6f} m²"
)

print(
    f"Mean area discrepancy    : "
    f"{area_difference.mean():.6f} m²"
)


# ============================================================
# 5. CANDIDATE SIZE DISTRIBUTION
# ============================================================

print()
print("=" * 84)
print("5. CANDIDATE SIZE DISTRIBUTION")
print("=" * 84)

for percentile in [
    1,
    5,
    10,
    25,
    50,
    75,
    90,
    95,
    99,
]:

    area = np.percentile(
        candidates["area_m2"],
        percentile,
    )

    length = np.percentile(
        candidates["length_m"],
        percentile,
    )

    width = np.percentile(
        candidates["width_m"],
        percentile,
    )

    print(
        f"P{percentile:02d} | "
        f"area={area:10.2f} m² | "
        f"length={length:8.2f} m | "
        f"width={width:8.2f} m"
    )


# ============================================================
# 6. VERY LARGE CANDIDATES
# ============================================================

print()
print("=" * 84)
print("6. VERY LARGE CANDIDATES")
print("=" * 84)

largest = (
    candidates[
        [
            "candidate_id",
            "area_m2",
            "length_m",
            "width_m",
        ]
    ]
    .sort_values(
        "area_m2",
        ascending=False,
    )
    .head(20)
)

print(
    largest.to_string(
        index=False
    )
)


# ============================================================
# 7. HOLES / INTERIOR RINGS
# ============================================================

print()
print("=" * 84)
print("7. POLYGON HOLES")
print("=" * 84)


def count_holes(geometry):

    if geometry.geom_type == "Polygon":
        return len(
            geometry.interiors
        )

    if geometry.geom_type == "MultiPolygon":
        return sum(
            len(part.interiors)
            for part in geometry.geoms
        )

    return 0


candidates["hole_count"] = (
    candidates.geometry.apply(
        count_holes
    )
)

candidates_with_holes = (
    candidates["hole_count"] > 0
).sum()

total_holes = (
    candidates["hole_count"].sum()
)

print(
    f"Candidates containing holes : "
    f"{candidates_with_holes:,}"
)

print(
    f"Total interior holes        : "
    f"{total_holes:,}"
)


# ============================================================
# 8. LOAD BUILDINGS
# ============================================================

print()
print("=" * 84)
print("8. RESIDUAL BUILDING OVERLAP")
print("=" * 84)

overture = gpd.read_file(
    OVERTURE_PATH
)

osm = gpd.read_file(
    OSM_PATH,
    layer="buildings",
)


if overture.crs != candidates.crs:
    overture = overture.to_crs(
        candidates.crs
    )

if osm.crs != candidates.crs:
    osm = osm.to_crs(
        candidates.crs
    )


overture = overture[
    overture.geometry.notna()
    & ~overture.geometry.is_empty
].copy()

osm = osm[
    osm.geometry.notna()
    & ~osm.geometry.is_empty
].copy()


building_union = (
    pd.concat(
        [
            overture[["geometry"]],
            osm[["geometry"]],
        ],
        ignore_index=True,
    )
)


building_union = gpd.GeoDataFrame(
    building_union,
    geometry="geometry",
    crs=candidates.crs,
).geometry.union_all()


# ============================================================
# CHECK CANDIDATE ↔ BUILDING INTERSECTIONS
# ============================================================

touching_buildings = (
    candidates.geometry.intersects(
        building_union
    )
)

overlap_areas = candidates.geometry.apply(
    lambda geom:
        geom.intersection(
            building_union
        ).area
)


positive_overlap = (
    overlap_areas > 1e-6
)


print(
    f"Candidates touching buildings      : "
    f"{touching_buildings.sum():,}"
)

print(
    f"Candidates with AREA overlap       : "
    f"{positive_overlap.sum():,}"
)

print(
    f"Total residual building overlap    : "
    f"{overlap_areas.sum():.6f} m²"
)


# ============================================================
# 9. INTERNAL CANDIDATE OVERLAP
# ============================================================

print()
print("=" * 84)
print("9. INTERNAL CANDIDATE OVERLAP")
print("=" * 84)

spatial_index = candidates.sindex

overlap_pairs = 0
positive_overlap_pairs = 0


for i, geom in enumerate(
    candidates.geometry
):

    possible = list(
        spatial_index.query(
            geom,
            predicate="intersects",
        )
    )

    for j in possible:

        if j <= i:
            continue

        overlap_pairs += 1

        intersection = geom.intersection(
            candidates.geometry.iloc[j]
        )

        if intersection.area > 1e-6:
            positive_overlap_pairs += 1


print(
    f"Intersecting candidate pairs       : "
    f"{overlap_pairs:,}"
)

print(
    f"Pairs with positive AREA overlap   : "
    f"{positive_overlap_pairs:,}"
)


# ============================================================
# 10. FINAL SUMMARY
# ============================================================

print()
print("=" * 84)
print("10. AUDIT SUMMARY")
print("=" * 84)

checks = {
    "valid_geometries":
        invalid_geometry == 0,

    "unique_candidate_ids":
        duplicate_ids == 0
        and missing_ids == 0,

    "all_pass_area":
        fail_area == 0,

    "all_pass_length":
        fail_length == 0,

    "all_pass_width":
        fail_width == 0,

    "stored_area_matches_geometry":
        area_difference.max() < 1e-6,

    "no_residual_building_area":
        overlap_areas.sum() < 1e-6,

    "no_candidate_area_overlap":
        positive_overlap_pairs == 0,
}


for name, passed in checks.items():

    status = (
        "PASS"
        if passed
        else "FAIL"
    )

    print(
        f"{name:<36} : "
        f"{status}"
    )


all_pass = all(
    checks.values()
)


print()
print("=" * 84)

if all_pass:

    print(
        "CORE CANDIDATE-GENERATION INVARIANTS: PASS"
    )

else:

    print(
        "CORE CANDIDATE-GENERATION INVARIANTS: "
        "CHECK FAILURES ABOVE"
    )

print("=" * 84)