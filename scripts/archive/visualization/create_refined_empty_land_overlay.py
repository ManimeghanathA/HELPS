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

BEFORE_BUILDINGS_PATH = (
    BASE_DIR
    / "bhadra_empty_land_mask.tif"
)

AFTER_BUILDINGS_PATH = (
    BASE_DIR
    / "bhadra_empty_land_mask_osm_overture.tif"
)

OUTPUT_PATH = (
    BASE_DIR
    / "bhadra_refined_empty_land_overlay.png"
)


# ============================================================
# LOAD RGB
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:

    blue = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    red = src.read(3).astype(np.float32)

    bounds = src.bounds


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


with rasterio.open(BEFORE_BUILDINGS_PATH) as src:
    before = src.read(1)


with rasterio.open(AFTER_BUILDINGS_PATH) as src:
    after = src.read(1)


inside_aoi = scl != 0


# ============================================================
# RGB DISPLAY
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

    values = band[
        inside_aoi
        & np.isfinite(band)
        & (band >= 0)
    ]

    low = np.percentile(values, 1)
    high = np.percentile(values, 99)

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
# CLASSIFY CHANGES
# ============================================================

remaining_empty = (
    after == 1
)

removed_by_overture = (
    (before == 1)
    & (after == 0)
)


remaining_count = np.count_nonzero(
    remaining_empty
)

removed_count = np.count_nonzero(
    removed_by_overture
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


# ------------------------------------------------------------
# GREEN = surviving possible-empty land
# ------------------------------------------------------------

green_overlay = np.zeros(
    (*after.shape, 4),
    dtype=np.float32,
)

green_overlay[
    remaining_empty,
    1,
] = 1.0

green_overlay[
    remaining_empty,
    3,
] = 0.50


ax.imshow(
    green_overlay,
    extent=[
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top,
    ],
    origin="upper",
)


# ------------------------------------------------------------
# RED = areas removed specifically because of Overture buildings
# ------------------------------------------------------------

red_overlay = np.zeros(
    (*after.shape, 4),
    dtype=np.float32,
)

red_overlay[
    removed_by_overture,
    0,
] = 1.0

red_overlay[
    removed_by_overture,
    3,
] = 0.80


ax.imshow(
    red_overlay,
    extent=[
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top,
    ],
    origin="upper",
)


ax.set_title(
    "HELPSs — Refined Possible Empty Land\n"
    "Green = retained | Red = removed by Overture buildings"
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
    dpi=220,
    bbox_inches="tight",
)

plt.close()


# ============================================================
# REPORT
# ============================================================

print("=" * 76)
print("HELPSs — REFINED EMPTY-LAND VISUAL CHECK")
print("=" * 76)

print(
    f"Remaining possible-empty pixels : "
    f"{remaining_count:,}"
)

print(
    f"Removed by Overture buildings   : "
    f"{removed_count:,}"
)

print()

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print()

print("Legend:")
print("  Green = retained possible-empty terrain")
print("  Red   = removed because of Overture building evidence")

print("=" * 76)