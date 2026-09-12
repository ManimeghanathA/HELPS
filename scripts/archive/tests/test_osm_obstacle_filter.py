import numpy as np

from scripts.processing.osm_obstacle_filter import apply_obstacle_mask


def test_obstacle_pixels_are_removed_from_possible_open():
    possible_open = np.array(
        [
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
        ],
        dtype=np.uint8,
    )

    obstacle_mask = np.array(
        [
            [0, 0, 0],
            [0, 1, 0],
            [0, 0, 0],
        ],
        dtype=np.uint8,
    )

    result = apply_obstacle_mask(
        possible_open,
        obstacle_mask,
    )

    expected = np.array(
        [
            [1, 1, 1],
            [1, 0, 1],
            [1, 1, 1],
        ],
        dtype=np.uint8,
    )

    np.testing.assert_array_equal(
        result,
        expected,
    )


def test_unknown_pixels_remain_unknown():
    possible_open = np.array(
        [
            [1, 255],
            [0, 1],
        ],
        dtype=np.uint8,
    )

    obstacle_mask = np.array(
        [
            [0, 1],
            [0, 0],
        ],
        dtype=np.uint8,
    )

    result = apply_obstacle_mask(
        possible_open,
        obstacle_mask,
    )

    assert result[0, 1] == 255