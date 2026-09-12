import geopandas as gpd
import pandas as pd

# ---------------------------------------
# Files
# ---------------------------------------

boundary_path = "data/processed/aoi/bhadra_ntca.geojson"
points_path = "data/raw/aoi/bhadra_official_boundary_reference.geojson"


# ---------------------------------------
# Load data
# ---------------------------------------

boundary = gpd.read_file(boundary_path)
points = gpd.read_file(points_path)

# Everything starts in WGS84
boundary = boundary.to_crs("EPSG:4326")
points = points.to_crs("EPSG:4326")


# ---------------------------------------
# Area
# ---------------------------------------

# EPSG:6933 = global equal-area projection
boundary_equal_area = boundary.to_crs("EPSG:6933")

area_km2 = (
    boundary_equal_area.geometry.area.sum()
    / 1_000_000
)

print("========================================")
print("NTCA BHADRA AOI VALIDATION")
print("========================================")

print(f"\nNTCA AOI area: {area_km2:.2f} km²")

print("\nGeometry:")
print(boundary.geometry.geom_type.value_counts().to_string())

print("\nBounds:")
print(tuple(boundary.total_bounds))


# ---------------------------------------
# Distance validation
# ---------------------------------------

# Use a metric projected CRS for this region.
# UTM Zone 43N covers the Bhadra region.
boundary_metric = boundary.to_crs("EPSG:32643")
points_metric = points.to_crs("EPSG:32643")


# Combine all polygon parts into one geometry
boundary_union = boundary_metric.geometry.union_all()


results = []

for _, row in points_metric.iterrows():

    point = row.geometry

    distance_m = point.distance(boundary_union)

    # Consider a point within 100 m of the boundary
    # as approximately matching.
    near_boundary = distance_m <= 100

    results.append({
        "map_id": row["map_id"],
        "distance_m": round(distance_m, 2),
        "near_boundary_100m": near_boundary
    })


results_df = pd.DataFrame(results)


# ---------------------------------------
# Results
# ---------------------------------------

print("\nOfficial reference-point comparison:")
print(
    results_df.to_string(index=False)
)

print("\n========================================")
print("SUMMARY")
print("========================================")

total = len(results_df)

near = results_df["near_boundary_100m"].sum()

print(f"Official points:       {total}")
print(f"Within 100 m:          {near}")
print(f"Outside 100 m:         {total - near}")

print(
    f"\nMaximum distance: "
    f"{results_df['distance_m'].max():.2f} m"
)

print(
    f"Average distance: "
    f"{results_df['distance_m'].mean():.2f} m"
)

print(
    f"Median distance: "
    f"{results_df['distance_m'].median():.2f} m"
)