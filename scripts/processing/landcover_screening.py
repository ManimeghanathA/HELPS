"""Supplementary land-cover obstacle evidence, never a clearance certificate."""
import numpy as np

EXCLUDED_CLASSES = (10,20,50,70,80,90,95)
KNOWN_CLASSES = (0,10,20,30,40,50,60,70,80,90,95,100)


def screen_landcover(state, cover, buffer_pixels=1):
    if state.shape != cover.shape:
        raise ValueError('Land-cover and state shape must match')
    if buffer_pixels < 0:
        raise ValueError('Buffer must be non-negative')
    excluded = np.isin(cover,EXCLUDED_CLASSES)
    for _ in range(buffer_pixels):
        padded = np.pad(excluded,1)
        excluded = np.logical_or.reduce([padded[y:y+state.shape[0],x:x+state.shape[1]]
                                         for y in range(3) for x in range(3)])
    result = state.copy()
    result[excluded & (result != 255)] = 0
    result[(cover == 0) | ~np.isin(cover,KNOWN_CLASSES)] = 255
    return result, excluded
