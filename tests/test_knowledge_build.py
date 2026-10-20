import json
from pathlib import Path
import pytest
from test_knowledge_sources import fixture_spec
from scripts.knowledge.build import build_knowledge
from scripts.knowledge.repository import KnowledgeRepository


def test_synthetic_end_to_end_build_checkpoint_and_no_auto_activation(tmp_path):
    spec=fixture_spec(tmp_path)
    spec.parameters={'min_area_m2':0,'min_width_m':0,'min_length_m':0,'min_clear_radius_m':0,'slope_thresholds_deg':[0,2,4]}
    messages=[]
    result=build_knowledge(spec,log=messages.append)
    assert result.validation['valid']
    assert result.counts['terrain']==2 and result.counts['zones']==6
    assert KnowledgeRepository(result.package_path).get_zone(KnowledgeRepository(result.package_path).list_zones()[0]['zone_id'])['restriction_state']=='unknown'
    assert not (tmp_path/'registry.json').exists()
    manifest=json.loads(result.manifest_path.read_text())
    assert manifest['status']=='complete' and manifest['stages']['dem']['status']=='complete'
    again=build_knowledge(spec,log=messages.append)
    assert again.package_path==result.package_path
    assert any('reuse' in m.lower() for m in messages)


def test_failed_source_build_keeps_prior_selected_registry(tmp_path):
    spec=fixture_spec(tmp_path); spec.dem.sha256='invalid'
    registry=tmp_path/'registry.json'; registry.write_text('{"selected":{"r":"previous"}}')
    before=registry.read_bytes()
    with pytest.raises(ValueError,match='hash'):
        build_knowledge(spec)
    assert registry.read_bytes()==before
    assert not (spec.output_dir/'knowledge.gpkg').exists()
    manifest=json.loads((spec.output_dir/'build-status.json').read_text())
    assert manifest['status']=='failed'

def test_changed_unhashed_dem_invalidates_resumed_features(tmp_path,monkeypatch):
    import numpy as np
    import rasterio
    import scripts.knowledge.build as module
    spec=fixture_spec(tmp_path)
    spec.parameters={'min_area_m2':0,'min_width_m':0,'min_length_m':0,'min_clear_radius_m':0,'slope_thresholds_deg':[0,2,4]}
    real_writer=module.write_package
    monkeypatch.setattr(module,'write_package',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('publication interrupted')))
    with pytest.raises(RuntimeError,match='publication interrupted'): build_knowledge(spec,log=lambda m:None)
    before=json.loads((spec.output_dir/'characteristics-checkpoint.json').read_text())['records'][0]['mean_slope_deg']
    assert before==0
    with rasterio.open(spec.dem.path,'r+') as ds:
        ds.write(np.tile(np.arange(ds.width,dtype='float32')*30*np.tan(np.deg2rad(4)),(ds.height,1)),1)
    monkeypatch.setattr(module,'write_package',real_writer)
    result=build_knowledge(spec,log=lambda m:None)
    assert result.counts['thresholds']['0.0']==0
    assert KnowledgeRepository(result.package_path).get_terrain('a')['mean_slope_deg']>3.99


def test_corrupt_lineage_checkpoint_is_regenerated(tmp_path,monkeypatch):
    import scripts.knowledge.build as module
    spec=fixture_spec(tmp_path); spec.parameters={'slope_thresholds_deg':[0]}
    real_writer=module.write_package
    monkeypatch.setattr(module,'write_package',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('interrupted')))
    with pytest.raises(RuntimeError): build_knowledge(spec,log=lambda m:None)
    (spec.output_dir/'lineage-checkpoint.json').write_text('{"corrupt":true}')
    monkeypatch.setattr(module,'write_package',real_writer)
    result=build_knowledge(spec,log=lambda m:None)
    assert result.validation['valid']


def test_changed_algorithm_cannot_reuse_immutable_package(tmp_path,monkeypatch):
    import scripts.knowledge.build as module
    spec=fixture_spec(tmp_path)
    spec.parameters={'slope_thresholds_deg':[0]}
    build_knowledge(spec,log=lambda m:None)
    monkeypatch.setattr(module,'algorithm_fingerprint',lambda:'changed-implementation',raising=False)
    with pytest.raises(FileExistsError,match='different spec'):
        build_knowledge(spec,log=lambda m:None)
