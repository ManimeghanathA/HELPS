import geopandas as gpd


def subtract_buildings(
    open_land,
    buildings,
    progress=None,
):
    """
    Subtract building footprints from open-land polygons.

    Parameters
    ----------
    open_land : GeoDataFrame
        Open-land polygons.

    buildings : GeoDataFrame
        Building polygons.

    Returns
    -------
    GeoDataFrame
        Remaining open-land fragments after building subtraction.
    """

    if open_land.empty:
        return open_land.copy()

    if buildings.empty:
        return open_land.copy()

    # Align CRS
    if buildings.crs != open_land.crs:
        buildings = buildings.to_crs(
            open_land.crs
        )

    # Merge all building footprints into one geometry
    building_union = (
        buildings.geometry.union_all()
    )

    rows = []

    for position, (_, row) in enumerate(open_land.iterrows()):

        if progress is not None and position % 500 == 0:
            progress(f'Building subtraction: {position:,} / {len(open_land):,} components')

        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        result = geom.difference(
            building_union
        )

        if result.is_empty:
            continue

        # Polygon result
        if result.geom_type == "Polygon":

            new_row = row.copy()
            new_row.geometry = result

            rows.append(
                new_row
            )

        # Building subtraction may split land into multiple pieces
        elif result.geom_type == "MultiPolygon":

            for part in result.geoms:

                if part.is_empty:
                    continue

                new_row = row.copy()
                new_row.geometry = part

                rows.append(
                    new_row
                )

        # GeometryCollection can occasionally occur
        elif result.geom_type == "GeometryCollection":

            for part in result.geoms:

                if part.geom_type != "Polygon":
                    continue

                if part.is_empty:
                    continue

                new_row = row.copy()
                new_row.geometry = part

                rows.append(
                    new_row
                )

    if not rows:
        return open_land.iloc[:0].copy()

    result_gdf = gpd.GeoDataFrame(
        rows,
        crs=open_land.crs,
    )

    result_gdf = result_gdf.reset_index(
        drop=True
    )

    return result_gdf
