def extract_operational_zones(
    polygon,
    clearance_radius_m=15.0,
):
    """
    Remove narrow connections from a candidate while
    preserving the physical usable surface.

    Process
    -------
    1. Erode the entire candidate by the required radius.
    2. Narrow necks / thin corridors disappear.
    3. Dilate the entire surviving geometry back once.
    4. Clip reconstruction to the original candidate.
    5. Return disconnected Polygon components.

    Important
    ---------
    Reconstruction is performed on the complete eroded
    geometry, NOT independently for every clearance core.

    This prevents independently reconstructed child zones
    from overlapping each other.
    """

    if polygon is None or polygon.is_empty:
        return []

    if clearance_radius_m <= 0:
        return [polygon]

    # --------------------------------------------------------
    # STEP 1: inward clearance
    # --------------------------------------------------------

    eroded = polygon.buffer(
        -clearance_radius_m
    )

    if eroded.is_empty:
        return []


    # --------------------------------------------------------
    # STEP 2: reconstruct once from the COMPLETE eroded shape
    # --------------------------------------------------------

    reconstructed = eroded.buffer(
        clearance_radius_m
    )


    # Never permit reconstructed land outside the
    # original candidate.
    reconstructed = reconstructed.intersection(
        polygon
    )


    if reconstructed.is_empty:
        return []


    # --------------------------------------------------------
    # STEP 3: extract independent connected polygons
    # --------------------------------------------------------

    if reconstructed.geom_type == "Polygon":

        return [
            reconstructed
        ]


    if reconstructed.geom_type == "MultiPolygon":

        return [
            part
            for part in reconstructed.geoms
            if (
                not part.is_empty
                and part.area > 0
            )
        ]


    if reconstructed.geom_type == "GeometryCollection":

        return [
            part
            for part in reconstructed.geoms
            if (
                part.geom_type == "Polygon"
                and not part.is_empty
                and part.area > 0
            )
        ]


    return []