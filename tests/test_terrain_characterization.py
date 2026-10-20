import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import box
from scripts.knowledge.characterization import characterize_terrain
from scripts.knowledge.dem import prepare_terrain_rasters
from scripts.knowledge.contracts import SourceAsset


def make_assets(tmp_path):
    path=tmp_path/'source.tif'
    with rasterio.open(path,'w',driver='GTiff',width=7,height=7,count=1,dtype='float32',crs=32643,transform=rasterio.transform.from_origin(0,210,30,30),nodata=-9999) as ds:
        ds.write(np.tile(np.arange(7,dtype='float32')*3,(7,1)),1)
    aoi=gpd.GeoDataFrame(geometry=[box(0,0,210,210)],crs=32643)
    return prepare_terrain_rasters(SourceAsset('dem',path,units='m'),aoi,tmp_path/'rasters')


def test_tiny_polygon_without_cell_center_has_area_weighted_support(tmp_path):
    assets=make_assets(tmp_path)
    frame=gpd.GeoDataFrame({'terrain_id':['tiny'],'source_zone_id':['tiny'],'dataset_id':['test']},geometry=[box(61,121,65,125)],crs=32643)
    original=frame.geometry.iloc[0].wkb
    features=characterize_terrain(frame,assets,{}, {})
    row=features.iloc[0]
    assert row.dem_valid_fraction==1
    assert row.dem_sample_count==1
    assert np.isclose(row.mean_slope_deg,np.degrees(np.arctan(.1)),atol=1e-4)
    assert row.surface_state=='unknown'
    assert frame.geometry.iloc[0].wkb==original


def test_partial_support_and_dated_surface_classes(tmp_path):
    assets=make_assets(tmp_path)
    frame=gpd.GeoDataFrame({'terrain_id':['mixed'],'source_zone_id':['mixed'],'dataset_id':['test']},geometry=[box(0,90,60,120)],crs=32643)
    path=tmp_path/'scl.tif'
    with rasterio.open(path,'w',driver='GTiff',width=2,height=1,count=1,dtype='uint8',crs=32643,transform=rasterio.transform.from_origin(0,120,30,30),nodata=0) as ds:
        ds.write(np.array([[4,0]],dtype='uint8'),1)
    row=characterize_terrain(frame,assets,{'scl':SourceAsset('scl',path,kind='scl',date='2026-06-01')},{}).iloc[0]
    assert row.dem_valid_fraction==.5
    assert row.surface_observations['scl']['date']=='2026-06-01'
    assert row.surface_observations['scl']['class_fractions']['4']==.5
    assert row.surface_observations['scl']['unknown_fraction']==.5
    assert row.ground_firmness_state=='unknown'

def test_parent_without_children_retains_mapped_access_and_water_context(tmp_path):
    from shapely.geometry import LineString
    assets=make_assets(tmp_path)
    frame=gpd.GeoDataFrame({'terrain_id':['p'],'source_zone_id':['p'],'dataset_id':['test']},geometry=[box(60,90,90,120)],crs=32643)
    roads=tmp_path/'roads.geojson'; water=tmp_path/'water.geojson'
    gpd.GeoDataFrame({'access':['private'],'highway':['track']},geometry=[LineString([(120,0),(120,210)])],crs=32643).to_file(roads)
    gpd.GeoDataFrame(geometry=[box(0,90,30,120)],crs=32643).to_file(water)
    row=characterize_terrain(frame,assets,{'roads':SourceAsset('roads',roads),'water':SourceAsset('water',water)},{}).iloc[0]
    assert row.road_distance_m==30
    assert row.water_distance_m==30
    assert row.road_access_state=='mapped_tag'
    assert row.road_access=='private'
    assert row.water_coverage_state=='unknown'


def test_unsigned_reflectance_preserves_negative_ndvi(tmp_path):
    assets=make_assets(tmp_path)
    frame=gpd.GeoDataFrame({'terrain_id':['p'],'source_zone_id':['p'],'dataset_id':['test']},geometry=[box(60,90,90,120)],crs=32643)
    spectral=tmp_path/'spectral.tif'
    bands=np.full((4,7,7),1000,dtype='uint16')
    bands[2]=2000
    with rasterio.open(spectral,'w',driver='GTiff',width=7,height=7,count=4,dtype='uint16',crs=32643,transform=rasterio.transform.from_origin(0,210,30,30)) as ds:
        ds.write(bands)
    row=characterize_terrain(frame,assets,{'spectral':SourceAsset('spectral',spectral,kind='spectral',metadata={'band_map':{'red':3,'nir':4}})},{}).iloc[0]
    assert np.isclose(row.ndvi_mean,-1/3)


def test_multiple_parents_keep_context_coverage_separate_from_raster_coverage(tmp_path):
    from shapely.geometry import LineString
    assets=make_assets(tmp_path)
    frame=gpd.GeoDataFrame({'terrain_id':['a','b'],'source_zone_id':['a','b'],'dataset_id':['test','test']},geometry=[box(60,90,90,120),box(90,90,120,120)],crs=32643)
    roads=tmp_path/'roads.geojson'
    gpd.GeoDataFrame(geometry=[LineString([(150,0),(150,210)])],crs=32643).to_file(roads)
    scl=tmp_path/'scl.tif'
    with rasterio.open(scl,'w',driver='GTiff',width=7,height=7,count=1,dtype='uint8',crs=32643,transform=rasterio.transform.from_origin(0,210,30,30)) as ds:
        ds.write(np.full((7,7),5,dtype='uint8'),1)
    features=characterize_terrain(frame,assets,{'scl':SourceAsset('scl',scl,kind='scl'),'roads':SourceAsset('roads',roads)}, {})
    assert features.road_distance_m.tolist()==[60,30]
    assert features.road_coverage_state.tolist()==['unknown','unknown']
    assert features.vegetation_fraction.tolist()==[0,0]


def test_cloud_scl_preserves_classes_but_withholds_ground_and_ndvi(tmp_path):
    assets=make_assets(tmp_path)
    frame=gpd.GeoDataFrame({'terrain_id':['a'],'source_zone_id':['a'],'dataset_id':['test']},geometry=[box(60,90,90,120)],crs=32643)
    paths={}
    for name,array in [('scl',np.full((1,7,7),9,dtype='uint16')),('spectral',np.full((4,7,7),1000,dtype='uint16'))]:
        path=tmp_path/(name+'.tif');paths[name]=SourceAsset(name,path,kind=name)
        with rasterio.open(path,'w',driver='GTiff',width=7,height=7,count=len(array),dtype='uint16',crs=32643,transform=rasterio.transform.from_origin(0,210,30,30)) as ds:ds.write(array)
    row=characterize_terrain(frame,assets,paths,{}).iloc[0]
    assert row.surface_observations['scl']['class_fractions']['9']==1
    assert row.surface_observations['scl']['observable_fraction']==0
    assert row.vegetation_fraction is None and row.ndvi_mean is None


def test_acquired_json_road_tags_remain_available_for_parent_context(tmp_path):
    from shapely.geometry import LineString
    assets=make_assets(tmp_path)
    frame=gpd.GeoDataFrame({'terrain_id':['p'],'source_zone_id':['p'],'dataset_id':['test']},geometry=[box(60,90,90,120)],crs=32643)
    roads=tmp_path/'roads.geojson'
    gpd.GeoDataFrame({'attributes':['{"highway":"track","access":"private"}']},geometry=[LineString([(120,0),(120,210)])],crs=32643).to_file(roads)
    row=characterize_terrain(frame,assets,{'roads':SourceAsset('roads',roads)},{}).iloc[0]
    assert row.road_tags['highway']=='track' and row.road_access=='private'
