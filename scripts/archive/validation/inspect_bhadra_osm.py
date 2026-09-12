from pathlib import Path

import fiona
import geopandas as gpd
import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GPKG_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "osm"
    / "bhadra_osm_context.gpkg"
)


# ============================================================
# TAGS WE CARE ABOUT
# ============================================================

IMPORTANT_TAGS = [
    "building",
    "highway",
    "railway",
    "power",
    "man_made",
    "barrier",
    "natural",
    "water",
    "waterway",
    "landuse",
    "surface",
    "service",
]


if not GPKG_PATH.exists():
    raise FileNotFoundError(
        f"GeoPackage not found:\n{GPKG_PATH}"
    )


print("=" * 80)
print("HELPSs — BHADRA OSM INVENTORY")
print("=" * 80)

print(f"GeoPackage:\n{GPKG_PATH}")
print()


# ============================================================
# LIST LAYERS
# ============================================================

layers = fiona.listlayers(GPKG_PATH)

print("Layers found:")
for layer in layers:
    print(f"  - {layer}")

print()


# ============================================================
# INSPECT EACH LAYER
# ============================================================

for layer_name in layers:

    print("=" * 80)
    print(f"LAYER: {layer_name}")
    print("=" * 80)

    gdf = gpd.read_file(
        GPKG_PATH,
        layer=layer_name,
    )

    print(f"Features : {len(gdf):,}")
    print(f"CRS      : {gdf.crs}")

    if len(gdf) == 0:
        print()
        continue


    # --------------------------------------------------------
    # Geometry types
    # --------------------------------------------------------

    print()
    print("Geometry types:")

    geometry_counts = (
        gdf.geometry
        .geom_type
        .value_counts(dropna=False)
    )

    for geometry_type, count in geometry_counts.items():
        print(
            f"  {str(geometry_type):<20} "
            f"{count:,}"
        )


    # --------------------------------------------------------
    # Important OSM tags
    # --------------------------------------------------------

    for tag in IMPORTANT_TAGS:

        if tag not in gdf.columns:
            continue

        values = gdf[tag]

        values = values[
            values.notna()
        ]

        if values.empty:
            continue

        print()
        print(f"Tag: {tag}")

        counts = (
            values
            .astype(str)
            .value_counts()
            .head(30)
        )

        for value, count in counts.items():

            print(
                f"  {value:<35} "
                f"{count:,}"
            )


    # --------------------------------------------------------
    # Available columns
    # --------------------------------------------------------

    print()
    print("Available columns:")

    useful_columns = [
        col
        for col in gdf.columns
        if col != "geometry"
    ]

    print(
        "  "
        + ", ".join(useful_columns)
    )

    print()


print("=" * 80)
print("OSM INVENTORY COMPLETE")
print("=" * 80)