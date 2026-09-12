def extract_clearance_cores(
    polygon,
    clearance_radius_m,
):
    """
    Shrink a candidate polygon inward by the required
    clearance radius and return each disconnected
    surviving polygon as a separate clearance core.

    Important:
    This does NOT permanently replace the original
    candidate polygon. It is used to understand whether
    the candidate contains one or multiple independently
    usable regions.
    """

    if polygon is None or polygon.is_empty:
        return []

    if clearance_radius_m <= 0:
        return [polygon]

    # Inward buffer:
    # removes regions that cannot maintain the required
    # clearance from the polygon boundary.
    eroded = polygon.buffer(
        -clearance_radius_m
    )

    if eroded.is_empty:
        return []

    if eroded.geom_type == "Polygon":
        return [eroded]

    if eroded.geom_type == "MultiPolygon":
        return [
            part
            for part in eroded.geoms
            if not part.is_empty
        ]

    if eroded.geom_type == "GeometryCollection":
        return [
            part
            for part in eroded.geoms
            if (
                part.geom_type == "Polygon"
                and not part.is_empty
            )
        ]

    return []