from pathlib import Path

import geopandas as gpd
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

BUILDINGS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "buildings"
    / "bhadra_overture_buildings.geojson"
)

OUTPUT_PATH = (
    BASE_DIR
    / "bhadra_overture_building_overlay.png"
)


# ============================================================
# READ RGB
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
# LOAD BUILDINGS
# ============================================================

buildings = gpd.read_file(
    BUILDINGS_PATH
)

if buildings.crs is None:
    buildings = buildings.set_crs(
        4326
    )

buildings = buildings.to_crs(
    raster_crs
)


print("=" * 72)
print("HELPSs — OVERTURE BUILDING OVERLAY")
print("=" * 72)

print(
    f"Buildings loaded : "
    f"{len(buildings):,}"
)

print(
    f"Raster CRS       : "
    f"{raster_crs}"
)

print()


# ============================================================
# VISUALIZE
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


# Overture footprint outlines
buildings.boundary.plot(
    ax=ax,
    linewidth=0.35,
    alpha=0.8,
)


ax.set_title(
    "HELPSs — Overture Building Footprints over Sentinel-2\n"
    f"{DATE}"
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


print(
    f"Saved overlay:\n"
    f"{OUTPUT_PATH}"
)

print("=" * 72)