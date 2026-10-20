import numpy as np
import pytest
from scripts.processing.landcover_screening import screen_landcover


def test_obstacles_and_missing_coverage_withhold_bare_spectral_pixels():
    state = np.ones((1,9),dtype='uint8')
    cover = np.array([[10,20,50,80,90,95,0,40,60]],dtype='uint8')
    result, excluded = screen_landcover(state,cover,buffer_pixels=0)
    assert result.tolist() == [[0,0,0,0,0,0,255,1,1]]
    assert excluded.tolist() == [[True,True,True,True,True,True,False,False,False]]


def test_obstacle_uncertainty_buffer_and_existing_unknown_are_preserved():
    state = np.ones((5,5),dtype='uint8'); state[2,2]=255
    cover = np.full((5,5),60,dtype='uint8'); cover[2,2]=10
    result, excluded = screen_landcover(state,cover,buffer_pixels=1)
    assert excluded.sum()==9
    assert result[2,2]==255
    assert result[1,1]==0
    assert result[0,0]==1


def test_landcover_grid_mismatch_is_rejected():
    with pytest.raises(ValueError,match='shape'):
        screen_landcover(np.ones((3,3),dtype='uint8'),np.ones((2,2),dtype='uint8'))
