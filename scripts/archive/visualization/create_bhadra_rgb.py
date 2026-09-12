from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import matplotlib.pyplot as plt


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

AOI_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_entire_region.geojson"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "sentinel2"
    / DATE
    / "bhadra_rgb_preview.png"
)


with rasterio.open(SPECTRAL_PATH) as src:

    blue = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    red = src.read(3).astype(np.float32)

    bounds = src.bounds
    raster_crs = src.crs


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


# Real AOI / valid Sentinel pixels only
valid_mask = scl != 0


rgb = np.stack(
    [red, green, blue],
    axis=-1
)


rgb_stretched = np.zeros_like(
    rgb,
    dtype=np.float32
)


for channel in range(3):

    band = rgb[:, :, channel]

    values = band[
        valid_mask
        & np.isfinite(band)
        & (band >= 0)
    ]

    if values.size == 0:
        continue

    # Slightly tighter stretch for natural-looking RGB
    low = np.percentile(values, 1)
    high = np.percentile(values, 99)

    stretched = (
        (band - low)
        / (high - low)
    )

    stretched = np.clip(
        stretched,
        0,
        1
    )

    # Optional gamma adjustment
    stretched = np.power(
        stretched,
        0.8
    )

    rgb_stretched[:, :, channel] = stretched


# Everything outside valid Bhadra pixels -> black
rgb_stretched[~valid_mask] = 0


aoi = gpd.read_file(
    AOI_PATH
).to_crs(
    raster_crs
)


fig, ax = plt.subplots(
    figsize=(10, 12)
)

ax.imshow(
    rgb_stretched,
    extent=[
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top,
    ],
    origin="upper"
)

aoi.boundary.plot(
    ax=ax,
    linewidth=1.0
)

ax.set_title(
    f"Bhadra Sentinel-2 L2A RGB Preview\n{DATE}"
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
    bbox_inches="tight"
)

plt.close()


print("=" * 70)
print("BHADRA RGB PREVIEW CREATED")
print("=" * 70)
print(f"Date   : {DATE}")
print(f"Output : {OUTPUT_PATH}")
print("=" * 70)