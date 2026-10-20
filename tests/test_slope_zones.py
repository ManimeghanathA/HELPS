import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import box, Polygon
from scripts.knowledge.contracts import TerrainRasterAssets
from scripts.knowledge.slope_zones import generate_slope_zones


def assets_for(tmp_path,slopes):
    paths=[]
    transform=rasterio.transform.from_origin(0,slopes.shape[0]*30,30,30)
    for name,array in [('elevation',slopes*0+100),('slope',slopes),('roughness',slopes*0),('valid',np.isfinite(slopes).astype('float32'))]:
        path=tmp_path/(name+'.tif'); paths.append(path)
        with rasterio.open(path,'w',driver='GTiff',width=slopes.shape[1],height=slopes.shape[0],count=1,dtype='float32',crs=32643,transform=transform,nodata=np.nan) as ds: ds.write(array.astype('float32'),1)
    return TerrainRasterAssets(*paths,'EPSG:32643',30)


def parent(geometry):
    return gpd.GeoDataFrame({'terrain_id':['p'],'source_zone_id':['p'],'dataset_id':['d']},geometry=[geometry],crs=32643)


def test_threshold_split_monotonic_and_corner_components(tmp_path):
    assets=assets_for(tmp_path,np.array([[1,8],[8,1]],dtype='float32'))
    zones,centres,audit=generate_slope_zones(parent(box(0,0,60,60)),assets,{},thresholds=(0,2,8),parameters={'min_area_m2':0,'min_width_m':0,'min_length_m':0,'min_clear_radius_m':0})
    assert len(zones[zones.slope_threshold_deg==2])==2
    assert len(zones[zones.slope_threshold_deg==8])==1
    assert zones[zones.slope_threshold_deg==2].area_m2.sum()==1800
    assert zones[zones.slope_threshold_deg==8].area_m2.sum()==3600
    assert 'no_valid_slope_cells' in audit.reason.tolist()
    assert len(centres)==len(zones)


def test_hole_exclusion_and_actual_geometry_gates(tmp_path):
    assets=assets_for(tmp_path,np.zeros((4,4),dtype='float32'))
    hole=Polygon([(0,0),(120,0),(120,120),(0,120)], [[(45,45),(75,45),(75,75),(45,75)]])
    exclude=gpd.GeoDataFrame(geometry=[box(0,0,10,120)],crs=32643)
    zones,centres,audit=generate_slope_zones(parent(hole),assets,{'buildings':exclude},thresholds=(0,),parameters={'min_area_m2':0,'min_width_m':0,'min_length_m':0,'min_clear_radius_m':0})
    assert len(zones)==1
    zone=zones.iloc[0]
    assert len(zone.geometry.interiors)==1
    assert zone.geometry.intersection(exclude.geometry.iloc[0]).area==0
    center=centres.geometry.iloc[0]
    assert np.isclose(center.distance(zone.geometry.boundary),zone.max_clear_radius_m)
    rejected=generate_slope_zones(parent(hole),assets,{},thresholds=(0,),parameters={'min_area_m2':20000})
    assert rejected[0].empty and 'area_below_minimum' in rejected[2].reason.tolist()


def test_complete_nodata_produces_audited_zero_children(tmp_path):
    assets=assets_for(tmp_path,np.full((2,2),np.nan,dtype='float32'))
    zones,_,audit=generate_slope_zones(parent(box(0,0,60,60)),assets,{},thresholds=(0,2))
    assert zones.empty and len(audit)==2
    assert set(audit.reason)=={'no_valid_slope_cells'}

def test_water_setback_and_diameter_gate_parameters_are_honored(tmp_path):
    assets=assets_for(tmp_path,np.zeros((4,4),dtype='float32'))
    water=gpd.GeoDataFrame(geometry=[box(0,0,10,120)],crs=32643)
    zones,_,_=generate_slope_zones(parent(box(0,0,120,120)),assets,{'water':water},thresholds=(0,),parameters={'water_setback_m':20,'min_clear_diameter_m':0,'min_area_m2':0,'min_width_m':0,'min_length_m':0})
    assert np.isclose(zones.geometry.iloc[0].bounds[0],30)
    rejected=generate_slope_zones(parent(box(0,0,120,120)),assets,{},thresholds=(0,),parameters={'min_clear_diameter_m':200})
    assert rejected[0].empty
