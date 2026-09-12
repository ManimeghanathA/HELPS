from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

AOI_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_entire_region.geojson"
)

OUTPUT_GPKG = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "osm"
    / "bhadra_osm_context.gpkg"
)


# Try another public Overpass endpoint instead of the one
# that timed out in the previous run.
ox.settings.overpass_url = (
    "https://overpass.kumi.systems/api/interpreter"
)


aoi = gpd.read_file(AOI_PATH).to_crs(4326)
aoi_geom = aoi.geometry.union_all()


def save_layer(features, layer_name):
    if features is None or features.empty:
        print(f"{layer_name}: no features found")
        return

    features = features.reset_index()

    features = gpd.clip(
        features,
        aoi,
    )

    if features.empty:
        print(f"{layer_name}: empty after AOI clipping")
        return

    features.to_file(
        OUTPUT_GPKG,
        layer=layer_name,
        driver="GPKG",
    )

    print(
        f"{layer_name}: "
        f"{len(features):,} features saved"
    )


print("=" * 72)
print("HELPSs — RETRY MISSING OSM CONTEXT")
print("=" * 72)


# ============================================================
# WATER POLYGONS
# ============================================================

print("\nDownloading natural=water ...")

try:
    water_polygons = ox.features_from_polygon(
        aoi_geom,
        {
            "natural": "water",
        },
    )

    save_layer(
        water_polygons,
        "water_polygons",
    )

except Exception as exc:
    print(
        f"natural=water FAILED:\n{exc}"
    )


# ============================================================
# WATERWAYS
# ============================================================

print("\nDownloading waterways ...")

try:
    waterways = ox.features_from_polygon(
        aoi_geom,
        {
            "waterway": True,
        },
    )

    save_layer(
        waterways,
        "waterways",
    )

except Exception as exc:
    print(
        f"waterways FAILED:\n{exc}"
    )


# ============================================================
# BARRIERS
# ============================================================

print("\nDownloading barriers ...")

try:
    barriers = ox.features_from_polygon(
        aoi_geom,
        {
            "barrier": True,
        },
    )

    save_layer(
        barriers,
        "barriers",
    )

except Exception as exc:
    print(
        f"barriers FAILED:\n{exc}"
    )


print("\n" + "=" * 72)
print("RETRY COMPLETE")
print("=" * 72)
print(OUTPUT_GPKG)