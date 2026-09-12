from shapely.geometry import box

from scripts.processing.maximum_clearance import (
    measure_maximum_clearance,
)


def test_square_has_expected_maximum_clearance():

    polygon = box(
        0,
        0,
        40,
        40,
    )

    result = measure_maximum_clearance(
        polygon,
        tolerance_m=0.1,
    )

    assert abs(result["center"].x - 20.0) < 0.2
    assert abs(result["center"].y - 20.0) < 0.2

    assert abs(result["radius_m"] - 20.0) < 0.2
    assert abs(result["diameter_m"] - 40.0) < 0.4