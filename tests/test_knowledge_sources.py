from pathlib import Path
import geopandas as gpd
import pytest
from shapely.geometry import Polygon, box
from scripts.knowledge.contracts import SourceAsset, KnowledgeBuildSpec
from scripts.knowledge.sources import validate_build_spec, load_retained_terrain


def test_nested_extract_tags_reach_road_characterization(tmp_path):
    import json
    from shapely.geometry import LineString
    from scripts.knowledge.sources import read_vector
    path=tmp_path/'roads.gpkg'
    tags={'highway':'service','access':'private','motor_vehicle':'no','surface':'gravel','bridge':'yes'}
    gpd.GeoDataFrame({'attributes':[json.dumps({'element':'way','id':'12','tags':tags})]},
        geometry=[LineString([(0,0),(10,0)])],crs=32643).to_file(path,layer='roads')
    frame=read_vector(SourceAsset('extract-roads',path,layer='roads'))
    assert {key:frame.iloc[0].get(key) for key in tags}==tags


def test_closed_facility_tags_preserve_area_semantics_for_all_features(tmp_path):
    import json
    from shapely.geometry import LineString
    from scripts.knowledge.sources import read_vector
    ring=LineString([(0,0),(100,0),(100,100),(0,100),(0,0)])
    path=tmp_path/'context.gpkg'
    tags=[{'power':'substation'},{'man_made':'storage_tank'},
          {'power':'substation','area':'no'},{'power':'line','man_made':'pipeline'}]
    gpd.GeoDataFrame({'attributes':[json.dumps({'tags':tag}) for tag in tags]},geometry=[ring]*4,crs=32643).to_file(path)
    frame=read_vector(SourceAsset('context',path))
    assert frame.geom_type.tolist()==['Polygon','Polygon','LineString','LineString']
    assert frame.geometry.iloc[0].area==10000


def fixture_spec(tmp_path):
    hole=Polygon([(0,0),(100,0),(100,100),(0,100)], [[(20,20),(30,20),(30,30),(20,30)]])
    seed=tmp_path/'seed.gpkg'
    gpd.GeoDataFrame({'zone_id':['a','b']},geometry=[hole,box(200,0,300,100)],crs=32643).to_file(seed,layer='seed')
    aoi=tmp_path/'aoi.geojson'
    gpd.GeoDataFrame(geometry=[box(-100,-100,400,200)],crs=32643).to_file(aoi)
    import rasterio
    import numpy as np
    dem=tmp_path/'dem.tif'
    with rasterio.open(dem,'w',driver='GTiff',width=20,height=20,count=1,dtype='float32',crs=32643,transform=rasterio.transform.from_origin(-100,300,30,30),nodata=-9999) as ds:
        ds.write(np.ones((20,20),dtype='float32'),1)
    return KnowledgeBuildSpec('test','test','2026-10-13',SourceAsset('aoi',aoi),SourceAsset('seed',seed,layer='seed'),SourceAsset('dem',dem,kind='raster',units='m'),tmp_path/'output')


def test_import_preserves_hole_and_exact_geometry(tmp_path):
    spec=fixture_spec(tmp_path)
    original=gpd.read_file(spec.retained_seed.path)
    actual=load_retained_terrain(spec)
    assert actual.terrain_id.tolist()==['a','b']
    assert actual.source_zone_id.tolist()==['a','b']
    assert actual.geometry.iloc[0].equals_exact(original.geometry.iloc[0],0)
    assert len(actual.geometry.iloc[0].interiors)==1
    assert validate_build_spec(spec)['valid']
    assert validate_build_spec(spec)['completeness']['restrictions']=='unknown'


def test_reviewed_quarantine_by_id(tmp_path):
    spec=fixture_spec(tmp_path)
    path=tmp_path/'review.geojson'
    gpd.GeoDataFrame({'source_zone_id':['b'],'status':['quarantined']},geometry=[box(0,0,1,1)],crs=32643).to_file(path)
    spec.reviewed_exclusions=SourceAsset('review',path)
    assert load_retained_terrain(spec).terrain_id.tolist()==['a']


def test_invalid_units_and_hash_rejected(tmp_path):
    spec=fixture_spec(tmp_path)
    spec.dem.units='unknown'
    spec.retained_seed.sha256='wrong'
    report=validate_build_spec(spec)
    assert not report['valid']
    assert any('units' in e for e in report['errors'])
    assert any('hash' in e for e in report['errors'])


def test_duplicate_source_ids_rejected(tmp_path):
    spec=fixture_spec(tmp_path)
    frame=gpd.read_file(spec.retained_seed.path); frame.zone_id=['same','same']
    frame.to_file(spec.retained_seed.path,layer='seed')
    with pytest.raises(ValueError,match='unique'):
        load_retained_terrain(spec)

def test_spectral_grid_mismatch_and_declared_bands_rejected(tmp_path):
    import rasterio
    import numpy as np
    spec=fixture_spec(tmp_path)
    spectral=tmp_path/'spectral.tif'; scl=tmp_path/'scl.tif'
    for path,width,count in [(spectral,4,4),(scl,3,1)]:
        with rasterio.open(path,'w',driver='GTiff',width=width,height=4,count=count,dtype='float32',crs=32643,transform=rasterio.transform.from_origin(0,120,30,30)) as ds: ds.write(np.ones((count,4,width),dtype='float32'))
    spec.sources={'spectral':SourceAsset('spectral',spectral,kind='spectral'),'scl':SourceAsset('scl',scl,kind='scl')}
    report=validate_build_spec(spec)
    assert not report['valid'] and any('grids' in e for e in report['errors'])
    assert any('band' in e for e in report['errors'])


def test_new_mode_requires_generation_inputs_instead_of_marker(tmp_path):
    spec=fixture_spec(tmp_path); spec.source_mode='new'; spec.parameters={'candidate_seed_generated':True}
    assert not validate_build_spec(spec)['valid']
