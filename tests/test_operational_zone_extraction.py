from shapely.geometry import box
from shapely.ops import unary_union

from scripts.processing.operational_zone_extraction import (
    extract_operational_zones,
)


def test_narrow_bridge_becomes_two_non_overlapping_zones():

    left = box(
        0,
        0,
        40,
        40,
    )

    right = box(
        80,
        0,
        120,
        40,
    )

    # 10 m wide bridge — below 30 m requirement
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

    zones = extract_operational_zones(
        candidate,
        clearance_radius_m=15,
    )

    assert len(zones) == 2

    # Independent zones must never overlap in area
    assert zones[0].intersection(
        zones[1]
    ).area == 0


def test_wide_bridge_remains_one_zone():

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

    # 40 m wide bridge — enough for 30 m clearance
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

    zones = extract_operational_zones(
        candidate,
        clearance_radius_m=15,
    )

    assert len(zones) == 1


def test_operational_zones_never_extend_outside_parent():

    candidate = box(
        0,
        0,
        100,
        100,
    )

    zones = extract_operational_zones(
        candidate,
        clearance_radius_m=15,
    )

    assert len(zones) == 1

    outside_area = zones[0].difference(
        candidate
    ).area

    assert outside_area == 0