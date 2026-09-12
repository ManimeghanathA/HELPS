import numpy as np
from rasterio.transform import from_origin

from scripts.processing.candidate_polygonization import (
    polygonize_open_mask,
)


def test_polygonize_single_connected_open_region():

    state = np.array(
        [
            [0, 0, 0, 0],
            [0, 1, 1, 0],
            [0, 1, 1, 0],
            [0, 0, 0, 0],
        ],
        dtype=np.uint8,
    )

    transform = from_origin(
        0,
        40,
        10,
        10,
    )

    polygons = polygonize_open_mask(
        state=state,
        transform=transform,
        crs="EPSG:32643",
    )

    assert len(polygons) == 1

    assert round(
        polygons.geometry.iloc[0].area,
        2,
    ) == 400.00

def test_polygonize_two_disconnected_open_regions():

    state = np.array(
        [
            [1, 1, 0, 0, 0],
            [1, 1, 0, 1, 1],
            [0, 0, 0, 1, 1],
        ],
        dtype=np.uint8,
    )

    transform = from_origin(
        0,
        30,
        10,
        10,
    )

    polygons = polygonize_open_mask(
        state=state,
        transform=transform,
        crs="EPSG:32643",
    )

    assert len(polygons) == 2

    areas = sorted(
        polygons.geometry.area.tolist()
    )

    assert areas == [
        400.0,
        400.0,
    ]