from pathlib import Path
import json
import sqlite3
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box
from scripts.knowledge.repository import write_package,validate_package,activate_dataset,KnowledgeRepository,register_dataset


def package_data():
    terrain=gpd.GeoDataFrame({'terrain_id':['p'],'source_zone_id':['p'],'dataset_id':['d']},geometry=[box(500000,1500000,500120,1500120)],crs=32643)
    zones=gpd.GeoDataFrame({'zone_id':['z'],'terrain_id':['p'],'dataset_id':['d'],'slope_threshold_deg':[4],'mean_slope_deg':[3],'max_slope_deg':[4],'dem_valid_fraction':[1]},geometry=[box(500010,1500010,500110,1500110)],crs=32643)
    return {'metadata':{'dataset_id':'d','region_id':'r','date':'2026-10-13'},'terrain':terrain,'zones':zones,'characteristics':pd.DataFrame([{'terrain_id':'p','surface_state':'unknown','mean_roughness_m':.5}]),'environment':pd.DataFrame([{'zone_id':'z','road_distance_m':25,'restriction_state':'unknown'}]),'sources':{'dem':{'source_id':'dem','sha256':'abc','crs':'EPSG:32643'}},'lineage':pd.DataFrame([{'terrain_id':'p','zone_id':'z','status':'accepted'}])}


def test_package_persists_real_foreign_keys_index_and_joined_records(tmp_path):
    path=tmp_path/'knowledge.gpkg'
    report=write_package(package_data(),path)
    assert report['valid'] and validate_package(path)['valid']
    with sqlite3.connect(path) as db:
        assert db.execute('pragma foreign_key_list(zones)').fetchall()
        assert db.execute('pragma foreign_key_check').fetchall()==[]
        assert db.execute('select count(*) from rtree_zones_geom').fetchone()[0]==1
    gis=gpd.read_file(path,layer='zones')
    assert gis.geometry.iloc[0].equals(package_data()['zones'].geometry.iloc[0])
    repo=KnowledgeRepository(path)
    assert repo.dataset_id=='d' and repo.region_id=='r'
    rows=repo.query_zones(bounds=(500000,1500000,500200,1500200),internal=True)
    assert rows[0]['metric_geometry'].area==10000
    assert rows[0]['road_distance_m']==25 and rows[0]['mean_roughness_m']==.5
    assert repo.query_zones(bounds=(0,0,1,1))==[]
    assert repo.get_terrain('p')['child_zone_count']==1
    assert repo.to_geojson(rows)['features'][0]['geometry']['type']=='Polygon'


def test_parent_clearance_is_validated_from_normalized_characteristics(tmp_path):
    data=package_data();data['terrain']['max_clear_radius_m']=60;data['terrain']['max_clear_diameter_m']=120
    data['characteristics'].loc[0,'poi_easting']=500060;data['characteristics'].loc[0,'poi_northing']=1500060
    data['characteristics'].loc[0,'max_clear_radius_m']=60;data['characteristics'].loc[0,'max_clear_diameter_m']=120
    path=tmp_path/'knowledge.gpkg';assert write_package(data,path)['valid']
    assert KnowledgeRepository(path).get_terrain('p')['poi_easting']==500060


def test_duplicate_or_missing_parent_fails_before_publication(tmp_path):
    data=package_data(); data['zones'].terrain_id=['missing']
    path=tmp_path/'knowledge.gpkg'
    with pytest.raises(ValueError,match='parent'):
        write_package(data,path)
    assert not path.exists()
    data=package_data(); data['terrain']=pd.concat([data['terrain'],data['terrain']])
    with pytest.raises(ValueError,match='unique'):
        write_package(data,path)


def test_explicit_activation_failure_keeps_previous_pointer(tmp_path):
    path=tmp_path/'d'/'knowledge.gpkg'; path.parent.mkdir()
    write_package(package_data(),path)
    registry=tmp_path/'registry.json'
    register_dataset('d',path,registry)
    assert json.loads(registry.read_text())['selected']=={}
    activate_dataset('d',registry)
    previous=registry.read_bytes()
    with pytest.raises(ValueError): activate_dataset('absent',registry)
    assert registry.read_bytes()==previous
    with sqlite3.connect(path) as db: db.execute('delete from rtree_zones_geom')
    assert not validate_package(path)['valid']
    with pytest.raises(ValueError): activate_dataset('d',registry)
    assert registry.read_bytes()==previous


def test_immutable_package_cannot_be_overwritten(tmp_path):
    path=tmp_path/'knowledge.gpkg'; write_package(package_data(),path)
    with pytest.raises(FileExistsError): write_package(package_data(),path)

def test_corrupt_stored_clearance_or_area_invalidates_package(tmp_path):
    import json
    path=tmp_path/'knowledge.gpkg'; data=package_data()
    data['zones']['area_m2']=10000
    data['zones']['poi_easting']=500060; data['zones']['poi_northing']=1500060
    data['zones']['max_clear_radius_m']=50
    write_package(data,path)
    with sqlite3.connect(path) as db:
        row=json.loads(db.execute('SELECT record_json FROM zones').fetchone()[0]); row['max_clear_radius_m']=500
        db.execute('UPDATE zones SET record_json=?',(json.dumps(row),))
    assert not validate_package(path)['valid']
