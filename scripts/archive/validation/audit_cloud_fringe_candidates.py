from pathlib import Path

import numpy as np
import rasterio
import geopandas as gpd

from rasterio.features import rasterize


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

SPECTRAL_PATH = BASE_DIR / "bhadra_spectral.tif"
SCL_PATH = BASE_DIR / "bhadra_scl.tif"
STATE_PATH = BASE_DIR / "bhadra_possible_open_mask_v2.tif"

ZONE_PATH = (
    BASE_DIR
    / "bhadra_final_open_land_zones.gpkg"
)


CLOUD_CLASSES = {
    3,
    8,
    9,
    10,
}


print("=" * 84)
print("HELPSs — CLOUD FRINGE CANDIDATE AUDIT")
print("=" * 84)


# ============================================================
# LOAD RASTERS
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:

    blue = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    red = src.read(3).astype(np.float32)
    nir = src.read(4).astype(np.float32)
    swir1 = src.read(5).astype(np.float32)
    swir2 = src.read(6).astype(np.float32)

    transform = src.transform
    raster_crs = src.crs


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


with rasterio.open(STATE_PATH) as src:
    state = src.read(1)


# ============================================================
# LOAD FINAL ZONES
# ============================================================

zones = gpd.read_file(
    ZONE_PATH,
    layer="final_open_land_zones",
)

if zones.crs != raster_crs:
    zones = zones.to_crs(raster_crs)


zone_mask = rasterize(
    (
        (geom, 1)
        for geom in zones.geometry
        if geom is not None
        and not geom.is_empty
    ),
    out_shape=state.shape,
    transform=transform,
    fill=0,
    dtype="uint8",
    all_touched=False,
)


# ============================================================
# CLOUD MASK + 1 PIXEL NEIGHBOURHOOD
# ============================================================

cloud = np.isin(
    scl,
    list(CLOUD_CLASSES),
)


cloud_neighbourhood = cloud.copy()


# 8-neighbour dilation by one pixel
for dr in [-1, 0, 1]:

    for dc in [-1, 0, 1]:

        if dr == 0 and dc == 0:
            continue

        shifted = np.zeros_like(
            cloud,
            dtype=bool,
        )

        src_r0 = max(0, -dr)
        src_r1 = cloud.shape[0] - max(0, dr)

        src_c0 = max(0, -dc)
        src_c1 = cloud.shape[1] - max(0, dc)

        dst_r0 = max(0, dr)
        dst_r1 = cloud.shape[0] - max(0, -dr)

        dst_c0 = max(0, dc)
        dst_c1 = cloud.shape[1] - max(0, -dc)

        shifted[
            dst_r0:dst_r1,
            dst_c0:dst_c1,
        ] = cloud[
            src_r0:src_r1,
            src_c0:src_c1,
        ]

        cloud_neighbourhood |= shifted


cloud_fringe = (
    cloud_neighbourhood
    & ~cloud
)


# ============================================================
# INDEX HELPERS
# ============================================================

def normalized_difference(a, b):

    denominator = a + b

    result = np.zeros_like(
        a,
        dtype=np.float32,
    )

    valid = (
        np.isfinite(a)
        & np.isfinite(b)
        & (np.abs(denominator) > 1e-8)
    )

    result[valid] = (
        a[valid] - b[valid]
    ) / denominator[valid]

    return result


ndvi = normalized_difference(
    nir,
    red,
)

mndwi = normalized_difference(
    green,
    swir1,
)


# ============================================================
# IMPORTANT PIXEL GROUPS
# ============================================================

open_pixels = (
    state == 1
)

final_zone_pixels = (
    zone_mask == 1
)


open_on_fringe = (
    open_pixels
    & cloud_fringe
)

zones_on_fringe = (
    final_zone_pixels
    & cloud_fringe
)


# ============================================================
# REPORT
# ============================================================

print()
print("=" * 84)
print("FRINGE SUMMARY")
print("=" * 84)

print(
    f"Cloud pixels                     : "
    f"{np.count_nonzero(cloud):,}"
)

print(
    f"1-pixel non-cloud fringe pixels  : "
    f"{np.count_nonzero(cloud_fringe):,}"
)

print(
    f"OPEN pixels on cloud fringe      : "
    f"{np.count_nonzero(open_on_fringe):,}"
)

print(
    f"FINAL ZONE pixels on fringe      : "
    f"{np.count_nonzero(zones_on_fringe):,}"
)


# ============================================================
# SCL DISTRIBUTION FOR OPEN FRINGE PIXELS
# ============================================================

print()
print("=" * 84)
print("SCL CLASSES OF OPEN CLOUD-FRINGE PIXELS")
print("=" * 84)

values, counts = np.unique(
    scl[open_on_fringe],
    return_counts=True,
)

for value, count in zip(
    values,
    counts,
):

    print(
        f"SCL {int(value):>2} : "
        f"{int(count):,}"
    )


# ============================================================
# SPECTRAL STATISTICS
# ============================================================

def report_stats(name, array, mask):

    values = array[
        mask
        & np.isfinite(array)
    ]

    if len(values) == 0:

        print(
            f"{name:<8} : no values"
        )

        return

    print(
        f"{name:<8} : "
        f"P05={np.percentile(values, 5):.4f} "
        f"P50={np.percentile(values, 50):.4f} "
        f"P95={np.percentile(values, 95):.4f}"
    )


print()
print("=" * 84)
print("OPEN CLOUD-FRINGE SPECTRAL STATS")
print("=" * 84)

report_stats(
    "BLUE",
    blue,
    open_on_fringe,
)

report_stats(
    "GREEN",
    green,
    open_on_fringe,
)

report_stats(
    "RED",
    red,
    open_on_fringe,
)

report_stats(
    "NDVI",
    ndvi,
    open_on_fringe,
)

report_stats(
    "MNDWI",
    mndwi,
    open_on_fringe,
)


print()
print("=" * 84)
print("INTERPRETATION")
print("=" * 84)

print(
    "If OPEN/fringe counts are tiny, current buffering is likely adequate."
)

print(
    "If many final-zone pixels lie on cloud fringe, inspect their SCL and spectral values before changing thresholds."
)

print("=" * 84)