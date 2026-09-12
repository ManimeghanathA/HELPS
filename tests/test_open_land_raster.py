from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from scripts.processing.open_land_detector import generate_open_land_mask


def test_generate_open_land_mask(tmp_path):
    spectral_path = tmp_path / "spectral.tif"
    scl_path = tmp_path / "scl.tif"
    output_path = tmp_path / "open_mask.tif"

    transform = from_origin(
        500000,
        1500000,
        10,
        10,
    )

    profile = {
        "driver": "GTiff",
        "height": 2,
        "width": 2,
        "count": 6,
        "dtype": "float32",
        "crs": "EPSG:32643",
        "transform": transform,
        "nodata": -9999.0,
    }

    # --------------------------------------------------------
    # Synthetic Sentinel example
    #
    # [0,0] = bare + low vegetation + dry -> OPEN
    # [0,1] = vegetation                  -> NOT_OPEN
    # [1,0] = water                       -> NOT_OPEN
    # [1,1] = cloud shadow                -> UNKNOWN
    # --------------------------------------------------------

    b02 = np.array([
        [0.08, 0.04],
        [0.05, 0.08],
    ], dtype=np.float32)

    b03 = np.array([
        [0.10, 0.06],
        [0.20, 0.10],
    ], dtype=np.float32)

    b04 = np.array([
        [0.10, 0.04],
        [0.04, 0.08],
    ], dtype=np.float32)

    b08 = np.array([
        [0.15, 0.35],
        [0.03, 0.15],
    ], dtype=np.float32)

    b11 = np.array([
        [0.20, 0.18],
        [0.05, 0.20],
    ], dtype=np.float32)

    b12 = np.array([
        [0.16, 0.10],
        [0.04, 0.16],
    ], dtype=np.float32)

    with rasterio.open(
        spectral_path,
        "w",
        **profile,
    ) as dst:

        dst.write(b02, 1)
        dst.write(b03, 2)
        dst.write(b04, 3)
        dst.write(b08, 4)
        dst.write(b11, 5)
        dst.write(b12, 6)

    scl_profile = profile.copy()

    scl_profile.update(
        count=1,
        dtype="uint8",
        nodata=0,
    )

    scl = np.array([
        [5, 4],
        [6, 3],
    ], dtype=np.uint8)

    with rasterio.open(
        scl_path,
        "w",
        **scl_profile,
    ) as dst:

        dst.write(scl, 1)

    generate_open_land_mask(
        spectral_path,
        scl_path,
        output_path,
    )

    assert output_path.exists()

    with rasterio.open(output_path) as src:

        result = src.read(1)

        assert src.count == 1
        assert src.crs.to_epsg() == 32643
        assert src.res == (10.0, 10.0)

        # 255 must represent UNKNOWN / NoData in the output.
        assert src.nodata == 255

    expected = np.array([
        [1, 0],
        [0, 255],
    ], dtype=np.uint8)

    np.testing.assert_array_equal(
        result,
        expected,
    )

from scripts.processing.open_land_detector import generate_possible_open_mask


def test_v2_raster_applies_cloud_buffer(tmp_path):
    spectral_path = tmp_path / "spectral.tif"
    scl_path = tmp_path / "scl.tif"
    output_path = tmp_path / "possible_open_v2.tif"

    transform = from_origin(
        500000,
        1500000,
        10,
        10,
    )

    profile = {
        "driver": "GTiff",
        "height": 3,
        "width": 3,
        "count": 6,
        "dtype": "float32",
        "crs": "EPSG:32643",
        "transform": transform,
        "nodata": -9999.0,
    }

    # Make every pixel spectrally look possible-open
    b02 = np.full((3, 3), 0.08, dtype=np.float32)
    b03 = np.full((3, 3), 0.10, dtype=np.float32)
    b04 = np.full((3, 3), 0.10, dtype=np.float32)
    b08 = np.full((3, 3), 0.15, dtype=np.float32)
    b11 = np.full((3, 3), 0.20, dtype=np.float32)
    b12 = np.full((3, 3), 0.16, dtype=np.float32)

    with rasterio.open(
        spectral_path,
        "w",
        **profile,
    ) as dst:
        dst.write(b02, 1)
        dst.write(b03, 2)
        dst.write(b04, 3)
        dst.write(b08, 4)
        dst.write(b11, 5)
        dst.write(b12, 6)

    scl_profile = profile.copy()

    scl_profile.update(
        count=1,
        dtype="uint8",
        nodata=0,
    )

    scl = np.full(
        (3, 3),
        5,
        dtype=np.uint8,
    )

    # Central pixel = high-probability cloud
    scl[1, 1] = 9

    with rasterio.open(
        scl_path,
        "w",
        **scl_profile,
    ) as dst:
        dst.write(scl, 1)

    generate_possible_open_mask(
        spectral_path,
        scl_path,
        output_path,
        cloud_buffer_pixels=1,
    )

    with rasterio.open(output_path) as src:
        result = src.read(1)

    expected = np.full(
        (3, 3),
        255,
        dtype=np.uint8,
    )

    np.testing.assert_array_equal(
        result,
        expected,
    )