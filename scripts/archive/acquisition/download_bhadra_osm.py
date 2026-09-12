from pathlib import Path

import geopandas as gpd
import osmnx as ox


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AOI_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_entire_region.geojson"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "osm"
)

OUTPUT_GPKG = (
    OUTPUT_DIR
    / "bhadra_osm_context.gpkg"
)


# ============================================================
# OSM FEATURE GROUPS
# ============================================================

FEATURE_GROUPS = {
    "buildings": {
        "building": True,
    },

    "roads": {
        "highway": True,
    },

    "railways": {
        "railway": True,
    },

    "power": {
        "power": True,
    },

    "man_made": {
        "man_made": True,
    },

    "barriers": {
        "barrier": True,
    },

    "water": {
        "natural": "water",
        "waterway": True,
    },
}


# ============================================================
# PREPARE
# ============================================================

print("=" * 72)
print("HELPSs — BHADRA OSM ACQUISITION")
print("=" * 72)

print(f"AOI    : {AOI_PATH}")
print(f"Output : {OUTPUT_GPKG}")
print()


if not AOI_PATH.exists():
    raise FileNotFoundError(
        f"AOI not found:\n{AOI_PATH}"
    )


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# LOAD AOI
# ============================================================

aoi = gpd.read_file(
    AOI_PATH
)


if aoi.crs is None:
    raise ValueError(
        "AOI does not have a CRS."
    )


# OSMnx expects WGS84 geometry.
aoi_wgs84 = aoi.to_crs(
    4326
)


# Merge all AOI features into one geometry.
aoi_geom = aoi_wgs84.geometry.union_all()


print(
    f"AOI CRS : "
    f"{aoi_wgs84.crs}"
)

print(
    f"Bounds  : "
    f"{aoi_geom.bounds}"
)

print()


# ============================================================
# DOWNLOAD EACH FEATURE GROUP
# ============================================================

for layer_name, tags in FEATURE_GROUPS.items():

    print("-" * 72)
    print(
        f"Downloading OSM layer: "
        f"{layer_name}"
    )
    print(
        f"Tags: {tags}"
    )

    try:

        features = ox.features_from_polygon(
            aoi_geom,
            tags,
        )

    except Exception as exc:

        print(
            f"FAILED: {layer_name}"
        )

        print(
            f"Reason: {exc}"
        )

        print()

        continue


    if features.empty:

        print(
            "No features found."
        )

        print()

        continue


    # --------------------------------------------------------
    # Convert index into normal columns
    # --------------------------------------------------------

    features = (
        features
        .reset_index()
    )


    # --------------------------------------------------------
    # Keep features inside actual Bhadra AOI
    # --------------------------------------------------------

    features = gpd.clip(
        features,
        aoi_wgs84,
    )


    if features.empty:

        print(
            "No features remained after AOI clipping."
        )

        print()

        continue


    # --------------------------------------------------------
    # Save one layer inside GeoPackage
    # --------------------------------------------------------

    features.to_file(
        OUTPUT_GPKG,
        layer=layer_name,
        driver="GPKG",
    )


    print(
        f"Features saved : "
        f"{len(features):,}"
    )


    geom_counts = (
        features
        .geometry
        .geom_type
        .value_counts()
    )


    print(
        "Geometry types:"
    )

    for geom_type, count in geom_counts.items():

        print(
            f"  {geom_type:<15} "
            f"{count:,}"
        )


    print()


# ============================================================
# COMPLETE
# ============================================================

print("=" * 72)
print("OSM ACQUISITION COMPLETE")
print("=" * 72)

print(
    f"Saved GeoPackage:\n"
    f"{OUTPUT_GPKG}"
)

print()

print(
    "Expected layers include:"
)

for name in FEATURE_GROUPS:

    print(
        f"  - {name}"
    )

print("=" * 72)