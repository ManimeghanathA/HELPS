from pathlib import Path

import numpy as np
import rasterio


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATE = "2026-06-01"

SPECTRAL_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "sentinel2"
    / DATE
    / "bhadra_spectral.tif"
)

SCL_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "sentinel2"
    / DATE
    / "bhadra_scl.tif"
)


SCL_CLASSES = {
    0: "No Data",
    1: "Saturated / defective",
    2: "Topographic shadow",
    3: "Cloud shadow",
    4: "Vegetation",
    5: "Bare / non-vegetated",
    6: "Water",
    7: "Unclassified",
    8: "Cloud medium probability",
    9: "Cloud high probability",
    10: "Thin cirrus",
    11: "Snow / ice",
}


# ============================================================
# HELPERS
# ============================================================

def safe_index(numerator, denominator):
    """
    Compute a normalized index safely.

    Pixels where the denominator is effectively zero become NaN.
    """

    result = np.full(
        numerator.shape,
        np.nan,
        dtype=np.float32,
    )

    valid = np.abs(denominator) > 1e-6

    result[valid] = (
        numerator[valid]
        / denominator[valid]
    )

    return result


def print_statistics(name, values):
    """
    Print useful percentiles for one spectral index.
    """

    values = values[np.isfinite(values)]

    if values.size == 0:
        print(f"{name:<8}: no valid pixels")
        return

    print(
        f"{name:<8}: "
        f"min={np.min(values):7.3f}  "
        f"P05={np.percentile(values, 5):7.3f}  "
        f"P25={np.percentile(values, 25):7.3f}  "
        f"P50={np.percentile(values, 50):7.3f}  "
        f"P75={np.percentile(values, 75):7.3f}  "
        f"P95={np.percentile(values, 95):7.3f}  "
        f"max={np.max(values):7.3f}"
    )


# ============================================================
# LOAD DATA
# ============================================================

if not SPECTRAL_PATH.exists():
    raise FileNotFoundError(
        f"Spectral raster does not exist:\n{SPECTRAL_PATH}"
    )

if not SCL_PATH.exists():
    raise FileNotFoundError(
        f"SCL raster does not exist:\n{SCL_PATH}"
    )


print("=" * 90)
print("HELPSs — BHADRA OPEN-LAND SPECTRAL ANALYSIS")
print("=" * 90)

print(f"Date     : {DATE}")
print(f"Spectral : {SPECTRAL_PATH}")
print(f"SCL      : {SCL_PATH}")


with rasterio.open(SPECTRAL_PATH) as src:

    b02 = src.read(1).astype(np.float32)  # Blue
    b03 = src.read(2).astype(np.float32)  # Green
    b04 = src.read(3).astype(np.float32)  # Red
    b08 = src.read(4).astype(np.float32)  # NIR
    b11 = src.read(5).astype(np.float32)  # SWIR1
    b12 = src.read(6).astype(np.float32)  # SWIR2

    spectral_shape = (
        src.height,
        src.width,
    )


with rasterio.open(SCL_PATH) as src:

    scl = src.read(1)

    scl_shape = (
        src.height,
        src.width,
    )


if spectral_shape != scl_shape:
    raise ValueError(
        "Spectral and SCL rasters do not have matching dimensions."
    )


# ============================================================
# SPECTRAL INDICES
# ============================================================

#
# NDVI
#
# High positive values generally indicate vegetation.
#
ndvi = safe_index(
    b08 - b04,
    b08 + b04,
)


#
# MNDWI
#
# Useful for separating water using Green and SWIR.
#
mndwi = safe_index(
    b03 - b11,
    b03 + b11,
)


#
# NDBI
#
# SWIR versus NIR.
#
# Can provide evidence for built-up / dry surfaces,
# but MUST NOT be treated as a reliable building detector.
#
ndbi = safe_index(
    b11 - b08,
    b11 + b08,
)


#
# BSI — Bare Soil Index
#
# Provides another signal for exposed / bare surfaces.
#
bsi = safe_index(
    (b11 + b04) - (b08 + b02),
    (b11 + b04) + (b08 + b02),
)


# ============================================================
# VALID PIXELS
# ============================================================

inside_aoi = scl != 0

finite_spectral = (
    np.isfinite(b02)
    & np.isfinite(b03)
    & np.isfinite(b04)
    & np.isfinite(b08)
    & np.isfinite(b11)
    & np.isfinite(b12)
)

valid = (
    inside_aoi
    & finite_spectral
)


print()
print("-" * 90)
print("BASIC COUNTS")
print("-" * 90)

print(
    f"Valid AOI pixels : "
    f"{np.count_nonzero(valid):,}"
)


# ============================================================
# GLOBAL INDEX STATISTICS
# ============================================================

print()
print("=" * 90)
print("INDEX DISTRIBUTIONS — WHOLE VALID BHADRA AOI")
print("=" * 90)

print_statistics(
    "NDVI",
    ndvi[valid],
)

print_statistics(
    "MNDWI",
    mndwi[valid],
)

print_statistics(
    "NDBI",
    ndbi[valid],
)

print_statistics(
    "BSI",
    bsi[valid],
)


# ============================================================
# INDEX STATISTICS BY SCL CLASS
# ============================================================

print()
print("=" * 90)
print("INDEX DISTRIBUTIONS BY SCL CLASS")
print("=" * 90)


for scl_value in [
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
]:

    class_mask = (
        valid
        & (scl == scl_value)
    )

    count = np.count_nonzero(
        class_mask
    )

    if count == 0:
        continue

    print()
    print("-" * 90)

    print(
        f"SCL {scl_value:2d} — "
        f"{SCL_CLASSES[scl_value]}"
    )

    print(
        f"Pixels : {count:,}"
    )

    print_statistics(
        "NDVI",
        ndvi[class_mask],
    )

    print_statistics(
        "MNDWI",
        mndwi[class_mask],
    )

    print_statistics(
        "NDBI",
        ndbi[class_mask],
    )

    print_statistics(
        "BSI",
        bsi[class_mask],
    )


# ============================================================
# EXTRA ANALYSIS OF BARE / NON-VEGETATED PIXELS
# ============================================================

bare_mask = (
    valid
    & (scl == 5)
)


print()
print("=" * 90)
print("SCL 5 — BARE / NON-VEGETATED PIXELS")
print("=" * 90)

print(
    f"Pixels : "
    f"{np.count_nonzero(bare_mask):,}"
)


if np.any(bare_mask):

    print()
    print(
        "NDVI distribution:"
    )

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
            f"  P{percentile:02d}: "
            f"{np.percentile(ndvi[bare_mask], percentile):.4f}"
        )


# ============================================================
# EXTRA ANALYSIS OF VEGETATION PIXELS
# ============================================================

vegetation_mask = (
    valid
    & (scl == 4)
)


print()
print("=" * 90)
print("SCL 4 — VEGETATION PIXELS")
print("=" * 90)

print(
    f"Pixels : "
    f"{np.count_nonzero(vegetation_mask):,}"
)


if np.any(vegetation_mask):

    print()
    print(
        "NDVI distribution:"
    )

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
            f"  P{percentile:02d}: "
            f"{np.percentile(ndvi[vegetation_mask], percentile):.4f}"
        )


# ============================================================
# WATER CHECK
# ============================================================

water_mask = (
    valid
    & (scl == 6)
)


print()
print("=" * 90)
print("SCL 6 — WATER PIXELS")
print("=" * 90)

print(
    f"Pixels : "
    f"{np.count_nonzero(water_mask):,}"
)


if np.any(water_mask):

    print()
    print(
        "MNDWI distribution:"
    )

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
            f"  P{percentile:02d}: "
            f"{np.percentile(mndwi[water_mask], percentile):.4f}"
        )


print()
print("=" * 90)
print("ANALYSIS COMPLETE")
print("=" * 90)

print()
print(
    "No open-land threshold has been applied yet."
)

print(
    "Use these distributions to choose evidence-based "
    "thresholds for the first HELPSs detector."
)