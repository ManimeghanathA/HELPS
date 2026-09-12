import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# -----------------------------
# 1. Load Bhadra OSM boundary
# -----------------------------

boundary_path = "data/processed/aoi/bhadra_wls_osm.geojson"

boundary = gpd.read_file(boundary_path)
boundary = boundary.to_crs("EPSG:4326")


# -----------------------------
# 2. Load official reference points
# -----------------------------

reference_path = "data/raw/aoi/bhadra_official_boundary_reference.geojson"

reference = gpd.read_file(reference_path)
reference = reference.to_crs("EPSG:4326")


# -----------------------------
# 3. Calculate area
# -----------------------------

# Equal-area projection
boundary_equal_area = boundary.to_crs("EPSG:6933")

area_km2 = boundary_equal_area.geometry.area.sum() / 1_000_000

print("Bhadra AOI area:")
print(f"{area_km2:.2f} km²")


# -----------------------------
# 4. Check reference points
# -----------------------------

# Use a small buffer because the official points
# are reference points and may not lie exactly
# on the OSM boundary.

boundary_buffer = boundary.buffer(0.001)

results = []

for _, row in reference.iterrows():

    point = row.geometry

    distance = boundary.distance(point).min()

    inside = boundary_buffer.contains(point).any()

    results.append({
        "map_id": row["map_id"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "inside_near_boundary": inside,
        "distance_degrees": distance
    })


results_df = pd.DataFrame(results)

print("\nReference point verification:")
print(results_df.to_string(index=False))

print("\nPoints near/on boundary:")
print(
    results_df["inside_near_boundary"]
    .value_counts()
)

print("\nMaximum distance from OSM boundary:")
print(
    results_df["distance_degrees"].max()
)