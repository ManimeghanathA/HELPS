from pathlib import Path

import numpy as np
import rasterio
import matplotlib.pyplot as plt


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
OPEN_MASK_PATH = BASE_DIR / "bhadra_open_mask.tif"

OUTPUT_PATH = BASE_DIR / "bhadra_open_land_overlay.png"


# ============================================================
# READ DATA
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:
    blue = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    red = src.read(3).astype(np.float32)

    bounds = src.bounds


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


with rasterio.open(OPEN_MASK_PATH) as src:
    open_state = src.read(1)


# ============================================================
# AOI MASK
# ============================================================

inside_aoi = scl != 0


# ============================================================
# RGB
# ============================================================

rgb = np.stack(
    [red, green, blue],
    axis=-1,
)

rgb_display = np.zeros_like(
    rgb,
    dtype=np.float32,
)


for channel in range(3):

    band = rgb[:, :, channel]

    valid_values = band[
        inside_aoi
        & np.isfinite(band)
        & (band >= 0)
    ]

    low = np.percentile(valid_values, 1)
    high = np.percentile(valid_values, 99)

    stretched = (
        band - low
    ) / (
        high - low
    )

    stretched = np.clip(
        stretched,
        0,
        1,
    )

    stretched = np.power(
        stretched,
        0.8,
    )

    rgb_display[:, :, channel] = stretched


rgb_display[~inside_aoi] = 0


# ============================================================
# OPEN PIXELS
# ============================================================

open_pixels = open_state == 1
unknown_pixels = open_state == 255


# ============================================================
# STATISTICS
# ============================================================

aoi_pixels = np.count_nonzero(
    inside_aoi
)

open_count = np.count_nonzero(
    open_pixels & inside_aoi
)

unknown_count = np.count_nonzero(
    unknown_pixels & inside_aoi
)

observed_count = (
    aoi_pixels
    - unknown_count
)

not_open_count = (
    observed_count
    - open_count
)


print("=" * 72)
print("BHADRA OPEN-LAND OVERLAY")
print("=" * 72)

print(f"AOI pixels          : {aoi_pixels:,}")
print(f"Observed AOI pixels : {observed_count:,}")
print(f"OPEN pixels         : {open_count:,}")
print(f"NOT_OPEN pixels     : {not_open_count:,}")
print(f"UNKNOWN AOI pixels  : {unknown_count:,}")

print()

print(
    f"Observed fraction   : "
    f"{observed_count / aoi_pixels * 100:.2f}%"
)

print(
    f"Unknown fraction    : "
    f"{unknown_count / aoi_pixels * 100:.2f}%"
)

print(
    f"Open / observed     : "
    f"{open_count / observed_count * 100:.2f}%"
)


# ============================================================
# VISUALIZATION
# ============================================================

fig, ax = plt.subplots(
    figsize=(11, 13)
)

ax.imshow(
    rgb_display,
    extent=[
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top,
    ],
    origin="upper",
)


# Red transparent layer for OPEN pixels
overlay = np.zeros(
    (
        open_state.shape[0],
        open_state.shape[1],
        4,
    ),
    dtype=np.float32,
)

overlay[
    open_pixels,
    0,
] = 1.0

overlay[
    open_pixels,
    3,
] = 0.55


ax.imshow(
    overlay,
    extent=[
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top,
    ],
    origin="upper",
)


ax.set_title(
    "HELPSs — Detected Open-Looking Terrain\n"
    f"Sentinel-2 {DATE}"
)

ax.set_xlabel(
    "Easting (m)"
)

ax.set_ylabel(
    "Northing (m)"
)

plt.tight_layout()

plt.savefig(
    OUTPUT_PATH,
    dpi=200,
    bbox_inches="tight",
)

plt.close()


print()
print(f"Overlay saved to:\n{OUTPUT_PATH}")

print("=" * 72)