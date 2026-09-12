import geopandas as gpd
import numpy as np

from rasterio.transform import from_origin
from shapely.geometry import box

from scripts.validation.candidate_cloud_audit import (
    audit_unknown_overlap,
)


def test_zone_overlapping_unknown_pixel_is_detected():

    # 3 x 3 raster, 10 m pixels
    state = np.array(
        [
            [1,   1,   1],
            [1, 255,   1],
            [1,   1,   1],
        ],
        dtype=np.uint8,
    )

    transform = from_origin(
        0,
        30,
        10,
        10,
    )

    # Polygon covers centre pixel
    zones = gpd.GeoDataFrame(
        {
            "zone_id": ["TEST_ZONE"],
        },
        geometry=[
            box(
                10,
                10,
                20,
                20,
            )
        ],
        crs="EPSG:32643",
    )

    result = audit_unknown_overlap(
        zones=zones,
        state=state,
        transform=transform,
        raster_crs="EPSG:32643",
    )

    assert result["unknown_overlap_pixels"] == 1
    assert result["zones_with_unknown_overlap"] == 1