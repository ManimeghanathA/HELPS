from pathlib import Path

import numpy as np
import rasterio


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATE = "2026-06-01"

BASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "Bhadra"
    / "sentinel2"
    / DATE
)

SPECTRAL_PATH = BASE_DIR / "bhadra_spectral.tif"
SCL_PATH = BASE_DIR / "bhadra_scl.tif"
STATE_PATH = BASE_DIR / "bhadra_possible_open_mask_v2.tif"


CLOUD_CLASSES = {8, 9, 10}


def percentile_report(
    name,
    values,
):
    values = values[
        np.isfinite(values)
    ]

    print()
    print(name)
    print("-" * 84)

    if len(values) == 0:
        print("No pixels")
        return

    for p in [
        1,
        5,
        10,
        25,
        50,
        75,
        90,
        95,
        99,
    ]:

        print(
            f"P{p:02d} : "
            f"{np.percentile(values, p):.4f}"
        )


print("=" * 84)
print("HELPSs — MISSED CLOUD SPECTRAL ANALYSIS")
print("=" * 84)


# ============================================================
# LOAD DATA
# ============================================================

with rasterio.open(SPECTRAL_PATH) as src:

    blue = src.read(1).astype(np.float32)
    green = src.read(2).astype(np.float32)
    red = src.read(3).astype(np.float32)
    nir = src.read(4).astype(np.float32)
    swir1 = src.read(5).astype(np.float32)
    swir2 = src.read(6).astype(np.float32)


with rasterio.open(SCL_PATH) as src:
    scl = src.read(1)


with rasterio.open(STATE_PATH) as src:
    state = src.read(1)


# ============================================================
# DERIVED FEATURES
# ============================================================

visible_brightness = (
    blue
    + green
    + red
) / 3.0


visible_max = np.maximum.reduce(
    [
        blue,
        green,
        red,
    ]
)

visible_min = np.minimum.reduce(
    [
        blue,
        green,
        red,
    ]
)


# Low value = spectrally white / neutral
whiteness = (
    visible_max
    - visible_min
)


denominator = (
    nir + red
)

ndvi = np.zeros_like(
    red,
    dtype=np.float32,
)

valid_ndvi = (
    np.abs(denominator)
    > 1e-8
)

ndvi[valid_ndvi] = (
    nir[valid_ndvi]
    - red[valid_ndvi]
) / denominator[valid_ndvi]


# ============================================================
# GROUPS
# ============================================================

known_cloud = np.isin(
    scl,
    list(CLOUD_CLASSES),
)

current_open = (
    state == 1
)

bare_scl = (
    scl == 5
)


print(
    f"Known cloud pixels : "
    f"{np.count_nonzero(known_cloud):,}"
)

print(
    f"Current OPEN pixels: "
    f"{np.count_nonzero(current_open):,}"
)

print(
    f"SCL bare pixels    : "
    f"{np.count_nonzero(bare_scl):,}"
)


# ============================================================
# REPORT IMPORTANT FEATURES
# ============================================================

for feature_name, feature in [

    (
        "VISIBLE BRIGHTNESS",
        visible_brightness,
    ),

    (
        "BLUE",
        blue,
    ),

    (
        "GREEN",
        green,
    ),

    (
        "RED",
        red,
    ),

    (
        "NIR",
        nir,
    ),

    (
        "SWIR1",
        swir1,
    ),

    (
        "WHITENESS RANGE",
        whiteness,
    ),

    (
        "NDVI",
        ndvi,
    ),
]:

    print()
    print("=" * 84)
    print(feature_name)
    print("=" * 84)

    percentile_report(
        "KNOWN CLOUD",
        feature[known_cloud],
    )

    percentile_report(
        "CURRENT OPEN",
        feature[current_open],
    )

    percentile_report(
        "SCL BARE / NON-VEGETATED",
        feature[bare_scl],
    )


# ============================================================
# HOW MANY OPEN PIXELS LOOK AS BRIGHT AS CLOUD?
# ============================================================

cloud_brightness_p05 = np.percentile(
    visible_brightness[
        known_cloud
    ],
    5,
)

cloud_brightness_p10 = np.percentile(
    visible_brightness[
        known_cloud
    ],
    10,
)


print()
print("=" * 84)
print("BRIGHT OPEN PIXEL CHECK")
print("=" * 84)

print(
    f"Cloud brightness P05 : "
    f"{cloud_brightness_p05:.4f}"
)

print(
    f"Cloud brightness P10 : "
    f"{cloud_brightness_p10:.4f}"
)


open_above_cloud_p05 = (
    current_open
    & (
        visible_brightness
        >= cloud_brightness_p05
    )
)

open_above_cloud_p10 = (
    current_open
    & (
        visible_brightness
        >= cloud_brightness_p10
    )
)


print(
    f"OPEN >= cloud P05 brightness : "
    f"{np.count_nonzero(open_above_cloud_p05):,}"
)

print(
    f"OPEN >= cloud P10 brightness : "
    f"{np.count_nonzero(open_above_cloud_p10):,}"
)


# ============================================================
# EXTRA: BRIGHT + WHITE OPEN PIXELS
# ============================================================

cloud_whiteness_p75 = np.percentile(
    whiteness[
        known_cloud
    ],
    75,
)


suspect_open = (
    current_open
    & (
        visible_brightness
        >= cloud_brightness_p05
    )
    & (
        whiteness
        <= cloud_whiteness_p75
    )
)


print()
print("=" * 84)
print("PRELIMINARY SUSPECT PIXELS")
print("=" * 84)

print(
    f"Cloud whiteness P75        : "
    f"{cloud_whiteness_p75:.4f}"
)

print(
    f"Bright + cloud-like OPEN   : "
    f"{np.count_nonzero(suspect_open):,}"
)

print()
print(
    "Do NOT use this as a filter yet."
)

print(
    "This diagnostic only tells us whether "
    "cloud-like OPEN pixels exist."
)

print("=" * 84)