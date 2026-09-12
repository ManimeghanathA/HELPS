import geopandas as gpd
from shapely.geometry import MultiPolygon

# -----------------------------
# Load NTCA Bhadra
# -----------------------------

boundary_path = "data/processed/aoi/bhadra_ntca.geojson"
points_path = "data/raw/aoi/bhadra_official_boundary_reference.geojson"

boundary = gpd.read_file(boundary_path).to_crs("EPSG:4326")
points = gpd.read_file(points_path).to_crs("EPSG:4326")

geometry = boundary.geometry.iloc[0]

# -----------------------------
# Break MultiPolygon into parts
# -----------------------------

if geometry.geom_type == "MultiPolygon":
    parts = list(geometry.geoms)
else:
    parts = [geometry]

print("========================================")
print("NTCA BHADRA COMPONENTS")
print("========================================")

print(f"\nNumber of polygon parts: {len(parts)}")

# -----------------------------
# Inspect each part
# -----------------------------

for i, part in enumerate(parts, start=1):

    print(f"\nPart {i}")

    print("  Bounds:")
    print("   ", tuple(round(x, 6) for x in part.bounds))

    print("  Area:")
    
    # Temporary GeoDataFrame for area
    part_gdf = gpd.GeoDataFrame(
        geometry=[part],
        crs="EPSG:4326"
    )

    area_km2 = (
        part_gdf
        .to_crs("EPSG:6933")
        .geometry.area.iloc[0]
        / 1_000_000
    )

    print(f"   {area_km2:.2f} km²")


# -----------------------------
# Check official points
# against each component
# -----------------------------

print("\n========================================")
print("OFFICIAL POINT → CLOSEST NTCA COMPONENT")
print("========================================")

# Use metric CRS
boundary_metric = boundary.to_crs("EPSG:32643")
points_metric = points.to_crs("EPSG:32643")

geometry_metric = boundary_metric.geometry.iloc[0]

if geometry_metric.geom_type == "MultiPolygon":
    metric_parts = list(geometry_metric.geoms)
else:
    metric_parts = [geometry_metric]


for _, row in points_metric.iterrows():

    point = row.geometry

    distances = [
        point.distance(part)
        for part in metric_parts
    ]

    closest_part = distances.index(min(distances)) + 1
    closest_distance = min(distances)

    print(
        f"Point {int(row['map_id']):2d} "
        f"→ Part {closest_part} "
        f"→ {closest_distance:.0f} m"
    )