import geopandas as gpd
from shapely.geometry import Polygon

# A small test polygon somewhere inside Bhadra
test_polygon = Polygon([
    (75.60, 13.60),
    (75.63, 13.60),
    (75.63, 13.63),
    (75.60, 13.63),
    (75.60, 13.60)
])

gdf = gpd.GeoDataFrame(
    {
        "restriction_type": ["test_restriction"],
        "reason": ["Pipeline validation only"]
    },
    geometry=[test_polygon],
    crs="EPSG:4326"
)

gdf.to_file(
    "data/processed/restricted/test_restriction.geojson",
    driver="GeoJSON"
)

print("Test restriction created.")