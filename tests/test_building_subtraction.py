import geopandas as gpd

from shapely.geometry import box

from scripts.processing.building_subtraction import (
    subtract_buildings,
)


def test_building_can_split_open_land_into_two_parts():

    # 100 m × 40 m open land
    open_land = gpd.GeoDataFrame(
        {
            "component_id": [1],
        },
        geometry=[
            box(
                0,
                0,
                100,
                40,
            )
        ],
        crs="EPSG:32643",
    )

    # Building cuts completely through the middle
    building = gpd.GeoDataFrame(
        geometry=[
            box(
                45,
                0,
                55,
                40,
            )
        ],
        crs="EPSG:32643",
    )

    result = subtract_buildings(
        open_land,
        building,
    )

    assert len(result) == 2

    areas = sorted(
        result.geometry.area.tolist()
    )

    assert areas == [
        1800.0,
        1800.0,
    ]