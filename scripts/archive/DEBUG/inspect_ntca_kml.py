import geopandas as gpd

path = "data/raw/aoi/PA_TR_Corridor_Final.kml"

for layer in ["PA_TR_Corridors.kml", "PA_TR_Corridors"]:

    print("\n" + "=" * 60)
    print("LAYER:", layer)
    print("=" * 60)

    gdf = gpd.read_file(path, layer=layer, driver="KML")

    print("Features:", len(gdf))
    print("Columns:", gdf.columns.tolist())

    if len(gdf) > 0:
        print("\nNames containing Bhadra:")

        matches = gdf[
            gdf["Name"]
            .fillna("")
            .str.contains("Bhadra", case=False, na=False)
        ]

        print(matches[["Name", "geometry"]].to_string(index=False))

        print("\nFirst 10 names:")
        print(gdf["Name"].head(10).to_string(index=False))

        print("\nGeometry types:")
        print(gdf.geometry.geom_type.value_counts())