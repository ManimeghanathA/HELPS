from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import (
    calculate_default_transform,
    reproject,
    Resampling,
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DEM = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "DEM"
    / "N13E075.tif"
)

AOI_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_valid_region.geojson"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "dem"
)

CLIPPED_DEM = OUTPUT_DIR / "bhadra_srtm_clipped.tif"

PROJECTED_DEM = OUTPUT_DIR / "bhadra_srtm_utm43n.tif"

TARGET_CRS = "EPSG:32643"


# ---------------------------------------------------------
# Setup
# ---------------------------------------------------------

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if not RAW_DEM.exists():
    raise FileNotFoundError(f"DEM not found: {RAW_DEM}")

if not AOI_FILE.exists():
    raise FileNotFoundError(f"AOI not found: {AOI_FILE}")


print("=" * 65)
print("BHADRA DEM PREPARATION")
print("=" * 65)


# ---------------------------------------------------------
# 1. Load AOI
# ---------------------------------------------------------

aoi = gpd.read_file(AOI_FILE)

if aoi.crs is None:
    raise ValueError("AOI has no CRS.")

print(f"\nAOI features : {len(aoi)}")
print(f"AOI CRS      : {aoi.crs}")


# ---------------------------------------------------------
# 2. Clip raw SRTM to AOI
# ---------------------------------------------------------

print("\n[1/2] Clipping SRTM to Bhadra AOI...")

with rasterio.open(RAW_DEM) as src:

    # Ensure AOI uses same CRS as raster
    aoi_dem_crs = aoi.to_crs(src.crs)

    geometries = [
        geom.__geo_interface__
        for geom in aoi_dem_crs.geometry
        if geom is not None and not geom.is_empty
    ]

    clipped_data, clipped_transform = mask(
        src,
        geometries,
        crop=True,
        nodata=src.nodata,
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
        CLIPPED_DEM,
        "w",
        **clipped_meta
    ) as dst:
        dst.write(clipped_data)


print(f"Saved: {CLIPPED_DEM}")


# ---------------------------------------------------------
# 3. Reproject clipped DEM to UTM 43N
# ---------------------------------------------------------

print("\n[2/2] Reprojecting to EPSG:32643...")

with rasterio.open(CLIPPED_DEM) as src:

    transform, width, height = calculate_default_transform(
        src.crs,
        TARGET_CRS,
        src.width,
        src.height,
        *src.bounds,
    )

    projected_meta = src.meta.copy()

    projected_meta.update(
        {
            "crs": TARGET_CRS,
            "transform": transform,
            "width": width,
            "height": height,
            "compress": "deflate",
        }
    )

    with rasterio.open(
        PROJECTED_DEM,
        "w",
        **projected_meta
    ) as dst:

        for band_index in range(1, src.count + 1):

            reproject(
                source=rasterio.band(src, band_index),
                destination=rasterio.band(dst, band_index),
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=src.nodata,
                dst_transform=transform,
                dst_crs=TARGET_CRS,
                dst_nodata=src.nodata,

                # Bilinear interpolation is appropriate
                # for continuous elevation values.
                resampling=Resampling.bilinear,
            )


print(f"Saved: {PROJECTED_DEM}")


# ---------------------------------------------------------
# 4. Validate final raster
# ---------------------------------------------------------

with rasterio.open(PROJECTED_DEM) as dem:

    elevation = dem.read(1, masked=True)
    values = elevation.compressed()

    print("\n" + "-" * 65)
    print("FINAL PROCESSED DEM")
    print("-" * 65)

    print(f"CRS        : {dem.crs}")
    print(
        f"Resolution : "
        f"{abs(dem.res[0]):.2f} m × "
        f"{abs(dem.res[1]):.2f} m"
    )
    print(f"Width      : {dem.width}")
    print(f"Height     : {dem.height}")
    print(f"NoData     : {dem.nodata}")

    if values.size:
        print(f"Min elev   : {np.min(values):.2f} m")
        print(f"Max elev   : {np.max(values):.2f} m")
        print(f"Mean elev  : {np.mean(values):.2f} m")
        print(f"Std dev    : {np.std(values):.2f} m")

        print(
            f"Valid cells: "
            f"{values.size:,} / {elevation.size:,} "
            f"({values.size / elevation.size * 100:.2f}%)"
        )


print("\n" + "=" * 65)
print("DEM PREPARATION COMPLETE")
print("=" * 65)