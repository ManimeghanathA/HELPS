from pathlib import Path
import geopandas as gpd
from shapely.ops import unary_union


# ============================================================
# CONFIGURATION
# ============================================================

AOI_PATH = Path("data/processed/aoi/bhadra_aoi.geojson")

RESTRICTION_DIR = Path("data/processed/restricted")

OUTPUT_DIR = Path("data/processed/usable")

OUTPUT_RESTRICTED = OUTPUT_DIR / "bhadra_restricted.geojson"
OUTPUT_USABLE = OUTPUT_DIR / "bhadra_usable_area.geojson"


# Metric CRS for geometric operations
# Bhadra lies in UTM Zone 43N
METRIC_CRS = "EPSG:32643"

WGS84 = "EPSG:4326"


# ============================================================
# HELPERS
# ============================================================

def load_polygon(path):
    """
    Load a vector dataset and return valid polygon geometry.
    """

    gdf = gpd.read_file(path)

    if gdf.empty:
        raise ValueError(f"No features found in: {path}")

    if gdf.crs is None:
        raise ValueError(f"No CRS defined in: {path}")

    # Standardize CRS
    gdf = gdf.to_crs(WGS84)

    # Keep only polygonal geometries
    gdf = gdf[
        gdf.geometry.geom_type.isin(
            ["Polygon", "MultiPolygon"]
        )
    ].copy()

    if gdf.empty:
        raise ValueError(
            f"No Polygon/MultiPolygon geometry found in: {path}"
        )

    # Repair minor geometry problems
    gdf["geometry"] = gdf.geometry.make_valid()

    return gdf


# ============================================================
# LOAD AOI
# ============================================================

def load_aoi():

    print("Loading AOI...")

    aoi = load_polygon(AOI_PATH)

    # Merge all AOI pieces into one geometry
    geometry = unary_union(aoi.geometry)

    return geometry


# ============================================================
# LOAD RESTRICTED AREAS
# ============================================================

def load_restricted_areas():

    print("\nLoading restricted-area layers...")

    files = list(RESTRICTION_DIR.glob("*.geojson"))

    if not files:
        print("No restriction layers found.")
        return None

    geometries = []

    for path in files:

        print(f"  Loading: {path.name}")

        gdf = load_polygon(path)

        geometries.extend(
            list(gdf.geometry)
        )

    if not geometries:
        return None

    # Combine every restriction into one geometry
    restricted = unary_union(geometries)

    return restricted


# ============================================================
# CLIP RESTRICTIONS TO AOI
# ============================================================

def clip_restrictions_to_aoi(aoi, restricted):

    print("\nClipping restricted areas to AOI...")

    if restricted is None:
        return None

    # Perform metric operations
    aoi_metric = gpd.GeoSeries(
        [aoi],
        crs=WGS84
    ).to_crs(METRIC_CRS).iloc[0]

    restricted_metric = gpd.GeoSeries(
        [restricted],
        crs=WGS84
    ).to_crs(METRIC_CRS).iloc[0]

    restricted_inside = restricted_metric.intersection(
        aoi_metric
    )

    return restricted_inside


# ============================================================
# CALCULATE USABLE AREA
# ============================================================

def calculate_usable_area(aoi, restricted):

    print("\nCalculating usable area...")

    aoi_metric = gpd.GeoSeries(
        [aoi],
        crs=WGS84
    ).to_crs(METRIC_CRS).iloc[0]

    if restricted is None:
        usable = aoi_metric

    else:
        usable = aoi_metric.difference(
            restricted
        )

    return usable


# ============================================================
# SAVE GEOMETRY
# ============================================================

def save_geometry(geometry, output_path, layer_name):

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    gdf = gpd.GeoDataFrame(
        {
            "layer": [layer_name]
        },
        geometry=[geometry],
        crs=METRIC_CRS
    )

    # Save in WGS84 for interoperability
    gdf = gdf.to_crs(WGS84)

    gdf.to_file(
        output_path,
        driver="GeoJSON"
    )

    print(f"Saved: {output_path}")


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():

    print("=" * 60)
    print("HELPS RESTRICTED AREA EXCLUSION ENGINE")
    print("=" * 60)

    # 1. Load complete AOI
    aoi = load_aoi()

    # 2. Load all restrictions
    restricted = load_restricted_areas()

    # 3. Restriction geometry inside AOI
    restricted_inside = clip_restrictions_to_aoi(
        aoi,
        restricted
    )

    # 4. Calculate usable region
    usable = calculate_usable_area(
        aoi,
        restricted_inside
    )

    # 5. Save restricted geometry
    if restricted_inside is not None:

        save_geometry(
            restricted_inside,
            OUTPUT_RESTRICTED,
            "restricted_area"
        )

    # 6. Save usable geometry
    save_geometry(
        usable,
        OUTPUT_USABLE,
        "usable_area"
    )

    print("\nPipeline completed.")


if __name__ == "__main__":
    main()