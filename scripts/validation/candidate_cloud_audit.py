import numpy as np

from rasterio.features import rasterize


UNKNOWN = 255


def audit_unknown_overlap(
    zones,
    state,
    transform,
    raster_crs,
):
    """
    Audit whether candidate zones occupy UNKNOWN pixels.

    UNKNOWN includes cloud / cloud shadow / unusable
    observations from the Sentinel classification pipeline.
    """

    if zones.empty:

        return {
            "unknown_overlap_pixels": 0,
            "zones_with_unknown_overlap": 0,
        }

    if zones.crs != raster_crs:

        zones = zones.to_crs(
            raster_crs
        )

    unknown_mask = (
        state == UNKNOWN
    )

    # Rasterize all zones onto the Sentinel grid.
    zone_mask = rasterize(
        (
            (geom, 1)
            for geom in zones.geometry
            if geom is not None
            and not geom.is_empty
        ),
        out_shape=state.shape,
        transform=transform,
        fill=0,
        dtype="uint8",

        # Pixel-centre rule is preferable here.
        # all_touched=True could falsely count zones that
        # merely touch an UNKNOWN pixel boundary.
        all_touched=False,
    )

    unknown_overlap = (
        (zone_mask == 1)
        & unknown_mask
    )

    unknown_overlap_pixels = int(
        np.count_nonzero(
            unknown_overlap
        )
    )

    # Count individual zones with UNKNOWN overlap.
    zones_with_unknown_overlap = 0

    for geom in zones.geometry:

        if geom is None or geom.is_empty:
            continue

        individual_mask = rasterize(
            [(geom, 1)],
            out_shape=state.shape,
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=False,
        )

        if np.any(
            (individual_mask == 1)
            & unknown_mask
        ):

            zones_with_unknown_overlap += 1

    return {
        "unknown_overlap_pixels":
            unknown_overlap_pixels,

        "zones_with_unknown_overlap":
            zones_with_unknown_overlap,
    }