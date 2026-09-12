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

POSSIBLE_PATH = (
    BASE_DIR
    / "bhadra_possible_open_mask_v2.tif"
)

EMPTY_PATH = (
    BASE_DIR
    / "bhadra_empty_land_mask.tif"
)

OUTPUT_PATH = (
    BASE_DIR
    / "bhadra_empty_land_overlay.png"
)


# ============================================================
# LOAD DATA
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:

    blue = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    red = src.read(3).astype(np.float32)

    bounds = src.bounds


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


with rasterio.open(POSSIBLE_PATH) as src:
    possible = src.read(1)


with rasterio.open(EMPTY_PATH) as src:
    empty = src.read(1)


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
# MASKS
# ============================================================

remaining = (
    empty == 1
)

removed_by_osm = (
    (possible == 1)
    & (empty == 0)
)


# ============================================================
# OVERLAY
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


# GREEN = still considered empty
remaining_overlay = np.zeros(
    (*empty.shape, 4),
    dtype=np.float32,
)

remaining_overlay[
    remaining,
    1,
] = 1.0

remaining_overlay[
    remaining,
    3,
] = 0.50


ax.imshow(
    remaining_overlay,
    extent=[
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top,
    ],
    origin="upper",
)


# RED = Sentinel proposed it, but OSM removed it
removed_overlay = np.zeros(
    (*empty.shape, 4),
    dtype=np.float32,
)

removed_overlay[
    removed_by_osm,
    0,
] = 1.0

removed_overlay[
    removed_by_osm,
    3,
] = 0.70


ax.imshow(
    removed_overlay,
    extent=[
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top,
    ],
    origin="upper",
)


ax.set_title(
    "HELPSs — Sentinel + OSM Empty-Land Refinement\n"
    "Green = retained | Red = removed using OSM"
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


# ============================================================
# SUMMARY
# ============================================================

remaining_count = np.count_nonzero(
    remaining
)

removed_count = np.count_nonzero(
    removed_by_osm
)


print("=" * 72)
print("HELPSs — EMPTY LAND VISUAL VALIDATION")
print("=" * 72)

print(
    f"Remaining empty pixels : "
    f"{remaining_count:,}"
)

print(
    f"Removed by OSM         : "
    f"{removed_count:,}"
)

print()

print("Green = retained possible empty terrain")
print("Red   = Sentinel candidate removed by OSM")

print()

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print("=" * 72)