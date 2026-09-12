from pathlib import Path

import rasterio

from scripts.processing.candidate_polygonization import (
    polygonize_open_mask,
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

OPEN_MASK_PATH = (
    BASE_DIR
    / "bhadra_possible_open_mask_v2.tif"
)

OUTPUT_PATH = (
    BASE_DIR
    / "bhadra_sentinel_open_components.gpkg"
)


print("=" * 80)
print("HELPSs — SENTINEL OPEN-LAND POLYGONIZATION")
print("=" * 80)

print(f"Input : {OPEN_MASK_PATH}")
print()


# ============================================================
# READ SENTINEL POSSIBLE-OPEN MASK
# ============================================================

with rasterio.open(OPEN_MASK_PATH) as src:

    state = src.read(1)

    transform = src.transform
    crs = src.crs


# ============================================================
# POLYGONIZE CONNECTED OPEN REGIONS
# ============================================================

components = polygonize_open_mask(
    state=state,
    transform=transform,
    crs=crs,
)


# ============================================================
# ADD BASIC GEOMETRY INFORMATION
# ============================================================

components["area_m2"] = (
    components.geometry.area
)

components["area_km2"] = (
    components["area_m2"]
    / 1_000_000
)


# ============================================================
# SUMMARY
# ============================================================

print(
    f"Connected open components : "
    f"{len(components):,}"
)

print(
    f"Total open area           : "
    f"{components['area_km2'].sum():.3f} km²"
)

if len(components) > 0:

    print()
    print("Component area statistics")

    print(
        f"Minimum : "
        f"{components['area_m2'].min():.2f} m²"
    )

    print(
        f"Median  : "
        f"{components['area_m2'].median():.2f} m²"
    )

    print(
        f"Mean    : "
        f"{components['area_m2'].mean():.2f} m²"
    )

    print(
        f"Maximum : "
        f"{components['area_m2'].max():.2f} m²"
    )


# ============================================================
# SAVE
# ============================================================

components.to_file(
    OUTPUT_PATH,
    layer="sentinel_open_components",
    driver="GPKG",
)


print()
print("=" * 80)
print("POLYGONIZATION COMPLETE")
print("=" * 80)

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print()
print(
    "NOTE: These are raw Sentinel open-surface components."
)

print(
    "They are NOT final landing-site candidates."
)

print("=" * 80)