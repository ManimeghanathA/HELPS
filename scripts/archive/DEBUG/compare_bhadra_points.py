import geopandas as gpd
import folium

# -----------------------------
# Load OSM Bhadra polygon
# -----------------------------

boundary_path = "data/processed/aoi/bhadra_wls_osm.geojson"

boundary = gpd.read_file(boundary_path)
boundary = boundary.to_crs("EPSG:4326")


# -----------------------------
# Load official 54 points
# -----------------------------

points_path = "data/raw/aoi/bhadra_official_boundary_reference.geojson"

points = gpd.read_file(points_path)
points = points.to_crs("EPSG:4326")


# -----------------------------
# Find map center
# -----------------------------

centroid = boundary.geometry.union_all().centroid

m = folium.Map(
    location=[centroid.y, centroid.x],
    zoom_start=11,
    tiles="OpenStreetMap"
)


# -----------------------------
# Add OSM polygon
# -----------------------------

folium.GeoJson(
    boundary.to_json(),
    name="OSM Bhadra Boundary",
    style_function=lambda feature: {
        "color": "blue",
        "weight": 3,
        "fillColor": "blue",
        "fillOpacity": 0.15,
    }
).add_to(m)


# -----------------------------
# Add official points
# -----------------------------

for _, row in points.iterrows():

    lat = row.geometry.y
    lon = row.geometry.x
    map_id = row["map_id"]

    folium.CircleMarker(
        location=[lat, lon],
        radius=5,
        color="red",
        fill=True,
        fillColor="red",
        fillOpacity=1,
        popup=f"Official Point {map_id}"
    ).add_to(m)


# -----------------------------
# Layer control
# -----------------------------

folium.LayerControl().add_to(m)


# -----------------------------
# Save
# -----------------------------

output = "bhadra_boundary_comparison.html"

m.save(output)

print(f"Map saved to: {output}")