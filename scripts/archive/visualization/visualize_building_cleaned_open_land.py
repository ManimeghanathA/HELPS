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

RAW_OPEN_PATH = (
    BASE_DIR
    / "bhadra_sentinel_open_components.gpkg"
)

CLEANED_OPEN_PATH = (
    BASE_DIR
    / "bhadra_open_components_buildings_removed.gpkg"
)

BUILDINGS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "buildings"
    / "bhadra_overture_buildings_in_possible_open.geojson"
)

OUTPUT_PATH = (
    BASE_DIR
    / "bhadra_open_land_before_after_buildings.png"
)


print("=" * 80)
print("HELPSs — BUILDING-CLEANED OPEN-LAND VISUALIZATION")
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
# LOAD VECTOR DATA
# ============================================================

raw_open = gpd.read_file(
    RAW_OPEN_PATH,
    layer="sentinel_open_components",
)

cleaned_open = gpd.read_file(
    CLEANED_OPEN_PATH,
    layer="building_cleaned_open_land",
)

buildings = gpd.read_file(
    BUILDINGS_PATH
)


if raw_open.crs != raster_crs:

    raw_open = raw_open.to_crs(
        raster_crs
    )


if cleaned_open.crs != raster_crs:

    cleaned_open = cleaned_open.to_crs(
        raster_crs
    )


if buildings.crs != raster_crs:

    buildings = buildings.to_crs(
        raster_crs
    )


print(
    f"Raw Sentinel components       : "
    f"{len(raw_open):,}"
)

print(
    f"Building-cleaned fragments    : "
    f"{len(cleaned_open):,}"
)

print(
    f"Relevant Overture buildings   : "
    f"{len(buildings):,}"
)


# ============================================================
# CREATE COMPARISON
# ============================================================

fig, axes = plt.subplots(
    1,
    2,
    figsize=(22, 13),
)


extent = [
    bounds.left,
    bounds.right,
    bounds.bottom,
    bounds.top,
]


# ============================================================
# LEFT — BEFORE BUILDING SUBTRACTION
# ============================================================

axes[0].imshow(
    rgb_display,
    extent=extent,
    origin="upper",
)


raw_open.plot(
    ax=axes[0],
    facecolor="lime",
    edgecolor="none",
    alpha=0.35,
)


buildings.plot(
    ax=axes[0],
    facecolor="red",
    edgecolor="red",
    linewidth=0.15,
    alpha=0.75,
)


axes[0].set_title(
    "BEFORE BUILDING SUBTRACTION\n"
    "Green = Sentinel possible-open | "
    "Red = building footprints"
)


# ============================================================
# RIGHT — AFTER BUILDING SUBTRACTION
# ============================================================

axes[1].imshow(
    rgb_display,
    extent=extent,
    origin="upper",
)


cleaned_open.plot(
    ax=axes[1],
    facecolor="lime",
    edgecolor="none",
    alpha=0.35,
)


# Draw buildings again so we can verify the holes
buildings.boundary.plot(
    ax=axes[1],
    edgecolor="red",
    linewidth=0.25,
    alpha=0.9,
)


axes[1].set_title(
    "AFTER VECTOR BUILDING SUBTRACTION\n"
    "Green = remaining open surface | "
    "Red = removed building footprint"
)


# ============================================================
# MATCH VIEW
# ============================================================

for ax in axes:

    ax.set_xlim(
        bounds.left,
        bounds.right,
    )

    ax.set_ylim(
        bounds.bottom,
        bounds.top,
    )

    ax.set_xlabel(
        "Easting (m)"
    )

    ax.set_ylabel(
        "Northing (m)"
    )


plt.suptitle(
    "HELPSs — Sentinel Open Land vs Building-Cleaned Open Land",
    fontsize=16,
)


plt.tight_layout()


# ============================================================
# SAVE
# ============================================================

plt.savefig(
    OUTPUT_PATH,
    dpi=220,
    bbox_inches="tight",
)

plt.close()


# ============================================================
# REPORT
# ============================================================

raw_area = (
    raw_open.geometry.area.sum()
    / 1_000_000
)

clean_area = (
    cleaned_open.geometry.area.sum()
    / 1_000_000
)


print()
print("=" * 80)
print("VISUALIZATION SUMMARY")
print("=" * 80)

print(
    f"Open area before buildings : "
    f"{raw_area:.3f} km²"
)

print(
    f"Open area after buildings  : "
    f"{clean_area:.3f} km²"
)

print(
    f"Building area removed      : "
    f"{raw_area - clean_area:.3f} km²"
)

print()

print(
    f"Saved:\n{OUTPUT_PATH}"
)

print("=" * 80)