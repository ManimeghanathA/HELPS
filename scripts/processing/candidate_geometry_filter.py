import math


def measure_candidate_geometry(
    polygon,
):
    """
    Measure candidate polygon geometry using
    its minimum rotated rectangle.

    Returns:
        {
            "area_m2": ...,
            "length_m": ...,
            "width_m": ...
        }
    """

    if polygon is None or polygon.is_empty:

        return {
            "area_m2": 0.0,
            "length_m": 0.0,
            "width_m": 0.0,
        }


    area_m2 = float(
        polygon.area
    )


    rectangle = (
        polygon.minimum_rotated_rectangle
    )


    coords = list(
        rectangle.exterior.coords
    )


    # Rectangle has 5 coordinates:
    # first point repeated at the end
    side_lengths = []


    for i in range(4):

        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]

        distance = math.hypot(
            x2 - x1,
            y2 - y1,
        )

        side_lengths.append(
            distance
        )


    # Opposite rectangle sides are equal.
    # We only need the two unique dimensions.
    dim1 = side_lengths[0]
    dim2 = side_lengths[1]


    length_m = max(
        dim1,
        dim2,
    )

    width_m = min(
        dim1,
        dim2,
    )


    return {
        "area_m2": area_m2,
        "length_m": float(length_m),
        "width_m": float(width_m),
    }


def passes_geometry_gate(
    polygon,
    min_area_m2=900,
    min_length_m=30,
    min_width_m=30,
):
    """
    Return True if polygon satisfies the
    initial HELPSs geometry thresholds.
    """

    measurements = (
        measure_candidate_geometry(
            polygon
        )
    )


    return (
        measurements["area_m2"]
        >= min_area_m2

        and measurements["length_m"]
        >= min_length_m

        and measurements["width_m"]
        >= min_width_m
    )