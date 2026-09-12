from pathlib import Path

import geopandas as gpd

from scripts.processing.operational_zone_extraction import (
    extract_operational_zones,
)

from scripts.processing.candidate_geometry_filter import (
    measure_candidate_geometry,
)

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
    / "bhadra_final_open_land_zones.gpkg"
)


CLEARANCE_RADIUS_M = 15.0

MIN_AREA_M2 = 900.0
MIN_LENGTH_M = 30.0
MIN_WIDTH_M = 30.0

MIN_CLEAR_DIAMETER_M = 30.0

MIC_TOLERANCE_M = 0.5


print("=" * 84)
print("HELPSs — FINAL SINGLE-DATE OPEN-LAND ZONE GENERATION")
print("=" * 84)

print(f"Input candidates      : {INPUT_PATH}")
print(f"Clearance radius      : {CLEARANCE_RADIUS_M:.1f} m")
print(f"Minimum area          : {MIN_AREA_M2:.0f} m²")
print(f"Minimum length        : {MIN_LENGTH_M:.0f} m")
print(f"Minimum width         : {MIN_WIDTH_M:.0f} m")
print(f"Minimum clear diameter: {MIN_CLEAR_DIAMETER_M:.0f} m")
print()


# ============================================================
# LOAD CURRENT CANDIDATES
# ============================================================

candidates = gpd.read_file(
    INPUT_PATH,
    layer="candidate_open_lands",
)

print(
    f"Parent candidates loaded : "
    f"{len(candidates):,}"
)


# ============================================================
# GENERATE OPERATIONAL ZONES
# ============================================================

all_zone_records = []

parents_with_no_zone = 0
parents_single_zone = 0
parents_split = 0


for _, row in candidates.iterrows():

    parent_id = row["candidate_id"]

    zones = extract_operational_zones(
        row.geometry,
        clearance_radius_m=CLEARANCE_RADIUS_M,
    )

    if len(zones) == 0:

        parents_with_no_zone += 1

    elif len(zones) == 1:

        parents_single_zone += 1

    else:

        parents_split += 1

    for zone_number, zone in enumerate(
        zones,
        start=1,
    ):

        measurements = measure_candidate_geometry(
            zone
        )

        all_zone_records.append(
            {
                "parent_candidate_id": parent_id,
                "zone_number": zone_number,

                "area_m2":
                    measurements["area_m2"],

                "length_m":
                    measurements["length_m"],

                "width_m":
                    measurements["width_m"],

                "geometry": zone,
            }
        )


all_zones = gpd.GeoDataFrame(
    all_zone_records,
    geometry="geometry",
    crs=candidates.crs,
)


print()
print(
    f"Raw operational zones generated : "
    f"{len(all_zones):,}"
)


# ============================================================
# REAPPLY GEOMETRY GATE TO EACH CHILD ZONE
# ============================================================

all_zones["passes_area"] = (
    all_zones["area_m2"]
    >= MIN_AREA_M2
)

all_zones["passes_length"] = (
    all_zones["length_m"]
    >= MIN_LENGTH_M
)

all_zones["passes_width"] = (
    all_zones["width_m"]
    >= MIN_WIDTH_M
)


all_zones["passes_geometry_gate"] = (
    all_zones["passes_area"]
    & all_zones["passes_length"]
    & all_zones["passes_width"]
)


geometry_passed = all_zones[
    all_zones["passes_geometry_gate"]
].copy()


print(
    f"Zones passing geometry gate      : "
    f"{len(geometry_passed):,}"
)


# ============================================================
# MAXIMUM CLEARANCE / MIC
# ============================================================

mic_centers = []
mic_radii = []
mic_diameters = []


for geom in geometry_passed.geometry:

    result = measure_maximum_clearance(
        geom,
        tolerance_m=MIC_TOLERANCE_M,
    )

    mic_centers.append(
        result["center"]
    )

    mic_radii.append(
        result["radius_m"]
    )

    mic_diameters.append(
        result["diameter_m"]
    )


geometry_passed["max_clear_radius_m"] = (
    mic_radii
)

geometry_passed["max_clear_diameter_m"] = (
    mic_diameters
)


geometry_passed["passes_clearance"] = (
    geometry_passed["max_clear_diameter_m"]
    >= MIN_CLEAR_DIAMETER_M
)


# ============================================================
# FINAL ZONES
# ============================================================

final_zones = geometry_passed[
    geometry_passed["passes_clearance"]
].copy()

final_zones = final_zones.reset_index(
    drop=True
)


final_zones["zone_id"] = [
    f"BHADRA_{DATE.replace('-', '')}_ZONE_{i:06d}"
    for i in range(
        1,
        len(final_zones) + 1,
    )
]


# ============================================================
# BUILD FINAL MIC CENTER LAYER
# ============================================================

final_centers = []


for index, row in geometry_passed.iterrows():

    if not row["passes_clearance"]:
        continue

    center = mic_centers[
        geometry_passed.index.get_loc(index)
    ]

    if center is None:
        continue

    final_centers.append(
        {
            "parent_candidate_id":
                row["parent_candidate_id"],

            "zone_number":
                row["zone_number"],

            "max_clear_radius_m":
                row["max_clear_radius_m"],

            "max_clear_diameter_m":
                row["max_clear_diameter_m"],

            "geometry":
                center,
        }
    )


centers_gdf = gpd.GeoDataFrame(
    final_centers,
    geometry="geometry",
    crs=candidates.crs,
)


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 84)
print("FINAL ZONE GENERATION RESULT")
print("=" * 84)

print(
    f"Original parent candidates       : "
    f"{len(candidates):,}"
)

print(
    f"Parents with no clearance zone   : "
    f"{parents_with_no_zone:,}"
)

print(
    f"Parents remaining as one zone    : "
    f"{parents_single_zone:,}"
)

print(
    f"Parents split into multiple zones: "
    f"{parents_split:,}"
)

print()

print(
    f"Raw operational zones            : "
    f"{len(all_zones):,}"
)

print(
    f"Pass child geometry gate          : "
    f"{len(geometry_passed):,}"
)

print(
    f"Pass MIC >= 30 m                  : "
    f"{len(final_zones):,}"
)


# ============================================================
# REJECTION COUNTS
# ============================================================

print()
print("=" * 84)
print("ZONE REJECTION SUMMARY")
print("=" * 84)

print(
    f"Fail area                         : "
    f"{(~all_zones['passes_area']).sum():,}"
)

print(
    f"Fail length                       : "
    f"{(~all_zones['passes_length']).sum():,}"
)

print(
    f"Fail width                        : "
    f"{(~all_zones['passes_width']).sum():,}"
)

print(
    f"Fail MIC after geometry gate      : "
    f"{(~geometry_passed['passes_clearance']).sum():,}"
)


# ============================================================
# FINAL DISTRIBUTION
# ============================================================

if not final_zones.empty:

    print()
    print("=" * 84)
    print("FINAL ZONE STATISTICS")
    print("=" * 84)

    print(
        f"Total final area          : "
        f"{final_zones.geometry.area.sum() / 1_000_000:.3f} km²"
    )

    print(
        f"Median area               : "
        f"{final_zones['area_m2'].median():.2f} m²"
    )

    print(
        f"Median length             : "
        f"{final_zones['length_m'].median():.2f} m"
    )

    print(
        f"Median width              : "
        f"{final_zones['width_m'].median():.2f} m"
    )

    print(
        f"Median clear diameter     : "
        f"{final_zones['max_clear_diameter_m'].median():.2f} m"
    )

    print(
        f"Maximum clear diameter    : "
        f"{final_zones['max_clear_diameter_m'].max():.2f} m"
    )


# ============================================================
# SAVE
# ============================================================

if OUTPUT_PATH.exists():
    OUTPUT_PATH.unlink()


all_zones.to_file(
    OUTPUT_PATH,
    layer="all_operational_zones",
    driver="GPKG",
)


geometry_passed.to_file(
    OUTPUT_PATH,
    layer="geometry_passed_zones",
    driver="GPKG",
)


final_zones.to_file(
    OUTPUT_PATH,
    layer="final_open_land_zones",
    driver="GPKG",
)


if not centers_gdf.empty:

    centers_gdf.to_file(
        OUTPUT_PATH,
        layer="maximum_clearance_centers",
        driver="GPKG",
    )


print()
print("=" * 84)
print("FINAL OPEN-LAND ZONE GENERATION COMPLETE")
print("=" * 84)

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print()
print("Layers:")
print("  all_operational_zones")
print("  geometry_passed_zones")
print("  final_open_land_zones")
print("  maximum_clearance_centers")

print("=" * 84)