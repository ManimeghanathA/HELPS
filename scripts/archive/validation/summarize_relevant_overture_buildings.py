from pathlib import Path
import ast

import geopandas as gpd
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]

BUILDINGS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "buildings"
    / "bhadra_overture_buildings_in_possible_open.geojson"
)


print("=" * 80)
print("HELPSs — RELEVANT OVERTURE BUILDING SUMMARY")
print("=" * 80)


gdf = gpd.read_file(BUILDINGS_PATH)

print(f"Relevant buildings : {len(gdf):,}")
print()


# ============================================================
# PARSE SOURCE FIELD
# ============================================================

def parse_source(value):

    if value is None:
        return None, None, None, None

    try:

        if isinstance(value, str):
            parsed = ast.literal_eval(value)
        else:
            parsed = value

        if not parsed:
            return None, None, None, None

        source = parsed[0]

        provider = source.get("provider")
        dataset = source.get("dataset")
        confidence = source.get("confidence")
        update_time = source.get("update_time")

        return (
            provider,
            dataset,
            confidence,
            update_time,
        )

    except Exception:

        return None, None, None, None


parsed = gdf["sources"].apply(
    parse_source
)

gdf["provider"] = [
    x[0] for x in parsed
]

gdf["dataset"] = [
    x[1] for x in parsed
]

gdf["confidence"] = [
    x[2] for x in parsed
]

gdf["source_update_time"] = [
    x[3] for x in parsed
]


# ============================================================
# PROVIDER COUNTS
# ============================================================

print("=" * 80)
print("PROVIDER DISTRIBUTION")
print("=" * 80)

provider_counts = (
    gdf["provider"]
    .fillna("UNKNOWN")
    .value_counts()
)

for provider, count in provider_counts.items():

    print(
        f"{provider:<20} "
        f"{count:>8,} "
        f"({count / len(gdf) * 100:6.2f}%)"
    )


# ============================================================
# DATASET COUNTS
# ============================================================

print()
print("=" * 80)
print("DATASET DISTRIBUTION")
print("=" * 80)

dataset_counts = (
    gdf["dataset"]
    .fillna("UNKNOWN")
    .value_counts()
)

for dataset, count in dataset_counts.items():

    print(
        f"{dataset:<35} "
        f"{count:>8,}"
    )


# ============================================================
# CONFIDENCE
# ============================================================

confidence = (
    gdf["confidence"]
    .dropna()
    .astype(float)
)

print()
print("=" * 80)
print("CONFIDENCE SUMMARY")
print("=" * 80)

print(
    f"Buildings with confidence : "
    f"{len(confidence):,}"
)

print(
    f"Buildings without confidence : "
    f"{len(gdf) - len(confidence):,}"
)

if len(confidence) > 0:

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

        print(
            f"P{percentile:02d} : "
            f"{np.percentile(confidence, percentile):.4f}"
        )


# ============================================================
# FOOTPRINT SIZE
# ============================================================

areas = gdf["footprint_area_m2"]

print()
print("=" * 80)
print("FOOTPRINT SIZE DISTRIBUTION")
print("=" * 80)

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

    print(
        f"P{percentile:02d} : "
        f"{np.percentile(areas, percentile):.2f} m²"
    )


# ============================================================
# VERY SMALL FOOTPRINTS
# ============================================================

print()
print("=" * 80)
print("SMALL FOOTPRINT COUNTS")
print("=" * 80)

for threshold in [
    5,
    10,
    20,
    30,
]:

    count = np.count_nonzero(
        areas < threshold
    )

    print(
        f"< {threshold:2d} m² : "
        f"{count:>8,} "
        f"({count / len(gdf) * 100:6.2f}%)"
    )


print()
print("=" * 80)
print("SUMMARY COMPLETE")
print("=" * 80)