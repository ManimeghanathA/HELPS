import geopandas as gpd
import numpy as np
from shapely.geometry import box, LineString
from scripts.knowledge.environment import characterize_environment


def zone():
    return gpd.GeoDataFrame({'zone_id':['z'],'terrain_id':['p']},geometry=[box(0,0,20,20)],crs=32643)


def test_measured_distances_do_not_invent_access_or_missing_water():
    roads=gpd.GeoDataFrame({'highway':['track']},geometry=[LineString([(50,-50),(50,100)])],crs=32643)
    row=characterize_environment(zone(),{'roads':roads}).iloc[0]
    assert row.road_distance_m==30
    assert row.road_access_state=='unknown'
    assert row.water_distance_m is None
    assert row.obstacle_height_state=='unknown'
    assert row.restriction_state=='unknown'


def test_overlapping_mapped_obstacles_count_area_once():
    obstacles=gpd.GeoDataFrame(geometry=[box(20,0,40,20),box(20,0,40,20)],crs=32643)
    row=characterize_environment(zone(),{'buildings':obstacles},analysis_radius_m=40).iloc[0]
    assert np.isclose(row.mapped_obstacle_fraction,400/zone().geometry.iloc[0].buffer(40).area)
    assert row.context_coverage_state=='unknown'
    assert row.openness_score<1


def test_empty_verified_source_distinct_from_missing_source():
    empty=gpd.GeoDataFrame({'geometry':[]},geometry='geometry',crs=32643)
    empty.attrs['coverage_state']='verified'; empty.attrs['coverage_geometry']=box(-500,-500,500,500)
    row=characterize_environment(zone(),{'roads':empty,'buildings':empty}).iloc[0]
    assert row.road_state=='verified_no_mapped_features'
    assert row.mapped_obstacle_fraction==0
    assert row.openness_score==1
    missing=characterize_environment(zone(),{}).iloc[0]
    assert missing.openness_score is None
    assert missing.mapped_obstacle_fraction is None

def test_surrounding_dated_vegetation_support_is_measured(tmp_path):
    import rasterio
    from scripts.knowledge.contracts import SourceAsset
    path=tmp_path/'scl.tif'
    with rasterio.open(path,'w',driver='GTiff',width=10,height=10,count=1,dtype='uint8',crs=32643,transform=rasterio.transform.from_origin(-40,60,10,10),nodata=0) as ds: ds.write(np.full((10,10),4,dtype='uint8'),1)
    row=characterize_environment(zone(),{'scl':SourceAsset('scl',path,kind='scl',date='2026-06-01')},analysis_radius_m=20).iloc[0]
    observation=row.context_surface_observations['scl']
    assert np.isclose(observation['vegetation_fraction'],1)
    assert np.isclose(observation['valid_fraction'],1)
    assert observation['date']=='2026-06-01'
    assert np.isclose(row.context_vegetation_fraction,1)


def test_road_mapped_connectivity_is_measured_separate_from_traversability():
    roads=gpd.GeoDataFrame(geometry=[LineString([(30,0),(50,0)]),LineString([(50,0),(70,0)]),LineString([(200,0),(250,0)])],crs=32643)
    row=characterize_environment(zone(),{'roads':roads}).iloc[0]
    assert row.road_mapped_component_count==2
    assert row.road_nearest_component_segment_count==2
    assert row.road_access_state=='unknown'
    assert row.road_connectivity_state=='derived_mapped_graph'

