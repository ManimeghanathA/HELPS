from shapely.ops import polylabel


def measure_maximum_clearance(
    polygon,
    tolerance_m=0.5,
):
    """
    Find the approximate Pole of Inaccessibility:
    the point inside a polygon having maximum
    distance from its boundary.

    This gives the maximum inscribed-circle
    radius and clear diameter.
    """

    if polygon is None or polygon.is_empty:

        return {
            "center": None,
            "radius_m": 0.0,
            "diameter_m": 0.0,
        }

    # Handle MultiPolygon defensively
    if polygon.geom_type == "MultiPolygon":

        best = None

        for part in polygon.geoms:

            result = measure_maximum_clearance(
                part,
                tolerance_m=tolerance_m,
            )

            if (
                best is None
                or result["radius_m"]
                > best["radius_m"]
            ):
                best = result

        return best

    if polygon.geom_type != "Polygon":

        return {
            "center": None,
            "radius_m": 0.0,
            "diameter_m": 0.0,
        }

    center = polylabel(
        polygon,
        tolerance=tolerance_m,
    )

    radius_m = center.distance(
        polygon.boundary
    )

    return {
        "center": center,
        "radius_m": float(radius_m),
        "diameter_m": float(
            radius_m * 2.0
        ),
    }