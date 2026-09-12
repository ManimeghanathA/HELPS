import geopandas as gpd

input_path = "data/raw/aoi/PA_TR_Corridor_Final.kml"
output_path = "data/processed/aoi/bhadra_ntca.geojson"

# Read the NTCA Protected Areas layer
gdf = gpd.read_file(
    input_path,
    layer="PA_TR_Corridors",
    driver="KML"
)

# Find Bhadra
bhadra = gdf[
    gdf["Name"].fillna("").str.strip().str.lower() == "bhadra"
].copy()

if bhadra.empty:
    raise RuntimeError("Bhadra was not found in the NTCA layer.")

print("Bhadra features found:", len(bhadra))
print("Geometry type:", bhadra.geometry.iloc[0].geom_type)

# KML is normally WGS84, but explicitly standardize it
bhadra = bhadra.to_crs("EPSG:4326")

# Save
bhadra.to_file(
    output_path,
    driver="GeoJSON"
)

print("Saved to:", output_path)

print("Bounds:", tuple(bhadra.total_bounds))

# Calculate area using an equal-area CRS
area_km2 = (
    bhadra.to_crs("EPSG:6933")
    .geometry.area.sum()
    / 1_000_000
)

print(f"Area: {area_km2:.2f} km²")