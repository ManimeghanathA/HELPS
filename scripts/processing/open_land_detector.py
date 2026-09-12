from pathlib import Path

import numpy as np
import rasterio


# ============================================================
# HELPSs STATE VALUES
# ============================================================

NOT_OPEN = 0
POSSIBLE_OPEN = 1
UNKNOWN = 255


# ============================================================
# V1 THRESHOLDS
# ============================================================

V1_NDVI_OPEN_MAX = 0.45
V1_MNDWI_OPEN_MAX = 0.0


# ============================================================
# V2 THRESHOLDS
# ============================================================

V2_NDVI_OPEN_MAX = 0.50
V2_MNDWI_OPEN_MAX = 0.0


# ============================================================
# SCL GROUPS
# ============================================================

UNKNOWN_SCL_CLASSES = {
    0,   # No Data
    1,   # Saturated / defective
    2,   # Topographic shadow
    3,   # Cloud shadow
    7,   # Unclassified
    8,   # Cloud medium probability
    9,   # Cloud high probability
    10,  # Thin cirrus
    11,  # Snow / ice
}


OBSERVABLE_SCL_CLASSES = {
    4,   # Vegetation
    5,   # Bare / non-vegetated
    6,   # Water
}


# ============================================================
# NORMALIZED DIFFERENCE
# ============================================================

def safe_normalized_difference(a, b):
    """
    Calculate:

        (a - b) / (a + b)

    safely.
    """

    denominator = a + b

    result = np.full(
        a.shape,
        np.nan,
        dtype=np.float32,
    )

    valid = np.abs(denominator) > 1e-6

    result[valid] = (
        (a[valid] - b[valid])
        / denominator[valid]
    )

    return result


# ============================================================
# V1 CLASSIFICATION
# ============================================================

def classify_open_pixels_v1(
    scl,
    ndvi,
    mndwi,
):
    """
    Original conservative baseline detector.

    POSSIBLE_OPEN only when:

        SCL == 5
        NDVI <= 0.45
        MNDWI < 0
    """

    if not (
        scl.shape
        == ndvi.shape
        == mndwi.shape
    ):
        raise ValueError(
            "SCL, NDVI and MNDWI arrays must have identical shapes."
        )

    result = np.full(
        scl.shape,
        NOT_OPEN,
        dtype=np.uint8,
    )

    unknown = np.isin(
        scl,
        list(UNKNOWN_SCL_CLASSES),
    )

    unknown |= (
        ~np.isfinite(ndvi)
        | ~np.isfinite(mndwi)
    )

    result[unknown] = UNKNOWN

    open_mask = (
        (scl == 5)
        & np.isfinite(ndvi)
        & np.isfinite(mndwi)
        & (ndvi <= V1_NDVI_OPEN_MAX)
        & (mndwi < V1_MNDWI_OPEN_MAX)
    )

    result[open_mask] = POSSIBLE_OPEN

    return result


# ============================================================
# V2 CLASSIFICATION
# ============================================================

def classify_open_pixels(
    scl,
    ndvi,
    mndwi,
):
    """
    HELPSs V2 possible-open detector.

    Output:

        0   = NOT_OPEN
        1   = POSSIBLE_OPEN
        255 = UNKNOWN

    POSSIBLE_OPEN means the observed surface does not show
    strong evidence of dense vegetation or water.

    This does NOT yet prove that the terrain is empty or
    helicopter-landable.
    """

    if not (
        scl.shape
        == ndvi.shape
        == mndwi.shape
    ):
        raise ValueError(
            "SCL, NDVI and MNDWI arrays must have identical shapes."
        )

    result = np.full(
        scl.shape,
        NOT_OPEN,
        dtype=np.uint8,
    )

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    unknown = np.isin(
        scl,
        list(UNKNOWN_SCL_CLASSES),
    )

    unknown |= (
        ~np.isfinite(ndvi)
        | ~np.isfinite(mndwi)
    )

    result[unknown] = UNKNOWN

    # --------------------------------------------------------
    # OBSERVABLE
    # --------------------------------------------------------

    observable = np.isin(
        scl,
        list(OBSERVABLE_SCL_CLASSES),
    )

    # --------------------------------------------------------
    # POSSIBLE OPEN
    # --------------------------------------------------------

    possible_open = (
        observable
        & (scl != 6)
        & np.isfinite(ndvi)
        & np.isfinite(mndwi)
        & (ndvi <= V2_NDVI_OPEN_MAX)
        & (mndwi < V2_MNDWI_OPEN_MAX)
    )

    result[possible_open] = POSSIBLE_OPEN

    # Explicit water protection
    result[scl == 6] = NOT_OPEN

    return result


# ============================================================
# CLOUD EDGE BUFFER
# ============================================================

def apply_cloud_edge_buffer(
    state,
    scl,
    buffer_pixels=1,
):
    """
    Expand cloud/cloud-shadow regions and mark their neighbors UNKNOWN.

    At 10 m Sentinel resolution:

        1 pixel = 10 m
        2 pixels = 20 m
    """

    if state.shape != scl.shape:
        raise ValueError(
            "State and SCL arrays must have identical shapes."
        )

    if buffer_pixels < 0:
        raise ValueError(
            "buffer_pixels cannot be negative."
        )

    if buffer_pixels == 0:
        return state.copy()

    cloud_classes = {
        3,   # Cloud shadow
        8,   # Cloud medium probability
        9,   # Cloud high probability
        10,  # Thin cirrus
    }

    cloud_mask = np.isin(
        scl,
        list(cloud_classes),
    )

    expanded = cloud_mask.copy()

    for _ in range(buffer_pixels):

        current = expanded.copy()

        # Vertical
        expanded[1:, :] |= current[:-1, :]
        expanded[:-1, :] |= current[1:, :]

        # Horizontal
        expanded[:, 1:] |= current[:, :-1]
        expanded[:, :-1] |= current[:, 1:]

        # Diagonals
        expanded[1:, 1:] |= current[:-1, :-1]
        expanded[:-1, :-1] |= current[1:, 1:]

        expanded[1:, :-1] |= current[:-1, 1:]
        expanded[:-1, 1:] |= current[1:, :-1]

    result = state.copy()

    result[expanded] = UNKNOWN

    return result


# ============================================================
# COMMON RASTER READER
# ============================================================

def _read_inputs(
    spectral_path,
    scl_path,
):
    spectral_path = Path(spectral_path)
    scl_path = Path(scl_path)

    if not spectral_path.exists():
        raise FileNotFoundError(
            f"Spectral raster not found:\n{spectral_path}"
        )

    if not scl_path.exists():
        raise FileNotFoundError(
            f"SCL raster not found:\n{scl_path}"
        )

    with rasterio.open(spectral_path) as src:

        if src.count < 6:
            raise ValueError(
                "Spectral raster must contain at least 6 bands."
            )

        b02 = src.read(1).astype(np.float32)
        b03 = src.read(2).astype(np.float32)
        b04 = src.read(3).astype(np.float32)
        b08 = src.read(4).astype(np.float32)
        b11 = src.read(5).astype(np.float32)
        b12 = src.read(6).astype(np.float32)

        profile = src.profile.copy()

        spectral_shape = (
            src.height,
            src.width,
        )

        spectral_crs = src.crs
        spectral_transform = src.transform

    with rasterio.open(scl_path) as src:

        scl = src.read(1).astype(np.uint8)

        scl_shape = (
            src.height,
            src.width,
        )

        scl_crs = src.crs
        scl_transform = src.transform

    if spectral_shape != scl_shape:
        raise ValueError(
            "Spectral and SCL dimensions do not match."
        )

    if spectral_crs != scl_crs:
        raise ValueError(
            "Spectral and SCL CRS do not match."
        )

    if spectral_transform != scl_transform:
        raise ValueError(
            "Spectral and SCL transforms do not match."
        )

    return (
        b02,
        b03,
        b04,
        b08,
        b11,
        b12,
        scl,
        profile,
    )


# ============================================================
# COMMON OUTPUT WRITER
# ============================================================

def _write_state_raster(
    state,
    profile,
    output_path,
):
    output_path = Path(output_path)

    output_profile = profile.copy()

    output_profile.update(
        driver="GTiff",
        count=1,
        dtype="uint8",
        nodata=UNKNOWN,
        compress="lzw",
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with rasterio.open(
        output_path,
        "w",
        **output_profile,
    ) as dst:

        dst.write(
            state,
            1,
        )

    return output_path


# ============================================================
# V1 RASTER GENERATOR
# ============================================================

def generate_open_land_mask(
    spectral_path,
    scl_path,
    output_path,
):
    """
    Generate the original V1 baseline mask.
    """

    (
        b02,
        b03,
        b04,
        b08,
        b11,
        b12,
        scl,
        profile,
    ) = _read_inputs(
        spectral_path,
        scl_path,
    )

    ndvi = safe_normalized_difference(
        b08,
        b04,
    )

    mndwi = safe_normalized_difference(
        b03,
        b11,
    )

    state = classify_open_pixels_v1(
        scl,
        ndvi,
        mndwi,
    )

    return _write_state_raster(
        state,
        profile,
        output_path,
    )


# ============================================================
# V2 RASTER GENERATOR
# ============================================================

def generate_possible_open_mask(
    spectral_path,
    scl_path,
    output_path,
    cloud_buffer_pixels=1,
):
    """
    Generate HELPSs V2 possible-open mask.
    """

    (
        b02,
        b03,
        b04,
        b08,
        b11,
        b12,
        scl,
        profile,
    ) = _read_inputs(
        spectral_path,
        scl_path,
    )

    ndvi = safe_normalized_difference(
        b08,
        b04,
    )

    mndwi = safe_normalized_difference(
        b03,
        b11,
    )

    state = classify_open_pixels(
        scl,
        ndvi,
        mndwi,
    )

    state = apply_cloud_edge_buffer(
        state,
        scl,
        buffer_pixels=cloud_buffer_pixels,
    )

    return _write_state_raster(
        state,
        profile,
        output_path,
    )