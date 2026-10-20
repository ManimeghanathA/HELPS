import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box
from scripts.pipeline.run_aoi_pipeline import _read_osm_layer


def test_conservative_rule_rejects_vegetation_even_when_scl_calls_it_bare():
    from scripts.processing.conservative_screening import classify_conservative_pixels
    scl = np.array([[5, 5, 4, 6, 9]], dtype='uint8')
    ndvi = np.array([[.1, .3, .1, .05, .1]], dtype='float32')
    mndwi = np.full(scl.shape, -.3, dtype='float32')
    assert classify_conservative_pixels(scl, ndvi, mndwi).tolist() == [[1, 0, 0, 0, 255]]


def test_required_missing_osm_layer_is_an_error(tmp_path):
    path = tmp_path/'osm.gpkg'
    gpd.GeoDataFrame(geometry=[box(75,13,75.01,13.01)], crs=4326).to_file(path, layer='buildings')
    with pytest.raises(ValueError, match='Required OSM'):
        _read_osm_layer(path, 'industrial', lambda _: None)


def test_empty_but_present_exclusion_layer_is_accepted(tmp_path):
    path = tmp_path/'osm.gpkg'
    gpd.GeoDataFrame(geometry=[], crs=4326).to_file(path, layer='industrial')
    assert _read_osm_layer(path, 'industrial', lambda _: None).empty


def test_exclusion_audit_rejects_a_valid_zone_on_a_facility():
    from scripts.pipeline.processing import audit
    from rasterio.transform import from_origin
    zones = gpd.GeoDataFrame([{'zone_id':'bad','area_m2':10000.,'max_clear_diameter_m':100.,
                              'geometry':box(0,0,100,100)}], crs=32643)
    empty = gpd.GeoDataFrame(geometry=[], crs=32643)
    facility = gpd.GeoDataFrame(geometry=[box(10,10,50,50)], crs=32643)
    state = np.ones((10,10),dtype='uint8'); scl = np.full((10,10),5,dtype='uint8')
    with pytest.raises(ValueError, match='audit failed'):
        audit(zones, empty, state, scl, from_origin(0,100,10,10),
              log=lambda _:None, exclusions={'facilities':facility})


def test_osm_requests_are_bounded_on_provider_failure():
    import requests
    from scripts.pipeline.acquisition import fetch_osm_response
    class FailingSession:
        calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            raise requests.Timeout('provider timed out')
    session = FailingSession()
    aoi = gpd.GeoDataFrame(geometry=[box(75,13,75.01,13.01)], crs=4326)
    with pytest.raises(RuntimeError, match='OSM acquisition failed'):
        fetch_osm_response(aoi, {'natural':'water'}, lambda _:None, session=session)
    from scripts.pipeline.acquisition import OVERPASS_ENDPOINTS
    assert session.calls == len(OVERPASS_ENDPOINTS)


def test_facility_points_are_not_dropped():
    from shapely.geometry import Point
    from scripts.pipeline.processing import prepare_facility_exclusion
    frame = gpd.GeoDataFrame(geometry=[Point(500000,1500000)],crs=32643)
    prepared = prepare_facility_exclusion(frame)
    assert len(prepared) == 1
    assert prepared.geometry.iloc[0].covers(frame.geometry.iloc[0])


def test_acquisition_halo_preserves_an_exterior_facility():
    from shapely.geometry import Point
    from scripts.pipeline.acquisition import hazard_query_aoi
    aoi = gpd.GeoDataFrame(geometry=[box(500000,1500000,500100,1500100)],crs=32643)
    facility = Point(499995,1500050)
    assert hazard_query_aoi(aoi).to_crs(32643).geometry.iloc[0].covers(facility)
