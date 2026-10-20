"""Versioned precision-first screening; these rules do not certify landing safety."""
import numpy as np
from scripts.processing.open_land_detector import classify_open_pixels, POSSIBLE_OPEN, NOT_OPEN

POLICY_ID = 'conservative-ground-v1'
NDVI_MAX = 0.20
BUILDING_UNCERTAINTY_BUFFER_M = 10.0


def classify_conservative_pixels(scl, ndvi, mndwi):
    state = classify_open_pixels(scl, ndvi, mndwi)
    # SCL alone cannot distinguish bare yards/roofs from empty ground. This
    # stricter vegetation gate is independent of the provider's SCL 4/5 label.
    # Only bare-class pixels survive; genuinely usable grass may be withheld.
    retain = (scl == 5) & np.isfinite(ndvi) & (ndvi <= NDVI_MAX)
    state[(state == POSSIBLE_OPEN) & ~retain] = NOT_OPEN
    return state
