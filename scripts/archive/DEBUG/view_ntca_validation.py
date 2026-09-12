import geopandas as gpd
import folium

boundary_path = "data/processed/aoi/bhadra_ntca.geojson"
points_path = "data/raw/aoi/bhadra_official_boundary_reference.geojson"

boundary = gpd.read_file(boundary_path).to_crs("EPSG:4326")
points = gpd.read_file(points_path).to_crs("EPSG:4326")

center = boundary.geometry.union_all().centroid

m = folium.Map(
    location=[center.y, center.x],
    zoom_start=11,
    tiles="OpenStreetMap"
)

# NTCA polygon
folium.GeoJson(
    boundary.to_json(),
    name="NTCA Bhadra",
    style_function=lambda feature: {
        "color": "blue",
        "weight": 3,
        "fillColor": "blue",
        "fillOpacity": 0.15,
    }
).add_to(m)

# Official points
for _, row in points.iterrows():

    folium.CircleMarker(
        location=[
            row.geometry.y,
            row.geometry.x
        ],
        radius=5,
        color="red",
        fill=True,
        fillColor="red",
        fillOpacity=1,
        popup=f"Official Point {row['map_id']}"
    ).add_to(m)

folium.LayerControl().add_to(m)

m.save("ntca_bhadra_validation.html")

print("Saved: ntca_bhadra_validation.html")