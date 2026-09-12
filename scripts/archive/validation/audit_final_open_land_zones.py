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

FINAL_PATH = (
    BASE_DIR
    / "bhadra_final_open_land_zones.gpkg"
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
MIN_CLEAR_DIAMETER_M = 30.0

AREA_TOLERANCE = 1e-6


print("=" * 88)
print("HELPSs — FINAL OPEN-LAND ZONE TOPOLOGY / CONSISTENCY AUDIT")
print("=" * 88)


# ============================================================
# LOAD FINAL ZONES
# ============================================================

zones = gpd.read_file(
    FINAL_PATH,
    layer="final_open_land_zones",
)

print(f"Final zones loaded : {len(zones):,}")
print(f"CRS                : {zones.crs}")


# ============================================================
# 1. BASIC GEOMETRY
# ============================================================

print()
print("=" * 88)
print("1. GEOMETRY INTEGRITY")
print("=" * 88)

null_count = int(
    zones.geometry.isna().sum()
)

empty_count = int(
    zones.geometry.is_empty.sum()
)

invalid_count = int(
    (~zones.geometry.is_valid).sum()
)

geometry_types = (
    zones.geometry.geom_type
    .value_counts()
)

print(f"Null geometries    : {null_count:,}")
print(f"Empty geometries   : {empty_count:,}")
print(f"Invalid geometries : {invalid_count:,}")

print()

for geom_type, count in geometry_types.items():
    print(
        f"{geom_type:<20} : "
        f"{count:,}"
    )


# ============================================================
# 2. ID INTEGRITY
# ============================================================

print()
print("=" * 88)
print("2. ID INTEGRITY")
print("=" * 88)

missing_ids = int(
    zones["zone_id"].isna().sum()
)

duplicate_ids = int(
    zones["zone_id"].duplicated().sum()
)

print(f"Missing zone IDs   : {missing_ids:,}")
print(f"Duplicate zone IDs : {duplicate_ids:,}")


# ============================================================
# 3. THRESHOLD INVARIANTS
# ============================================================

print()
print("=" * 88)
print("3. FINAL THRESHOLD INVARIANTS")
print("=" * 88)

fail_area = int(
    (zones["area_m2"] < MIN_AREA_M2).sum()
)

fail_length = int(
    (zones["length_m"] < MIN_LENGTH_M).sum()
)

fail_width = int(
    (zones["width_m"] < MIN_WIDTH_M).sum()
)

fail_clearance = int(
    (
        zones["max_clear_diameter_m"]
        < MIN_CLEAR_DIAMETER_M
    ).sum()
)

print(f"Area failures           : {fail_area:,}")
print(f"Length failures         : {fail_length:,}")
print(f"Width failures          : {fail_width:,}")
print(f"Clear-diameter failures : {fail_clearance:,}")

print()

print(
    f"Minimum area           : "
    f"{zones['area_m2'].min():.3f} m²"
)

print(
    f"Minimum length         : "
    f"{zones['length_m'].min():.3f} m"
)

print(
    f"Minimum width          : "
    f"{zones['width_m'].min():.3f} m"
)

print(
    f"Minimum clear diameter : "
    f"{zones['max_clear_diameter_m'].min():.3f} m"
)


# ============================================================
# 4. STORED AREA VS ACTUAL AREA
# ============================================================

print()
print("=" * 88)
print("4. STORED AREA CONSISTENCY")
print("=" * 88)

actual_area = (
    zones.geometry.area
)

area_difference = np.abs(
    actual_area
    - zones["area_m2"]
)

print(
    f"Maximum discrepancy : "
    f"{area_difference.max():.9f} m²"
)

print(
    f"Mean discrepancy    : "
    f"{area_difference.mean():.9f} m²"
)


# ============================================================
# 5. PARENT / SPLIT STATISTICS
# ============================================================

print()
print("=" * 88)
print("5. PARENT / ZONE STRUCTURE")
print("=" * 88)

parent_counts = (
    zones["parent_candidate_id"]
    .value_counts()
)

print(
    f"Unique surviving parents : "
    f"{parent_counts.size:,}"
)

print(
    f"Parents with one final zone : "
    f"{(parent_counts == 1).sum():,}"
)

print(
    f"Parents with 2+ final zones : "
    f"{(parent_counts > 1).sum():,}"
)

print(
    f"Maximum final zones from one parent : "
    f"{parent_counts.max():,}"
)


# ============================================================
# 6. BUILDING OVERLAP
# ============================================================

print()
print("=" * 88)
print("6. RESIDUAL BUILDING OVERLAP")
print("=" * 88)

overture = gpd.read_file(
    OVERTURE_PATH
)

osm = gpd.read_file(
    OSM_PATH,
    layer="buildings",
)


if overture.crs != zones.crs:
    overture = overture.to_crs(
        zones.crs
    )

if osm.crs != zones.crs:
    osm = osm.to_crs(
        zones.crs
    )


overture = overture[
    overture.geometry.notna()
    & ~overture.geometry.is_empty
].copy()

osm = osm[
    osm.geometry.notna()
    & ~osm.geometry.is_empty
].copy()


buildings = gpd.GeoDataFrame(
    pd.concat(
        [
            overture[["geometry"]],
            osm[["geometry"]],
        ],
        ignore_index=True,
    ),
    geometry="geometry",
    crs=zones.crs,
)


building_union = (
    buildings.geometry.union_all()
)


touching_buildings = (
    zones.geometry.intersects(
        building_union
    )
)

building_overlap_area = (
    zones.geometry.apply(
        lambda geom:
            geom.intersection(
                building_union
            ).area
    )
)


print(
    f"Zones touching building boundaries : "
    f"{touching_buildings.sum():,}"
)

print(
    f"Zones with positive building area  : "
    f"{(building_overlap_area > AREA_TOLERANCE).sum():,}"
)

print(
    f"Total residual building overlap    : "
    f"{building_overlap_area.sum():.9f} m²"
)


# ============================================================
# 7. INTERNAL ZONE OVERLAP
# ============================================================

print()
print("=" * 88)
print("7. FINAL ZONE ↔ ZONE OVERLAP")
print("=" * 88)

sindex = zones.sindex

intersecting_pairs = 0
positive_overlap_pairs = 0

total_overlap_area = 0.0
maximum_overlap_area = 0.0

same_parent_overlap_pairs = 0
different_parent_overlap_pairs = 0


for i, geom in enumerate(
    zones.geometry
):

    candidates_idx = sindex.query(
        geom,
        predicate="intersects",
    )

    for j in candidates_idx:

        if j <= i:
            continue

        intersecting_pairs += 1

        other = zones.geometry.iloc[j]

        intersection = geom.intersection(
            other
        )

        overlap_area = (
            intersection.area
        )

        if overlap_area > AREA_TOLERANCE:

            positive_overlap_pairs += 1

            total_overlap_area += (
                overlap_area
            )

            maximum_overlap_area = max(
                maximum_overlap_area,
                overlap_area,
            )

            parent_i = zones.iloc[i][
                "parent_candidate_id"
            ]

            parent_j = zones.iloc[j][
                "parent_candidate_id"
            ]

            if parent_i == parent_j:
                same_parent_overlap_pairs += 1

            else:
                different_parent_overlap_pairs += 1


print(
    f"Intersecting zone pairs       : "
    f"{intersecting_pairs:,}"
)

print(
    f"Positive-area overlap pairs   : "
    f"{positive_overlap_pairs:,}"
)

print(
    f"  Same-parent overlaps        : "
    f"{same_parent_overlap_pairs:,}"
)

print(
    f"  Different-parent overlaps   : "
    f"{different_parent_overlap_pairs:,}"
)

print(
    f"Total pairwise overlap area   : "
    f"{total_overlap_area:.6f} m²"
)

print(
    f"Maximum pair overlap          : "
    f"{maximum_overlap_area:.6f} m²"
)


# ============================================================
# 8. HOLES
# ============================================================

print()
print("=" * 88)
print("8. FINAL POLYGON HOLES")
print("=" * 88)


def hole_count(geom):

    if geom.geom_type == "Polygon":
        return len(
            geom.interiors
        )

    if geom.geom_type == "MultiPolygon":
        return sum(
            len(part.interiors)
            for part in geom.geoms
        )

    return 0


holes = (
    zones.geometry.apply(
        hole_count
    )
)

print(
    f"Zones containing holes : "
    f"{(holes > 0).sum():,}"
)

print(
    f"Total holes            : "
    f"{holes.sum():,}"
)

print(
    f"Maximum holes in zone  : "
    f"{holes.max():,}"
)


# ============================================================
# 9. SIZE / CLEARANCE DISTRIBUTION
# ============================================================

print()
print("=" * 88)
print("9. FINAL ZONE DISTRIBUTION")
print("=" * 88)

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
        zones["area_m2"],
        percentile,
    )

    width = np.percentile(
        zones["width_m"],
        percentile,
    )

    clearance = np.percentile(
        zones["max_clear_diameter_m"],
        percentile,
    )

    print(
        f"P{percentile:02d} | "
        f"area={area:11.2f} m² | "
        f"width={width:8.2f} m | "
        f"clear={clearance:8.2f} m"
    )


# ============================================================
# 10. LARGEST / MOST COMPLEX ZONES
# ============================================================

print()
print("=" * 88)
print("10. LARGEST FINAL ZONES")
print("=" * 88)

largest = (
    zones[
        [
            "zone_id",
            "parent_candidate_id",
            "area_m2",
            "length_m",
            "width_m",
            "max_clear_diameter_m",
        ]
    ]
    .sort_values(
        "area_m2",
        ascending=False,
    )
    .head(15)
)

print(
    largest.to_string(
        index=False
    )
)


# ============================================================
# FINAL PASS / FAIL
# ============================================================

print()
print("=" * 88)
print("FINAL AUDIT SUMMARY")
print("=" * 88)

checks = {
    "valid_geometries":
        invalid_count == 0
        and null_count == 0
        and empty_count == 0,

    "unique_zone_ids":
        missing_ids == 0
        and duplicate_ids == 0,

    "all_pass_area":
        fail_area == 0,

    "all_pass_length":
        fail_length == 0,

    "all_pass_width":
        fail_width == 0,

    "all_pass_clear_diameter":
        fail_clearance == 0,

    "stored_area_matches_geometry":
        area_difference.max()
        < AREA_TOLERANCE,

    "no_residual_building_area":
        building_overlap_area.sum()
        < AREA_TOLERANCE,

    "no_positive_zone_overlap":
        positive_overlap_pairs == 0,
}


for name, passed in checks.items():

    print(
        f"{name:<38} : "
        f"{'PASS' if passed else 'FAIL'}"
    )


print()
print("=" * 88)

if all(checks.values()):

    print(
        "FINAL SINGLE-DATE TOPOLOGY / CONSISTENCY: PASS"
    )

else:

    print(
        "FINAL SINGLE-DATE TOPOLOGY / CONSISTENCY: "
        "INVESTIGATION REQUIRED"
    )

print("=" * 88)