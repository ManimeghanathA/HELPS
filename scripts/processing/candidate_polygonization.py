import geopandas as gpd
import numpy as np

from rasterio.features import shapes
from shapely.geometry import shape


OPEN = 1


def polygonize_open_mask(
    state,
    transform,
    crs,
):
    """
    Convert connected OPEN=1 raster regions
    into vector polygons.

    Parameters
    ----------
    state : np.ndarray
        Classification raster.
        OPEN pixels must have value 1.

    transform : rasterio.Affine
        Raster geotransform.

    crs : CRS-like
        CRS for output GeoDataFrame.

    Returns
    -------
    geopandas.GeoDataFrame
        One polygon feature per connected
        OPEN raster region.
    """

    open_mask = (
        state == OPEN
    )

    geometries = []

    for geom, value in shapes(
        state.astype(np.uint8),
        mask=open_mask,
        transform=transform,
        connectivity=8,
    ):

        if int(value) != OPEN:
            continue

        polygon = shape(
            geom
        )

        if polygon.is_empty:
            continue

        geometries.append(
            polygon
        )

    return gpd.GeoDataFrame(
        {
            "component_id": range(
                1,
                len(geometries) + 1,
            )
        },
        geometry=geometries,
        crs=crs,
    )