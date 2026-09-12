from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.mask import mask


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATE = "2026-06-01"

AOI_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_entire_region.geojson"
)

RAW_TILE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Sentinel2"
    / DATE
    / "tiles"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "sentinel2"
    / DATE
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SPECTRAL_OUTPUT = OUTPUT_DIR / "bhadra_spectral.tif"
SCL_OUTPUT = OUTPUT_DIR / "bhadra_scl.tif"


# ============================================================
# CHECK INPUTS
# ============================================================

if not AOI_PATH.exists():
    raise FileNotFoundError(
        f"AOI file not found:\n{AOI_PATH}"
    )

if not RAW_TILE_DIR.exists():
    raise FileNotFoundError(
        f"Sentinel tile folder not found:\n{RAW_TILE_DIR}"
    )


# ============================================================
# LOAD AOI
# ============================================================

aoi = gpd.read_file(AOI_PATH)

if aoi.crs is None:
    raise ValueError("Bhadra AOI has no CRS.")


# ============================================================
# FIND TILES
# ============================================================

spectral_tiles = sorted(
    RAW_TILE_DIR.glob("*_spectral.tif")
)

scl_tiles = sorted(
    RAW_TILE_DIR.glob("*_SCL.tif")
)


print("=" * 72)
print("BHADRA SENTINEL-2 PREPARATION")
print("=" * 72)

print(f"Date           : {DATE}")
print(f"AOI            : {AOI_PATH.name}")
print(f"Spectral tiles : {len(spectral_tiles)}")
print(f"SCL tiles      : {len(scl_tiles)}")


if not spectral_tiles:
    raise RuntimeError(
        "No spectral tiles found."
    )

if not scl_tiles:
    raise RuntimeError(
        "No SCL tiles found."
    )


# ============================================================
# HELPER: MOSAIC + CLIP
# ============================================================

def mosaic_and_clip(
    tile_paths,
    output_path,
    is_scl=False,
):

    print()
    print("-" * 72)
    print(
        f"Preparing {'SCL' if is_scl else 'spectral'} raster..."
    )
    print("-" * 72)

    sources = [
        rasterio.open(path)
        for path in tile_paths
    ]

    try:

        # ----------------------------------------------------
        # MOSAIC
        # ----------------------------------------------------

        mosaic_data, mosaic_transform = merge(
            sources
        )

        reference = sources[0]

        mosaic_meta = reference.meta.copy()

        mosaic_meta.update(
            {
                "height": mosaic_data.shape[1],
                "width": mosaic_data.shape[2],
                "transform": mosaic_transform,
                "compress": "deflate",
            }
        )

        raster_crs = reference.crs

        print(
            f"Mosaic size    : "
            f"{mosaic_data.shape[2]} x "
            f"{mosaic_data.shape[1]}"
        )

        print(
            f"Mosaic bands   : "
            f"{mosaic_data.shape[0]}"
        )

        print(
            f"Mosaic CRS     : "
            f"{raster_crs}"
        )

        # ----------------------------------------------------
        # AOI TO RASTER CRS
        # ----------------------------------------------------

        aoi_raster_crs = aoi.to_crs(
            raster_crs
        )

        geometries = [
            geom.__geo_interface__
            for geom in aoi_raster_crs.geometry
            if geom is not None
            and not geom.is_empty
        ]

        # ----------------------------------------------------
        # WRITE TEMP MOSAIC
        # ----------------------------------------------------

        temp_path = (
            OUTPUT_DIR
            / (
                "temp_scl_mosaic.tif"
                if is_scl
                else "temp_spectral_mosaic.tif"
            )
        )

        with rasterio.open(
            temp_path,
            "w",
            **mosaic_meta,
        ) as dst:

            dst.write(
                mosaic_data
            )

        # ----------------------------------------------------
        # CLIP TO EXACT BHADRA POLYGON
        # ----------------------------------------------------

        with rasterio.open(
            temp_path
        ) as src:

            clipped_data, clipped_transform = mask(
                src,
                geometries,
                crop=True,
                filled=True,
            )

            clipped_meta = src.meta.copy()

            clipped_meta.update(
                {
                    "height": clipped_data.shape[1],
                    "width": clipped_data.shape[2],
                    "transform": clipped_transform,
                    "compress": "deflate",
                }
            )

            with rasterio.open(
                output_path,
                "w",
                **clipped_meta,
            ) as dst:

                dst.write(
                    clipped_data
                )

        # ----------------------------------------------------
        # REMOVE TEMP FILE
        # ----------------------------------------------------

        if temp_path.exists():
            temp_path.unlink()

        print(
            f"Final size     : "
            f"{clipped_data.shape[2]} x "
            f"{clipped_data.shape[1]}"
        )

        print(
            f"Saved          : "
            f"{output_path}"
        )

    finally:

        for src in sources:
            src.close()


# ============================================================
# PREPARE SPECTRAL
# ============================================================

mosaic_and_clip(
    spectral_tiles,
    SPECTRAL_OUTPUT,
    is_scl=False,
)


# ============================================================
# PREPARE SCL
# ============================================================

mosaic_and_clip(
    scl_tiles,
    SCL_OUTPUT,
    is_scl=True,
)


# ============================================================
# SCL QUALITY ANALYSIS
# ============================================================

print()
print("=" * 72)
print("SCL QUALITY ANALYSIS")
print("=" * 72)


# Sentinel-2 SCL classes
SCL_CLASSES = {
    0: "No Data",
    1: "Saturated / defective",
    2: "Topographic shadow",
    3: "Cloud shadow",
    4: "Vegetation",
    5: "Bare / non-vegetated",
    6: "Water",
    7: "Unclassified",
    8: "Cloud medium probability",
    9: "Cloud high probability",
    10: "Thin cirrus",
    11: "Snow / ice",
}


with rasterio.open(
    SCL_OUTPUT
) as src:

    scl = src.read(1)

    unique_values, counts = np.unique(
        scl,
        return_counts=True,
    )

    total_pixels = scl.size

    print(
        f"Total raster pixels : "
        f"{total_pixels:,}"
    )

    print()

    for value, count in zip(
        unique_values,
        counts,
    ):

        label = SCL_CLASSES.get(
            int(value),
            "Unknown",
        )

        percentage = (
            count
            / total_pixels
            * 100
        )

        print(
            f"SCL {int(value):2d} "
            f"{label:<28} "
            f"{count:>10,} "
            f"{percentage:>7.2f}%"
        )


# ============================================================
# COMPUTE USABLE / CLOUD FRACTIONS
# ============================================================

with rasterio.open(
    SCL_OUTPUT
) as src:

    scl = src.read(1)

    valid_mask = scl != 0

    valid_pixels = np.count_nonzero(
        valid_mask
    )

    # Cloud-related SCL classes
    cloud_mask = np.isin(
        scl,
        [3, 8, 9, 10],
    )

    cloud_pixels = np.count_nonzero(
        cloud_mask
    )

    usable_mask = (
        valid_mask
        & ~cloud_mask
    )

    usable_pixels = np.count_nonzero(
        usable_mask
    )


print()
print("-" * 72)

print(
    f"Valid pixels  : "
    f"{valid_pixels:,}"
)

print(
    f"Cloud/shadow  : "
    f"{cloud_pixels:,}"
)

print(
    f"Usable pixels : "
    f"{usable_pixels:,}"
)

if valid_pixels > 0:

    cloud_percent = (
        cloud_pixels
        / valid_pixels
        * 100
    )

    usable_percent = (
        usable_pixels
        / valid_pixels
        * 100
    )

    print(
        f"Cloud fraction: "
        f"{cloud_percent:.2f}%"
    )

    print(
        f"Usable fraction: "
        f"{usable_percent:.2f}%"
    )


# ============================================================
# FINAL SUMMARY
# ============================================================

print()
print("=" * 72)
print("SENTINEL PREPARATION COMPLETE")
print("=" * 72)

print()
print("Outputs:")

print(
    f"  Spectral : "
    f"{SPECTRAL_OUTPUT}"
)

print(
    f"  SCL      : "
    f"{SCL_OUTPUT}"
)

print()

print(
    "Spectral band order:"
)

print(
    "  1 = B02\n"
    "  2 = B03\n"
    "  3 = B04\n"
    "  4 = B08\n"
    "  5 = B11\n"
    "  6 = B12"
)