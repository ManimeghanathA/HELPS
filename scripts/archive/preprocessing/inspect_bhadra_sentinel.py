from pathlib import Path

import numpy as np
import rasterio


# ============================================================
# PATHS
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


# ============================================================
# CHECK FILES
# ============================================================

if not SPECTRAL_PATH.exists():
    raise FileNotFoundError(SPECTRAL_PATH)

if not SCL_PATH.exists():
    raise FileNotFoundError(SCL_PATH)


# ============================================================
# BAND NAMES
# ============================================================

BAND_NAMES = {
    1: "B02 - Blue",
    2: "B03 - Green",
    3: "B04 - Red",
    4: "B08 - NIR",
    5: "B11 - SWIR1",
    6: "B12 - SWIR2",
}


print("=" * 72)
print("BHADRA SENTINEL-2 SPECTRAL INSPECTION")
print("=" * 72)


# ============================================================
# READ SCL
# ============================================================

with rasterio.open(SCL_PATH) as scl_src:

    scl = scl_src.read(1)

    # Pixels inside the Bhadra AOI / real Sentinel observation
    valid_aoi = scl != 0


print(f"Valid AOI pixels : {np.count_nonzero(valid_aoi):,}")
print()


# ============================================================
# READ SPECTRAL RASTER
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:

    print(f"CRS        : {src.crs}")
    print(f"Size       : {src.width} x {src.height}")
    print(f"Bands      : {src.count}")
    print(f"Data type  : {src.dtypes}")
    print(f"NoData     : {src.nodata}")
    print(f"Resolution : {src.res}")

    print()
    print("-" * 72)
    print("BAND STATISTICS — INSIDE BHADRA ONLY")
    print("-" * 72)

    for band_index in range(1, src.count + 1):

        data = src.read(band_index).astype(np.float32)

        mask = (
            valid_aoi
            & np.isfinite(data)
            & (data > -1000)
        )

        values = data[mask]

        print()
        print(
            f"Band {band_index}: "
            f"{BAND_NAMES.get(band_index, 'Unknown')}"
        )

        if values.size == 0:
            print("No valid values.")
            continue

        print(f"Pixels : {values.size:,}")
        print(f"Min    : {np.min(values):.6f}")
        print(f"P01    : {np.percentile(values, 1):.6f}")
        print(f"P02    : {np.percentile(values, 2):.6f}")
        print(f"P25    : {np.percentile(values, 25):.6f}")
        print(f"Median : {np.median(values):.6f}")
        print(f"Mean   : {np.mean(values):.6f}")
        print(f"P75    : {np.percentile(values, 75):.6f}")
        print(f"P98    : {np.percentile(values, 98):.6f}")
        print(f"P99    : {np.percentile(values, 99):.6f}")
        print(f"Max    : {np.max(values):.6f}")


print()
print("=" * 72)
print("INSPECTION COMPLETE")
print("=" * 72)