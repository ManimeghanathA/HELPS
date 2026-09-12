from shapely.geometry import box
from shapely.ops import unary_union

from scripts.processing.clearance_analysis import (
    extract_clearance_cores,
)


def test_narrow_bridge_splits_candidate_into_two_clearance_cores():

    # Left 40 m × 40 m region
    left = box(
        0,
        0,
        40,
        40,
    )

    # Right 40 m × 40 m region
    right = box(
        80,
        0,
        120,
        40,
    )

    # Only 10 m wide.
    # This bridge is too narrow for a 30 m clearance requirement.
    bridge = box(
        40,
        15,
        80,
        25,
    )

    candidate = unary_union(
        [
            left,
            bridge,
            right,
        ]
    )

    cores = extract_clearance_cores(
        candidate,
        clearance_radius_m=15,
    )

    assert len(cores) == 2

    assert all(
        not core.is_empty
        for core in cores
    )

def test_wide_bridge_keeps_candidate_connected():

    left = box(
        0,
        0,
        60,
        60,
    )

    right = box(
        100,
        0,
        160,
        60,
    )

    # 40 m wide bridge
    bridge = box(
        60,
        10,
        100,
        50,
    )

    candidate = unary_union(
        [
            left,
            bridge,
            right,
        ]
    )

    cores = extract_clearance_cores(
        candidate,
        clearance_radius_m=15,
    )

    assert len(cores) == 1


def test_candidate_too_narrow_has_no_clearance_core():

    # 100 m long but only 20 m wide
    candidate = box(
        0,
        0,
        100,
        20,
    )

    cores = extract_clearance_cores(
        candidate,
        clearance_radius_m=15,
    )

    assert len(cores) == 0