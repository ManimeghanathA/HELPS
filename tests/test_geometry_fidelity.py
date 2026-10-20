"""Regression coverage for excluded interiors, disconnected parts and source CRS."""
import geopandas as gpd
import pytest
from shapely.geometry import MultiPolygon, Polygon, box, shape

from landing_zone_engine import LandingZoneEngine


@pytest.fixture(params=[32643, 32644])
def terrain_engine(tmp_path, request):
    polygon = Polygon(box(500000, 1500000, 500100, 1500100).exterior.coords,
                      [box(500030, 1500030, 500060, 1500060).exterior.coords])
    multipart = MultiPolygon([polygon, box(500150, 1500000, 500200, 1500050)])
    rows = []
    for index, geom in enumerate([polygon, multipart]):
        rows.append(dict(zone_id=f'zone-{index}', parent_candidate_id=index,
                         area_m2=geom.area, length_m=200., width_m=100.,
                         max_clear_radius_m=20., max_clear_diameter_m=40., geometry=geom))
    zones = gpd.GeoDataFrame(rows, crs=request.param)
    centers = gpd.GeoDataFrame({'zone_id': zones.zone_id},
                              geometry=zones.representative_point(), crs=zones.crs)
    folder = tmp_path / 'processed/Bhadra/sentinel2/2026-06-01'
    folder.mkdir(parents=True)
    path = folder / 'bhadra_final_open_land_zones.gpkg'
    zones.to_file(path, layer='final_open_land_zones', driver='GPKG')
    centers.to_file(path, layer='maximum_clearance_centers', driver='GPKG')
    # GPKG may promote a mixed Polygon/MultiPolygon layer to MultiPolygon.
    # Compare against what is actually stored, not the pre-write frame.
    stored = gpd.read_file(path, layer='final_open_land_zones')
    return LandingZoneEngine(tmp_path), stored


def assert_matches_source(records, source):
    assert len(records) == len(source)
    for record, original in zip(records, source.geometry):
        exported = shape(record['geometry'])
        restored = gpd.GeoSeries([exported], crs=4326).to_crs(source.crs).iloc[0]
        assert restored.symmetric_difference(original).area < 1e-5
        assert exported.geom_type == original.geom_type


def test_engine_preserves_complete_polygon_geometry_and_crs(terrain_engine):
    engine, source = terrain_engine
    assert_matches_source(engine.zones, source)


def test_map_and_ranked_endpoints_preserve_same_geometry(terrain_engine, monkeypatch):
    import app as web
    engine, source = terrain_engine
    monkeypatch.setattr(web, 'landing_engine', engine)
    client = web.app.test_client()
    response = client.get('/api/gpkg-zones')
    assert response.status_code == 200
    assert_matches_source(response.get_json()['features'], source)
    first = engine.zones[0]
    response = client.post('/api/landing-zones', json={
        'latitude': first['latitude'], 'longitude': first['longitude'], 'radius_km': 1,
    })
    assert response.status_code == 200
    spots = sorted(response.get_json()['spots'], key=lambda item: item['zone_id'])
    assert_matches_source(spots, source)


def test_reviewed_negative_is_withheld_from_existing_dataset(terrain_engine):
    engine, source = terrain_engine
    folder = engine.data_root/'raw/reviewed-site'
    folder.mkdir(parents=True)
    source.iloc[:1].to_crs(4326).to_file(folder/'reviewed_exclusions.geojson',driver='GeoJSON')
    engine._load_datasets()
    assert engine.total_zones == 0
