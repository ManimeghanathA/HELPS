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

V1_PATH = BASE_DIR / "bhadra_open_mask.tif"
V2_PATH = BASE_DIR / "bhadra_possible_open_mask_v2.tif"

OUTPUT_PATH = BASE_DIR / "bhadra_v1_v2_comparison.png"


# ============================================================
# READ RGB
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:
    blue = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    red = src.read(3).astype(np.float32)

    bounds = src.bounds


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


with rasterio.open(V1_PATH) as src:
    v1 = src.read(1)


with rasterio.open(V2_PATH) as src:
    v2 = src.read(1)


inside_aoi = scl != 0


# ============================================================
# RGB STRETCH
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

v1_open = v1 == 1
v2_open = v2 == 1

new_in_v2 = (
    v2_open
    & ~v1_open
)

common = (
    v1_open
    & v2_open
)


print("=" * 72)
print("HELPSs — V1 VS V2 COMPARISON")
print("=" * 72)

print(
    f"V1 open pixels        : "
    f"{np.count_nonzero(v1_open & inside_aoi):,}"
)

print(
    f"V2 possible-open      : "
    f"{np.count_nonzero(v2_open & inside_aoi):,}"
)

print(
    f"Common V1 + V2        : "
    f"{np.count_nonzero(common & inside_aoi):,}"
)

print(
    f"New pixels added V2   : "
    f"{np.count_nonzero(new_in_v2 & inside_aoi):,}"
)

print("=" * 72)


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
# COMMON V1 + V2
#
# Green = areas both detectors agree on
# ------------------------------------------------------------

common_overlay = np.zeros(
    (
        v1.shape[0],
        v1.shape[1],
        4,
    ),
    dtype=np.float32,
)

common_overlay[
    common,
    1,
] = 1.0

common_overlay[
    common,
    3,
] = 0.55


ax.imshow(
    common_overlay,
    extent=[
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top,
    ],
    origin="upper",
)


# ------------------------------------------------------------
# NEW V2 AREAS
#
# Red = areas added only by broader V2
# ------------------------------------------------------------

new_overlay = np.zeros(
    (
        v1.shape[0],
        v1.shape[1],
        4,
    ),
    dtype=np.float32,
)

new_overlay[
    new_in_v2,
    0,
] = 1.0

new_overlay[
    new_in_v2,
    3,
] = 0.55


ax.imshow(
    new_overlay,
    extent=[
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top,
    ],
    origin="upper",
)


ax.set_title(
    "HELPSs — V1 vs V2 Possible Open Terrain\n"
    "Green = V1 + V2 agreement | Red = newly added by V2"
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


print(
    f"Saved comparison:\n{OUTPUT_PATH}"
)