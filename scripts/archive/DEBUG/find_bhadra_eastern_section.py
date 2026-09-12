import geopandas as gpd
from shapely.geometry import Point

path = "data/raw/aoi/PA_TR_Corridor_Final.kml"

# Load all Protected Area features
gdf = gpd.read_file(
    path,
    layer="PA_TR_Corridors",
    driver="KML"
).to_crs("EPSG:4326")

# Points 48-53 from the official reference list
target_points = {
    48: (75.7490, 13.5566),
    49: (75.7606, 13.5372),
    50: (75.7746, 13.5445),
    51: (75.7742, 13.5156),
    52: (75.7370, 13.5010),
    53: (75.7395, 13.5181),
}

print("=" * 60)
print("SEARCHING NTCA DATA FOR BHADRA EASTERN SECTION")
print("=" * 60)

for map_id, (lon, lat) in target_points.items():

    point = Point(lon, lat)

    # Find features whose geometry contains the point
    containing = gdf[gdf.geometry.contains(point)]

    print(f"\nOfficial Point {map_id}")
    print(f"Location: {lat}, {lon}")

    if len(containing) > 0:
        print("Features containing point:")

        for _, row in containing.iterrows():
            print(
                f"  Name: {row['Name']}"
            )

    else:
        # If nothing contains it, find nearby features
        metric = gdf.to_crs("EPSG:32643")
        point_metric = gpd.GeoSeries(
            [point],
            crs="EPSG:4326"
        ).to_crs("EPSG:32643").iloc[0]

        distances = metric.geometry.distance(point_metric)

        nearest_index = distances.idxmin()
        nearest = gdf.loc[nearest_index]

        print("No feature contains this point.")
        print("Nearest NTCA feature:")
        print(f"  Name: {nearest['Name']}")
        print(f"  Distance: {distances.loc[nearest_index]:.0f} m")


print("\n" + "=" * 60)
print("FEATURE NAMES CONTAINING 'BHADRA' OR 'BAB'")
print("=" * 60)

matches = gdf[
    gdf["Name"]
    .fillna("")
    .str.contains(
        "bhadra|baba",
        case=False,
        regex=True,
        na=False
    )
]

print(
    matches[
        ["Name", "geometry"]
    ][["Name"]].to_string(index=False)
)