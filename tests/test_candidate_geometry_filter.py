from shapely.geometry import box

from scripts.processing.candidate_geometry_filter import (
    measure_candidate_geometry,
    passes_geometry_gate,
)


def test_valid_40_by_30_candidate_passes_geometry_gate():

    polygon = box(
        0,
        0,
        40,
        30,
    )

    measurements = measure_candidate_geometry(
        polygon
    )

    assert measurements["area_m2"] == 1200.0
    assert measurements["length_m"] == 40.0
    assert measurements["width_m"] == 30.0

    assert passes_geometry_gate(
        polygon,
        min_area_m2=900,
        min_length_m=30,
        min_width_m=30,
    )

def test_candidate_below_minimum_area_fails():

    polygon = box(
        0,
        0,
        30,
        20,
    )

    assert not passes_geometry_gate(
        polygon,
        min_area_m2=900,
        min_length_m=30,
        min_width_m=30,
    )


def test_candidate_that_is_long_but_too_narrow_fails():

    polygon = box(
        0,
        0,
        100,
        20,
    )

    measurements = measure_candidate_geometry(
        polygon
    )

    assert measurements["length_m"] == 100.0
    assert measurements["width_m"] == 20.0

    assert not passes_geometry_gate(
        polygon,
        min_area_m2=900,
        min_length_m=30,
        min_width_m=30,
    )