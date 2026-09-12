import numpy as np

from scripts.processing.open_land_detector import classify_open_pixels


def test_bare_low_vegetation_dry_pixel_is_open():
    scl = np.array([[5]], dtype=np.uint8)
    ndvi = np.array([[0.30]], dtype=np.float32)
    mndwi = np.array([[-0.40]], dtype=np.float32)

    result = classify_open_pixels(scl, ndvi, mndwi)

    assert result[0, 0] == 1


def test_high_ndvi_bare_pixel_is_not_open():
    scl = np.array([[5]], dtype=np.uint8)
    ndvi = np.array([[0.60]], dtype=np.float32)
    mndwi = np.array([[-0.30]], dtype=np.float32)

    result = classify_open_pixels(scl, ndvi, mndwi)

    assert result[0, 0] == 0


def test_water_like_pixel_is_not_open():
    scl = np.array([[5]], dtype=np.uint8)
    ndvi = np.array([[0.20]], dtype=np.float32)
    mndwi = np.array([[0.25]], dtype=np.float32)

    result = classify_open_pixels(scl, ndvi, mndwi)

    assert result[0, 0] == 0


def test_scl_water_is_not_open():
    scl = np.array([[6]], dtype=np.uint8)
    ndvi = np.array([[0.05]], dtype=np.float32)
    mndwi = np.array([[-0.10]], dtype=np.float32)

    result = classify_open_pixels(scl, ndvi, mndwi)

    assert result[0, 0] == 0

def test_cloud_shadow_is_unknown():
    scl = np.array([[3]], dtype=np.uint8)
    ndvi = np.array([[0.20]], dtype=np.float32)
    mndwi = np.array([[-0.30]], dtype=np.float32)

    result = classify_open_pixels(scl, ndvi, mndwi)

    assert result[0, 0] == 255


def test_unclassified_pixel_is_unknown():
    scl = np.array([[7]], dtype=np.uint8)
    ndvi = np.array([[0.20]], dtype=np.float32)
    mndwi = np.array([[-0.30]], dtype=np.float32)

    result = classify_open_pixels(scl, ndvi, mndwi)

    assert result[0, 0] == 255

def test_low_vegetation_surface_can_be_possible_open():
    scl = np.array([[4]], dtype=np.uint8)
    ndvi = np.array([[0.42]], dtype=np.float32)
    mndwi = np.array([[-0.30]], dtype=np.float32)

    result = classify_open_pixels(scl, ndvi, mndwi)

    assert result[0, 0] == 1


def test_dense_vegetation_is_not_open():
    scl = np.array([[4]], dtype=np.uint8)
    ndvi = np.array([[0.75]], dtype=np.float32)
    mndwi = np.array([[-0.40]], dtype=np.float32)

    result = classify_open_pixels(scl, ndvi, mndwi)

    assert result[0, 0] == 0


def test_positive_water_evidence_is_not_open():
    scl = np.array([[4]], dtype=np.uint8)
    ndvi = np.array([[0.30]], dtype=np.float32)
    mndwi = np.array([[0.20]], dtype=np.float32)

    result = classify_open_pixels(scl, ndvi, mndwi)

    assert result[0, 0] == 0

from scripts.processing.open_land_detector import apply_cloud_edge_buffer


def test_cloud_edge_buffer_marks_neighbor_unknown():
    state = np.array([
        [0, 1, 0],
        [1, 255, 1],
        [0, 1, 0],
    ], dtype=np.uint8)

    scl = np.array([
        [5, 5, 5],
        [5, 9, 5],
        [5, 5, 5],
    ], dtype=np.uint8)

    result = apply_cloud_edge_buffer(
        state,
        scl,
        buffer_pixels=1,
    )

    expected = np.array([
        [255, 255, 255],
        [255, 255, 255],
        [255, 255, 255],
    ], dtype=np.uint8)

    np.testing.assert_array_equal(
        result,
        expected,
    )