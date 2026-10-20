import json
from scripts.pipeline.run_selection import latest_completed_run


def test_failed_partial_and_running_outputs_cannot_replace_completed_run(tmp_path):
    for name, status, passed in [('001','complete',True), ('002','failed',True),
                                 ('003','running',True), ('004','complete',False)]:
        folder = tmp_path/name
        folder.mkdir()
        (folder/'run.json').write_text(json.dumps({'status':status,'summary':{'audits':{'passed':passed}}}))
        (folder/'final_zones.gpkg').touch()
        (folder/'final_zones.geojson').touch()
    assert latest_completed_run(tmp_path)[0].name == '001'


def test_complete_metadata_without_artifacts_is_not_active(tmp_path):
    folder = tmp_path/'001'; folder.mkdir()
    (folder/'run.json').write_text(json.dumps({'status':'complete','summary':{'audits':{'passed':True}}}))
    assert latest_completed_run(tmp_path) is None


def test_new_cli_output_awaiting_review_is_not_auto_selected(tmp_path):
    folder=tmp_path/'001';folder.mkdir()
    (folder/'run.json').write_text(json.dumps({'status':'complete','review_required':True,'review_decision':'pending','summary':{'audits':{'passed':True}}}))
    (folder/'final_zones.gpkg').touch();(folder/'final_zones.geojson').touch()
    assert latest_completed_run(tmp_path) is None


def test_api_metadata_describes_the_loaded_engine(monkeypatch):
    from types import SimpleNamespace
    import app as web
    metadata = {'status':'complete','run_id':'loaded-001','screening_profile':'conservative'}
    monkeypatch.setattr(web,'landing_engine',SimpleNamespace(active_run_info=metadata))
    assert web.app.test_client().get('/api/pipeline-run-info').get_json() == metadata


def test_incomplete_source_experiment_is_never_selected_as_complete(tmp_path):
    folder=tmp_path/'001';folder.mkdir()
    (folder/'run.json').write_text(json.dumps({'status':'complete','summary':{'sources_complete':False,'audits':{'passed':True}}}))
    (folder/'final_zones.gpkg').touch();(folder/'final_zones.geojson').touch()
    assert latest_completed_run(tmp_path) is None


def test_explicit_experiment_cannot_be_selected_even_with_complete_sources(tmp_path):
    folder=tmp_path/'001';folder.mkdir()
    (folder/'run.json').write_text(json.dumps({'status':'complete','summary':{'sources_complete':True,'experimental':True,'audits':{'passed':True}}}))
    (folder/'final_zones.gpkg').touch();(folder/'final_zones.geojson').touch()
    assert latest_completed_run(tmp_path) is None


def test_incomplete_source_result_cannot_be_promoted(tmp_path,monkeypatch):
    from scripts.pipeline.run_aoi_pipeline import promote_to_canonical
    from scripts.pipeline import run_aoi_pipeline
    monkeypatch.setattr(run_aoi_pipeline,'ROOT',tmp_path/'isolated-root')
    import pytest
    (tmp_path/'final_zones.gpkg').touch()
    (tmp_path/'summary.json').write_text(json.dumps({'sources_complete':False,'audits':{'passed':True}}))
    with pytest.raises(ValueError,match='complete'):
        promote_to_canonical(tmp_path,'Bhadra','2026-06-01')
