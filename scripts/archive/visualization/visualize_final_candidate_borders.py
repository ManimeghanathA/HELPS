from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio


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

SPECTRAL_PATH = (
    BASE_DIR
    / "bhadra_spectral.tif"
)

SCL_PATH = (
    BASE_DIR
    / "bhadra_scl.tif"
)

CANDIDATE_PATH = (
    BASE_DIR
    / "bhadra_candidate_open_lands.gpkg"
)

OUTPUT_PATH = (
    BASE_DIR
    / "bhadra_final_candidate_borders.png"
)


print("=" * 80)
print("HELPSs — FINAL CANDIDATE OPEN-LAND BORDERS")
print("=" * 80)


# ============================================================
# LOAD SENTINEL RGB
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:

    blue = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    red = src.read(3).astype(np.float32)

    bounds = src.bounds
    raster_crs = src.crs


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


inside_aoi = scl != 0


# ============================================================
# BUILD RGB DISPLAY
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

    valid = (
        inside_aoi
        & np.isfinite(band)
        & (band >= 0)
    )

    values = band[valid]

    low = np.percentile(
        values,
        1,
    )

    high = np.percentile(
        values,
        99,
    )

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
# LOAD FINAL CANDIDATES
# ============================================================

candidates = gpd.read_file(
    CANDIDATE_PATH,
    layer="candidate_open_lands",
)


if candidates.crs != raster_crs:

    candidates = candidates.to_crs(
        raster_crs
    )


print(
    f"Final candidate polygons : "
    f"{len(candidates):,}"
)

print(
    f"Total candidate area     : "
    f"{candidates.geometry.area.sum() / 1_000_000:.3f} km²"
)


# ============================================================
# VISUALIZE
# ============================================================

fig, ax = plt.subplots(
    figsize=(13, 15)
)


extent = [
    bounds.left,
    bounds.right,
    bounds.bottom,
    bounds.top,
]


ax.imshow(
    rgb_display,
    extent=extent,
    origin="upper",
)


# ============================================================
# DRAW ONLY CANDIDATE BORDERS
# ============================================================

candidates.boundary.plot(
    ax=ax,
    linewidth=0.55,
    alpha=0.95,
)


ax.set_xlim(
    bounds.left,
    bounds.right,
)

ax.set_ylim(
    bounds.bottom,
    bounds.top,
)


ax.set_title(
    "HELPSs — Final Candidate Open Lands\n"
    f"{DATE} | {len(candidates):,} candidates"
)

ax.set_xlabel(
    "Easting (m)"
)

ax.set_ylabel(
    "Northing (m)"
)


plt.tight_layout()


# ============================================================
# SAVE
# ============================================================

plt.savefig(
    OUTPUT_PATH,
    dpi=260,
    bbox_inches="tight",
)

plt.close()


print()
print("=" * 80)
print("VISUALIZATION COMPLETE")
print("=" * 80)

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print()
print(
    "Each visible boundary represents one final "
    "candidate open-land polygon."
)

print("=" * 80)