from pathlib import Path

import numpy as np
import rasterio

from scripts.processing.open_land_detector import generate_open_land_mask


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATE = "2026-06-01"

INPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "sentinel2"
    / DATE
)

SPECTRAL_PATH = INPUT_DIR / "bhadra_spectral.tif"
SCL_PATH = INPUT_DIR / "bhadra_scl.tif"
OUTPUT_PATH = INPUT_DIR / "bhadra_open_mask.tif"


print("=" * 72)
print("HELPSs — OPEN LAND DETECTION")
print("=" * 72)

print(f"Date     : {DATE}")
print(f"Spectral : {SPECTRAL_PATH}")
print(f"SCL      : {SCL_PATH}")
print(f"Output   : {OUTPUT_PATH}")
print()


generate_open_land_mask(
    spectral_path=SPECTRAL_PATH,
    scl_path=SCL_PATH,
    output_path=OUTPUT_PATH,
)


with rasterio.open(OUTPUT_PATH) as src:

    mask = src.read(1)

    pixel_width = abs(src.transform.a)
    pixel_height = abs(src.transform.e)

    pixel_area_m2 = (
        pixel_width
        * pixel_height
    )


open_pixels = np.count_nonzero(
    mask == 1
)

not_open_pixels = np.count_nonzero(
    mask == 0
)

unknown_pixels = np.count_nonzero(
    mask == 255
)

observed_pixels = (
    open_pixels
    + not_open_pixels
)

total_pixels = mask.size


open_area_m2 = (
    open_pixels
    * pixel_area_m2
)

open_area_km2 = (
    open_area_m2
    / 1_000_000
)


if observed_pixels > 0:

    open_fraction_observed = (
        open_pixels
        / observed_pixels
        * 100
    )

else:

    open_fraction_observed = 0


unknown_fraction = (
    unknown_pixels
    / total_pixels
    * 100
)


print("=" * 72)
print("OPEN LAND DETECTION SUMMARY")
print("=" * 72)

print(
    f"OPEN pixels      : "
    f"{open_pixels:,}"
)

print(
    f"NOT_OPEN pixels  : "
    f"{not_open_pixels:,}"
)

print(
    f"UNKNOWN pixels   : "
    f"{unknown_pixels:,}"
)

print(
    f"Observed pixels  : "
    f"{observed_pixels:,}"
)

print()

print(
    f"Pixel area       : "
    f"{pixel_area_m2:.2f} m²"
)

print(
    f"Open area        : "
    f"{open_area_km2:.3f} km²"
)

print(
    f"Open fraction    : "
    f"{open_fraction_observed:.2f}% "
    f"of observed pixels"
)

print(
    f"Unknown fraction : "
    f"{unknown_fraction:.2f}% "
    f"of raster"
)

print()

print(
    "Class values:"
)

print(
    "  0   = NOT_OPEN"
)

print(
    "  1   = OPEN"
)

print(
    "  255 = UNKNOWN"
)

print("=" * 72)