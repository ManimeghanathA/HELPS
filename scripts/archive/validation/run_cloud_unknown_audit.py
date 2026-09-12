from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio

from scripts.validation.candidate_cloud_audit import (
    audit_unknown_overlap,
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

STATE_PATH = (
    BASE_DIR
    / "bhadra_possible_open_mask_v2.tif"
)

SCL_PATH = (
    BASE_DIR
    / "bhadra_scl.tif"
)

ZONE_PATH = (
    BASE_DIR
    / "bhadra_final_open_land_zones.gpkg"
)


UNKNOWN = 255

CLOUD_CLASSES = {
    3,   # cloud shadow
    8,   # cloud medium probability
    9,   # cloud high probability
    10,  # thin cirrus
}


print("=" * 84)
print("HELPSs — CLOUD / UNKNOWN INTEGRITY AUDIT")
print("=" * 84)


# ============================================================
# LOAD FINAL ZONES
# ============================================================

zones = gpd.read_file(
    ZONE_PATH,
    layer="final_open_land_zones",
)

print(
    f"Final zones loaded : "
    f"{len(zones):,}"
)


# ============================================================
# LOAD V2 STATE RASTER
# ============================================================

with rasterio.open(STATE_PATH) as src:

    state = src.read(1)

    transform = src.transform
    raster_crs = src.crs

    pixel_area_m2 = (
        abs(src.transform.a)
        * abs(src.transform.e)
    )


# ============================================================
# UNKNOWN OVERLAP AUDIT
# ============================================================

result = audit_unknown_overlap(
    zones=zones,
    state=state,
    transform=transform,
    raster_crs=raster_crs,
)


print()
print("=" * 84)
print("UNKNOWN OVERLAP")
print("=" * 84)

print(
    f"Zones overlapping UNKNOWN pixels : "
    f"{result['zones_with_unknown_overlap']:,}"
)

print(
    f"UNKNOWN pixels inside zones      : "
    f"{result['unknown_overlap_pixels']:,}"
)

print(
    f"UNKNOWN overlap area             : "
    f"{result['unknown_overlap_pixels'] * pixel_area_m2 / 1_000_000:.6f} km²"
)


# ============================================================
# DIRECT SCL CLOUD CHECK
# ============================================================

with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


cloud_mask = np.isin(
    scl,
    list(CLOUD_CLASSES),
)


from rasterio.features import rasterize


zone_mask = rasterize(
    (
        (geom, 1)
        for geom in zones.to_crs(
            raster_crs
        ).geometry
    ),
    out_shape=state.shape,
    transform=transform,
    fill=0,
    dtype="uint8",
    all_touched=False,
)


cloud_overlap = (
    (zone_mask == 1)
    & cloud_mask
)


cloud_pixels = int(
    np.count_nonzero(
        cloud_overlap
    )
)


print()
print("=" * 84)
print("DIRECT SCL CLOUD CHECK")
print("=" * 84)

print(
    f"Cloud / shadow pixels inside zones : "
    f"{cloud_pixels:,}"
)

print(
    f"Cloud overlap area                 : "
    f"{cloud_pixels * pixel_area_m2 / 1_000_000:.6f} km²"
)


# ============================================================
# FINAL RESULT
# ============================================================

print()
print("=" * 84)
print("AUDIT RESULT")
print("=" * 84)


passed = (
    result["unknown_overlap_pixels"] == 0
    and cloud_pixels == 0
)


if passed:

    print(
        "PASS — final zones contain no cloud/UNKNOWN "
        "Sentinel pixels."
    )

else:

    print(
        "FAIL — some final zones contain cloud/UNKNOWN "
        "pixels and must be investigated."
    )


print("=" * 84)