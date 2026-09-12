from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio

from rasterio.features import shapes
from shapely.geometry import shape


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

OVERVIEW_OUTPUT = (
    BASE_DIR
    / "bhadra_cloud_candidate_diagnostic.png"
)

ZOOM_OUTPUT = (
    BASE_DIR
    / "bhadra_cloud_candidate_diagnostic_zooms.png"
)


# Sentinel-2 SCL cloud / shadow classes
CLOUD_CLASSES = {
    3,   # cloud shadow
    8,   # cloud medium probability
    9,   # cloud high probability
    10,  # thin cirrus
}


print("=" * 84)
print("HELPSs — CLOUD / CANDIDATE DIAGNOSTIC")
print("=" * 84)


# ============================================================
# LOAD SENTINEL
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:

    blue = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    red = src.read(3).astype(np.float32)

    bounds = src.bounds
    raster_crs = src.crs
    transform = src.transform


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


inside_aoi = (
    scl != 0
)


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
# LOAD FINAL ZONES
# ============================================================

zones = gpd.read_file(
    ZONE_PATH,
    layer="final_open_land_zones",
)

if zones.crs != raster_crs:

    zones = zones.to_crs(
        raster_crs
    )


# ============================================================
# CLOUD MASK
# ============================================================

cloud_mask = np.isin(
    scl,
    list(CLOUD_CLASSES),
)


cloud_overlay = np.zeros(
    (*cloud_mask.shape, 4),
    dtype=np.float32,
)

# Red overlay
cloud_overlay[
    cloud_mask,
    0,
] = 1.0

cloud_overlay[
    cloud_mask,
    3,
] = 0.48


extent = [
    bounds.left,
    bounds.right,
    bounds.bottom,
    bounds.top,
]


# ============================================================
# OVERVIEW
# ============================================================

fig, ax = plt.subplots(
    figsize=(14, 16)
)


ax.imshow(
    rgb_display,
    extent=extent,
    origin="upper",
)


ax.imshow(
    cloud_overlay,
    extent=extent,
    origin="upper",
)


zones.boundary.plot(
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
    "HELPSs — Cloud Diagnostic\n"
    "Red = SCL cloud/shadow | Blue = final open-land zones"
)

ax.set_xlabel(
    "Easting (m)"
)

ax.set_ylabel(
    "Northing (m)"
)


plt.tight_layout()

plt.savefig(
    OVERVIEW_OUTPUT,
    dpi=280,
    bbox_inches="tight",
)

plt.close()


# ============================================================
# FIND LARGEST CLOUD COMPONENTS
# ============================================================

cloud_binary = cloud_mask.astype(
    np.uint8
)

cloud_polygons = []


for geom, value in shapes(
    cloud_binary,
    mask=cloud_mask,
    transform=transform,
    connectivity=8,
):

    if int(value) != 1:
        continue

    polygon = shape(
        geom
    )

    if polygon.is_empty:
        continue

    cloud_polygons.append(
        polygon
    )


cloud_gdf = gpd.GeoDataFrame(
    geometry=cloud_polygons,
    crs=raster_crs,
)

cloud_gdf["area_m2"] = (
    cloud_gdf.geometry.area
)


largest_clouds = (
    cloud_gdf
    .sort_values(
        "area_m2",
        ascending=False,
    )
    .head(6)
    .reset_index(drop=True)
)


print(
    f"Cloud components found : "
    f"{len(cloud_gdf):,}"
)

print(
    f"Zooming largest        : "
    f"{len(largest_clouds):,}"
)


# ============================================================
# CLOUD ZOOMS
# ============================================================

fig, axes = plt.subplots(
    2,
    3,
    figsize=(18, 12),
)

axes = axes.flatten()


for i, ax in enumerate(axes):

    if i >= len(largest_clouds):

        ax.axis("off")
        continue


    cloud_geom = (
        largest_clouds.geometry.iloc[i]
    )

    minx, miny, maxx, maxy = (
        cloud_geom.bounds
    )


    # Add context around cloud
    padding = max(
        500.0,
        0.35 * max(
            maxx - minx,
            maxy - miny,
        ),
    )


    zoom_minx = minx - padding
    zoom_maxx = maxx + padding
    zoom_miny = miny - padding
    zoom_maxy = maxy + padding


    ax.imshow(
        rgb_display,
        extent=extent,
        origin="upper",
    )


    ax.imshow(
        cloud_overlay,
        extent=extent,
        origin="upper",
    )


    zones.boundary.plot(
        ax=ax,
        linewidth=0.8,
        alpha=0.95,
    )


    ax.set_xlim(
        zoom_minx,
        zoom_maxx,
    )

    ax.set_ylim(
        zoom_miny,
        zoom_maxy,
    )


    ax.set_title(
        f"Cloud region {i + 1}\n"
        f"SCL cloud area "
        f"{largest_clouds['area_m2'].iloc[i] / 1_000_000:.3f} km²"
    )


plt.suptitle(
    "HELPSs — Largest SCL Cloud Regions\n"
    "Look for visible white cloud outside the red mask",
    fontsize=16,
)


plt.tight_layout()

plt.savefig(
    ZOOM_OUTPUT,
    dpi=240,
    bbox_inches="tight",
)

plt.close()


# ============================================================
# SUMMARY
# ============================================================

cloud_pixels = np.count_nonzero(
    cloud_mask
)

cloud_area_km2 = (
    cloud_pixels
    * abs(
        transform.a
        * transform.e
    )
    / 1_000_000
)


print()
print("=" * 84)
print("CLOUD DIAGNOSTIC COMPLETE")
print("=" * 84)

print(
    f"SCL cloud/shadow pixels : "
    f"{cloud_pixels:,}"
)

print(
    f"SCL cloud/shadow area   : "
    f"{cloud_area_km2:.3f} km²"
)

print()

print(
    f"Overview:\n{OVERVIEW_OUTPUT}"
)

print()

print(
    f"Zooms:\n{ZOOM_OUTPUT}"
)

print()
print(
    "Interpretation:"
)

print(
    "  Red correctly covering visible cloud "
    "= SCL working there."
)

print(
    "  Visible white cloud outside red "
    "= possible SCL miss / contamination."
)

print(
    "  Blue zone crossing visible unmasked cloud "
    "= candidate problem requiring detector correction."
)

print("=" * 84)