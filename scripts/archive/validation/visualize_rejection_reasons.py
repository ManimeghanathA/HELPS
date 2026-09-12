from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio

from rasterio.features import rasterize
from matplotlib.colors import ListedColormap


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATE = "2026-06-01"

BASE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "sentinel2"
    / DATE
)

SPECTRAL_PATH = BASE / "bhadra_spectral.tif"
SCL_PATH = BASE / "bhadra_scl.tif"
OPEN_MASK_PATH = BASE / "bhadra_possible_open_mask_v2.tif"
FINAL_ZONE_PATH = BASE / "bhadra_final_open_land_zones.gpkg"

OUTPUT_PATH = BASE / "bhadra_rejection_reason_map.png"


# ============================================================
# LOAD RASTERS
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:

    blue = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    red = src.read(3).astype(np.float32)
    nir = src.read(4).astype(np.float32)
    swir1 = src.read(5).astype(np.float32)

    transform = src.transform
    crs = src.crs
    bounds = src.bounds


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


with rasterio.open(OPEN_MASK_PATH) as src:
    state = src.read(1)


# ============================================================
# INDICES
# ============================================================

ndvi_den = nir + red

ndvi = np.zeros_like(red)

valid = np.abs(ndvi_den) > 1e-8

ndvi[valid] = (
    nir[valid] - red[valid]
) / ndvi_den[valid]


mndwi_den = green + swir1

mndwi = np.zeros_like(green)

valid = np.abs(mndwi_den) > 1e-8

mndwi[valid] = (
    green[valid] - swir1[valid]
) / mndwi_den[valid]


# ============================================================
# FINAL ZONES → RASTER
# ============================================================

zones = gpd.read_file(
    FINAL_ZONE_PATH,
    layer="final_open_land_zones",
)

if zones.crs != crs:
    zones = zones.to_crs(crs)


final_mask = rasterize(
    [
        (geom, 1)
        for geom in zones.geometry
        if geom is not None
        and not geom.is_empty
    ],
    out_shape=scl.shape,
    transform=transform,
    fill=0,
    dtype="uint8",
)


# ============================================================
# REJECTION CLASSES
# ============================================================

# 0 = outside / unused
# 1 = UNKNOWN
# 2 = WATER-LIKE
# 3 = HIGH VEGETATION
# 4 = OTHER NOT-OPEN
# 5 = POSSIBLE OPEN BUT LOST LATER
# 6 = FINAL ZONE

reason = np.zeros_like(
    scl,
    dtype=np.uint8,
)


inside_aoi = (
    scl != 0
)


# UNKNOWN from actual detector
reason[
    inside_aoi
    & (state == 255)
] = 1


# Water / water-like
water_like = (
    inside_aoi
    & (state == 0)
    & (
        (scl == 6)
        | (mndwi >= 0)
    )
)

reason[
    water_like
] = 2


# Vegetation rejected
vegetation_rejected = (
    inside_aoi
    & (state == 0)
    & ~water_like
    & (ndvi > 0.50)
)

reason[
    vegetation_rejected
] = 3


# Remaining NOT_OPEN
other_not_open = (
    inside_aoi
    & (state == 0)
    & (reason == 0)
)

reason[
    other_not_open
] = 4


# Sentinel considered open, but it did not survive
# buildings / geometry / clearance / MIC
possible_but_not_final = (
    (state == 1)
    & (final_mask == 0)
)

reason[
    possible_but_not_final
] = 5


# Final accepted zone
reason[
    final_mask == 1
] = 6


# ============================================================
# PRINT COUNTS
# ============================================================

labels = {
    1: "UNKNOWN / cloud uncertainty",
    2: "Water-like",
    3: "High vegetation",
    4: "Other NOT_OPEN",
    5: "Possible-open but rejected later",
    6: "Final zone",
}


print("=" * 80)
print("HELPSs — REJECTION REASON MAP")
print("=" * 80)

for value, label in labels.items():

    count = np.count_nonzero(
    inside_aoi
    & (reason == value)
    )

    print(
        f"{label:<35}: "
        f"{count:,} pixels "
        f"({count * 100 / np.count_nonzero(inside_aoi):.2f}%)"
    )


# ============================================================
# VISUALIZE
# ============================================================

cmap = ListedColormap([
    "black",
    "gray",
    "blue",
    "green",
    "purple",
    "orange",
    "cyan",
])


fig, ax = plt.subplots(
    figsize=(13, 16)
)


extent = [
    bounds.left,
    bounds.right,
    bounds.bottom,
    bounds.top,
]


ax.imshow(
    reason,
    cmap=cmap,
    vmin=0,
    vmax=6,
    extent=extent,
    origin="upper",
)


ax.set_title(
    "HELPSs — Why Terrain Was Rejected\n"
    "2026-06-01"
)

ax.set_xlabel("Easting (m)")
ax.set_ylabel("Northing (m)")


legend_text = (
    "Gray   = UNKNOWN / cloud\n"
    "Blue   = water-like\n"
    "Green  = NDVI > 0.50\n"
    "Purple = other NOT_OPEN\n"
    "Orange = Sentinel-open but rejected later\n"
    "Cyan   = final zone"
)


ax.text(
    0.02,
    0.02,
    legend_text,
    transform=ax.transAxes,
    fontsize=10,
    verticalalignment="bottom",
    bbox=dict(
        boxstyle="round",
        alpha=0.8,
    ),
)


plt.tight_layout()

plt.savefig(
    OUTPUT_PATH,
    dpi=250,
    bbox_inches="tight",
)

plt.close()


print()
print(f"Saved: {OUTPUT_PATH}")
print("=" * 80)