from pathlib import Path
import geopandas as gpd
import numpy as np
import pytest
import rasterio
from shapely.geometry import box
from test_pipeline_reproducibility import new_spec
from scripts.knowledge.sources import file_sha256


@pytest.mark.parametrize('screening_policy', ['conservative', 'calibrated', 'neha-236c34c'])
def test_harmonization_rebuilds_original_masks_without_mutating_sources(tmp_path, screening_policy):
    from scripts.knowledge.history import harmonize_history
    from scripts.knowledge.temporal import validate_history_raster
    spec=new_spec(tmp_path)
    original=tmp_path/'old.tif'
    with rasterio.open(spec.sources['scl'].path) as src:
        profile=src.profile;profile.update(nodata=255)
    with rasterio.open(original,'w',**profile) as dst:dst.write(np.ones((20,20),dtype='uint8'),1)
    row={'source_id':'old','date':'2026-05-01','path':str(original),'status':'available','provenance_state':'original','spectral_path':str(spec.sources['spectral'].path),'scl_path':str(spec.sources['scl'].path),'spectral_sha256':file_sha256(spec.sources['spectral'].path),'scl_sha256':file_sha256(spec.sources['scl'].path),**validate_history_raster(original)}
    before=original.read_bytes()
    rows=harmonize_history([row],tmp_path/'history',screening_policy,log=lambda _:None)
    assert rows[0]['status']=='available'
    assert rows[0]['classification_policy']==screening_policy and rows[0]['cloud_buffer_pixels']==3
    assert rows[0]['path']!=str(original) and original.read_bytes()==before
    assert rows[0]['original_classification_sha256']==row['sha256']
    again=harmonize_history([row],tmp_path/'history',screening_policy,log=lambda _:None)
    assert rows[0]['sha256']==again[0]['sha256']


def test_incomparable_history_is_explicitly_failed_not_silently_used(tmp_path):
    from scripts.knowledge.history import harmonize_history
    rows=harmonize_history([{'source_id':'missing','date':'2026-05-01','path':str(tmp_path/'missing.tif'),'status':'available','sha256':'wrong','provenance_state':'unknown'}],tmp_path/'cache','conservative',log=lambda _:None)
    assert rows[0]['status']=='failed' and rows[0]['error']


def test_missing_requested_date_reduces_temporal_support(tmp_path):
    from scripts.knowledge.temporal import compute_temporal,validate_history_raster
    spec=new_spec(tmp_path);path=tmp_path/'state.tif'
    with rasterio.open(spec.sources['scl'].path) as src:profile=src.profile;profile.update(nodata=255)
    with rasterio.open(path,'w',**profile) as dst:dst.write(np.ones((20,20),dtype='uint8'),1)
    history=[{'source_id':'available','date':'2026-04-01','path':str(path),'status':'available','provenance_state':'test',**validate_history_raster(path)},{'source_id':'failed','date':'2026-05-01','status':'failed'}]
    frame=gpd.GeoDataFrame({'terrain_id':['p']},geometry=[box(500050,1500050,500150,1500150)],crs=32643)
    zones=gpd.GeoDataFrame({'zone_id':[]},geometry=[],crs=32643)
    observations,aggregates=compute_temporal(frame,zones,history,'2026-06-01','d')
    assert len(observations)==1
    assert aggregates[0]['temporal_open_confidence']==1
    assert aggregates[0]['temporal_support']==pytest.approx(.5)
    assert aggregates[0]['history_date_count']==2 and aggregates[0]['available_history_date_count']==1


def test_harmonized_previous_current_satisfies_activation_history_guard(tmp_path):
    from test_knowledge_repository import package_data
    from scripts.knowledge.repository import write_package,_require_current_history
    data=package_data();data['metadata'].update(dataset_id='new',date='2026-10-14')
    for frame in (data['terrain'],data['zones']):frame['dataset_id']='new'
    data['sources']['history']={'source_id':'history','sha256':'normalized-hash','date':'2026-10-13','original_classification_sha256':'original-hash','original_source_id':'original-state'}
    data['temporal_observations']=[{'entity_type':entity,'entity_id':identity,'date':'2026-10-13','source_id':'history','open_area_m2':area,'valid_area_m2':area,'unknown_area_m2':0} for entity,identity,area in [('terrain','p',14400),('zones','z',10000)]]
    path=tmp_path/'new.gpkg';write_package(data,path)
    registry={'selected':{'r':'current'},'datasets':{'current':{'observation_source':{'date':'2026-10-13','sha256':'original-hash','source_id':'original-state'}}}}
    _require_current_history(registry,'r',path,'2026-10-14')


def test_requested_missing_dates_survive_normalized_package_validation(tmp_path):
    from test_knowledge_repository import package_data
    from scripts.knowledge.repository import write_package
    from scripts.knowledge.temporal import aggregate_observations
    data=package_data()
    data['sources']['history']={'source_id':'history','sha256':'hash'}
    row={'entity_type':'terrain','entity_id':'p','date':'2026-09-01','source_id':'history','open_area_m2':14400,'valid_area_m2':14400,'unknown_area_m2':0}
    aggregate=aggregate_observations(14400,[row]);aggregate.update(temporal_support=.5,history_date_count=2,history_dates=['2026-08-01','2026-09-01'],available_history_date_count=1)
    data.update(temporal_observations=[row],temporal_aggregates=[{'entity_type':'terrain','entity_id':'p',**aggregate}])
    assert write_package(data,tmp_path/'knowledge.gpkg')['valid']


def test_unpinned_historical_imagery_cannot_be_claimed_immutable(tmp_path):
    from scripts.knowledge.history import harmonize_history
    from scripts.knowledge.temporal import validate_history_raster
    spec=new_spec(tmp_path);state=tmp_path/'old.tif'
    with rasterio.open(spec.sources['scl'].path) as src:profile=src.profile;profile.update(nodata=255)
    with rasterio.open(state,'w',**profile) as dst:dst.write(np.ones((20,20),dtype='uint8'),1)
    row={'source_id':'old','date':'2026-05-01','path':str(state),'status':'available','provenance_state':'unknown','spectral_path':str(spec.sources['spectral'].path),'scl_path':str(spec.sources['scl'].path),**validate_history_raster(state)}
    actual=harmonize_history([row],tmp_path/'cache',log=lambda _:None)
    assert actual[0]['status']=='failed' and 'hash' in actual[0]['error'].lower()
