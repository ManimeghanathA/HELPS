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

ZONE_PATH = (
    BASE_DIR
    / "bhadra_final_open_land_zones.gpkg"
)

OUTPUT_PATH = (
    BASE_DIR
    / "bhadra_final_open_land_zones.png"
)


# ============================================================
# RGB
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:

    blue = src.read(1).astype(
        np.float32
    )

    green = src.read(2).astype(
        np.float32
    )

    red = src.read(3).astype(
        np.float32
    )

    bounds = src.bounds
    raster_crs = src.crs


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


inside_aoi = (
    scl != 0
)


rgb = np.stack(
    [
        red,
        green,
        blue,
    ],
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

    rgb_display[:, :, channel] = (
        stretched
    )


rgb_display[~inside_aoi] = 0


# ============================================================
# FINAL ZONES + MIC CENTERS
# ============================================================

zones = gpd.read_file(
    ZONE_PATH,
    layer="final_open_land_zones",
)

centers = gpd.read_file(
    ZONE_PATH,
    layer="maximum_clearance_centers",
)


if zones.crs != raster_crs:

    zones = zones.to_crs(
        raster_crs
    )


if centers.crs != raster_crs:

    centers = centers.to_crs(
        raster_crs
    )


# ============================================================
# DRAW
# ============================================================

fig, ax = plt.subplots(
    figsize=(14, 16)
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


# Final zone borders only
zones.boundary.plot(
    ax=ax,
    linewidth=0.55,
    alpha=0.95,
)


# Small MIC center markers
centers.plot(
    ax=ax,
    markersize=2,
    alpha=0.75,
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
    "HELPSs — Final Single-Date Open-Land Zones\n"
    f"{DATE} | {len(zones):,} independent zones"
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
    dpi=280,
    bbox_inches="tight",
)

plt.close()


print("=" * 84)
print("HELPSs — FINAL ZONE VISUALIZATION")
print("=" * 84)

print(
    f"Zones              : "
    f"{len(zones):,}"
)

print(
    f"MIC centers        : "
    f"{len(centers):,}"
)

print(
    f"Total zone area    : "
    f"{zones.geometry.area.sum() / 1_000_000:.3f} km²"
)

print()

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print("=" * 84)