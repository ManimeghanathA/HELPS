from pathlib import Path

import numpy as np
import rasterio

from scripts.processing.open_land_detector import (
    generate_possible_open_mask,
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

SPECTRAL_PATH = BASE_DIR / "bhadra_spectral.tif"
SCL_PATH = BASE_DIR / "bhadra_scl.tif"

OUTPUT_PATH = (
    BASE_DIR
    / "bhadra_possible_open_mask_v2.tif"
)


print("=" * 72)
print("HELPSs — POSSIBLE OPEN DETECTION V2")
print("=" * 72)

print(f"Date     : {DATE}")
print(f"Spectral : {SPECTRAL_PATH}")
print(f"SCL      : {SCL_PATH}")
print(f"Output   : {OUTPUT_PATH}")
print()


generate_possible_open_mask(
    spectral_path=SPECTRAL_PATH,
    scl_path=SCL_PATH,
    output_path=OUTPUT_PATH,
    cloud_buffer_pixels=3,
)


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


with rasterio.open(OUTPUT_PATH) as src:
    state = src.read(1)

    pixel_area_m2 = (
        abs(src.transform.a)
        * abs(src.transform.e)
    )


inside_aoi = scl != 0

possible_open_pixels = np.count_nonzero(
    (state == 1)
    & inside_aoi
)

not_open_pixels = np.count_nonzero(
    (state == 0)
    & inside_aoi
)

unknown_pixels = np.count_nonzero(
    (state == 255)
    & inside_aoi
)

aoi_pixels = np.count_nonzero(
    inside_aoi
)

observed_pixels = (
    possible_open_pixels
    + not_open_pixels
)

possible_open_area_km2 = (
    possible_open_pixels
    * pixel_area_m2
    / 1_000_000
)


print("=" * 72)
print("V2 SUMMARY")
print("=" * 72)

print(
    f"AOI pixels             : "
    f"{aoi_pixels:,}"
)

print(
    f"Observed AOI pixels    : "
    f"{observed_pixels:,}"
)

print()

print(
    f"POSSIBLE_OPEN pixels   : "
    f"{possible_open_pixels:,}"
)

print(
    f"NOT_OPEN pixels        : "
    f"{not_open_pixels:,}"
)

print(
    f"UNKNOWN pixels         : "
    f"{unknown_pixels:,}"
)

print()

print(
    f"Possible-open area     : "
    f"{possible_open_area_km2:.3f} km²"
)

if observed_pixels > 0:
    print(
        f"Possible-open/observed : "
        f"{possible_open_pixels / observed_pixels * 100:.2f}%"
    )

if aoi_pixels > 0:
    print(
        f"Unknown/AOI            : "
        f"{unknown_pixels / aoi_pixels * 100:.2f}%"
    )

print()

print("Class values:")
print("  0   = NOT_OPEN")
print("  1   = POSSIBLE_OPEN")
print("  255 = UNKNOWN")

print("=" * 72)