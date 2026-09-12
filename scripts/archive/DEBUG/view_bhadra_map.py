import geopandas as gpd
import folium

# Load Bhadra AOI
path = "data/processed/aoi/bhadra_wls_osm.geojson"
gdf = gpd.read_file(path)

# Convert to latitude/longitude
gdf = gdf.to_crs("EPSG:4326")

# Find center of AOI
center = gdf.geometry.union_all().centroid

# Create map
m = folium.Map(
    location=[center.y, center.x],
    zoom_start=11,
    tiles="OpenStreetMap"
)

# Add Bhadra polygon
folium.GeoJson(
    gdf.to_json(),
    name="Bhadra AOI",
    style_function=lambda feature: {
        "fillColor": "#3388ff",
        "color": "#0000ff",
        "weight": 2,
        "fillOpacity": 0.4,
    }
).add_to(m)

# Save map
output = "bhadra_map.html"
m.save(output)

print(f"Map saved to: {output}")