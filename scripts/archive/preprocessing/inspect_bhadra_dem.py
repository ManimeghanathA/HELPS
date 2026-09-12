from pathlib import Path
import sys

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.warp import transform_bounds


# --------------------------------------------------
# Project paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AOI_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_valid_region.geojson"
)


# --------------------------------------------------
# DEM path from command line
# --------------------------------------------------

if len(sys.argv) != 2:
    raise SystemExit(
        "\nUsage:\n"
        "python scripts/preprocessing/inspect_bhadra_dem.py "
        "data/raw/DEM/<dem_file>.tif\n"
    )

DEM_PATH = Path(sys.argv[1])

if not DEM_PATH.is_absolute():
    DEM_PATH = PROJECT_ROOT / DEM_PATH


# --------------------------------------------------
# Check files
# --------------------------------------------------

if not DEM_PATH.exists():
    raise FileNotFoundError(f"DEM not found: {DEM_PATH}")

if not AOI_PATH.exists():
    raise FileNotFoundError(f"AOI not found: {AOI_PATH}")


# --------------------------------------------------
# Read AOI
# --------------------------------------------------

aoi = gpd.read_file(AOI_PATH)

print("=" * 65)
print("BHADRA DEM INSPECTION")
print("=" * 65)

print("\nAOI")
print("-" * 65)
print(f"File     : {AOI_PATH.name}")
print(f"CRS      : {aoi.crs}")
print(f"Features : {len(aoi)}")

aoi_bounds = aoi.total_bounds

print(
    f"Bounds   : "
    f"{aoi_bounds[0]:.6f}, "
    f"{aoi_bounds[1]:.6f}, "
    f"{aoi_bounds[2]:.6f}, "
    f"{aoi_bounds[3]:.6f}"
)


# --------------------------------------------------
# Read DEM
# --------------------------------------------------

with rasterio.open(DEM_PATH) as dem:

    print("\nDEM")
    print("-" * 65)

    print(f"File        : {DEM_PATH.name}")
    print(f"Driver      : {dem.driver}")
    print(f"CRS         : {dem.crs}")
    print(f"Width       : {dem.width}")
    print(f"Height      : {dem.height}")
    print(f"Band count  : {dem.count}")
    print(f"Data type   : {dem.dtypes[0]}")
    print(f"NoData      : {dem.nodata}")

    print(
        f"Resolution  : "
        f"{abs(dem.res[0]):.8f}, "
        f"{abs(dem.res[1]):.8f}"
    )

    print(
        f"Bounds      : "
        f"{dem.bounds.left:.6f}, "
        f"{dem.bounds.bottom:.6f}, "
        f"{dem.bounds.right:.6f}, "
        f"{dem.bounds.top:.6f}"
    )

    # --------------------------------------------------
    # Elevation statistics
    # --------------------------------------------------

    elevation = dem.read(1, masked=True)
    valid_values = elevation.compressed()

    print("\nELEVATION STATISTICS")
    print("-" * 65)

    if valid_values.size == 0:
        print("No valid elevation values found.")
    else:
        print(f"Minimum     : {np.min(valid_values):.2f} m")
        print(f"Maximum     : {np.max(valid_values):.2f} m")
        print(f"Mean        : {np.mean(valid_values):.2f} m")
        print(f"Median      : {np.median(valid_values):.2f} m")
        print(f"Std Dev     : {np.std(valid_values):.2f} m")

        total_pixels = elevation.size
        valid_pixels = valid_values.size

        print(
            f"Valid pixels: "
            f"{valid_pixels:,} / {total_pixels:,} "
            f"({valid_pixels / total_pixels * 100:.2f}%)"
        )

    # --------------------------------------------------
    # AOI coverage check
    # --------------------------------------------------

    if aoi.crs is None:
        raise ValueError("AOI has no CRS.")

    if dem.crs is None:
        raise ValueError("DEM has no CRS.")

    transformed_aoi_bounds = transform_bounds(
        aoi.crs,
        dem.crs,
        *aoi_bounds
    )

    aoi_left, aoi_bottom, aoi_right, aoi_top = transformed_aoi_bounds

    coverage_ok = (
        dem.bounds.left <= aoi_left
        and dem.bounds.right >= aoi_right
        and dem.bounds.bottom <= aoi_bottom
        and dem.bounds.top >= aoi_top
    )

    print("\nAOI COVERAGE CHECK")
    print("-" * 65)

    print(
        f"AOI in DEM CRS : "
        f"{aoi_left:.6f}, "
        f"{aoi_bottom:.6f}, "
        f"{aoi_right:.6f}, "
        f"{aoi_top:.6f}"
    )

    print(f"Fully covered  : {coverage_ok}")

    if not coverage_ok:
        print(
            "\nWARNING: The DEM does not completely cover "
            "the Bhadra AOI."
        )


print("\n" + "=" * 65)
print("INSPECTION COMPLETE")
print("=" * 65)