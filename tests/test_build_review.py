import json
from time import sleep
from types import SimpleNamespace
from pathlib import Path
import pytest
from flask import Flask
from scripts.knowledge.repository import write_package,register_dataset,activate_dataset
from test_knowledge_repository import package_data

HEADERS={'X-HELPS-Role':'engineer'}


def test_same_date_vision_revision_requires_pinned_base_source_and_audit(tmp_path):
    from scripts.knowledge.review import BuildReview
    from scripts.knowledge.sources import file_sha256
    data=package_data();source=tmp_path/'current.gpkg';write_package(data,source)
    vision=tmp_path/'vision.gpkg';vision.write_bytes(b'pinned external vision source')
    audit=tmp_path/'refinement-audit.json';audit.write_text(json.dumps({'passed':True,'vision_sha256':file_sha256(vision),'inward_contraction_m':5,'new_site_max_slope_deg':12,'all_other_classes_excluded':[1,2,5,6,7,8]}))
    policy={'base_dataset_id':'d','source_package_sha256':file_sha256(source),'vision_path':str(vision),'vision_sha256':file_sha256(vision),'same_observation_revision':True,'new_inward_contraction_m':5,'new_max_slope_deg':12,'geometry_audit_sha256':file_sha256(audit)}
    proposal=package_data();proposal['metadata'].update(dataset_id='revision',build_spec={'parameters':{'cv_refinement':policy}})
    for frame in (proposal['terrain'],proposal['zones']):frame['dataset_id']='revision'
    target=tmp_path/'revision.gpkg';write_package(proposal,target)
    result={'source_package_sha256':file_sha256(source),'refinement_audit_path':str(audit),'refinement_audit_sha256':file_sha256(audit)}
    BuildReview.verify_refinement(source,target,result)
    vision.write_bytes(b'changed external vision source')
    with pytest.raises(ValueError,match='Vision source'):BuildReview.verify_refinement(source,target,result)


def test_same_date_vision_revision_activates_only_after_review(tmp_path):
    from scripts.ui.api import register_api
    from scripts.knowledge.sources import file_sha256
    managed=tmp_path/'data/knowledge';managed.mkdir(parents=True);registry=managed/'registry.json'
    original=package_data();original['metadata']['dataset_id']='current'
    for frame in (original['terrain'],original['zones']):frame['dataset_id']='current'
    source=managed/'current/knowledge.gpkg';source.parent.mkdir();write_package(original,source)
    register_dataset('current',source,registry);activate_dataset('current',registry)
    vision=managed/'vision.gpkg';vision.write_bytes(b'fixture vision')
    audit=managed/'audit.json';audit.write_text(json.dumps({'passed':True,'vision_sha256':file_sha256(vision),'inward_contraction_m':5,'new_site_max_slope_deg':12,'all_other_classes_excluded':[1,2,5,6,7,8]}))
    policy={'base_dataset_id':'current','source_package_sha256':file_sha256(source),'vision_path':str(vision),'vision_sha256':file_sha256(vision),'same_observation_revision':True,'new_inward_contraction_m':5,'new_max_slope_deg':12,'geometry_audit_sha256':file_sha256(audit)}
    data=package_data();data['metadata'].update(dataset_id='revision',build_spec={'parameters':{'cv_refinement':policy}})
    for frame in (data['terrain'],data['zones']):frame['dataset_id']='revision'
    target=managed/'revision/knowledge.gpkg';target.parent.mkdir();write_package(data,target)
    app=Flask(__name__);register_api(app,tmp_path);manager=app.extensions['knowledge_jobs'];client=app.test_client()
    result={'package_path':str(target),'refinement_of':'current','source_package_sha256':file_sha256(source),'refinement_audit_path':str(audit),'refinement_audit_sha256':file_sha256(audit)}
    job=manager.submit(SimpleNamespace(dataset_id='revision',region_id='r',date='2026-10-13'),lambda spec:result)
    for _ in range(100):
        if manager.get(job['job_id'])['status']=='completed':break
        sleep(.01)
    assert json.loads(registry.read_text())['selected']['r']=='current'
    url='/api/knowledge/jobs/'+job['job_id'];preview=client.get(url+'/preview?format=geojson',headers=HEADERS)
    response=client.post(url+'/accept',json={'preview_token':preview.json['preview_token']},headers=HEADERS)
    assert response.status_code==200,response.json
    assert json.loads(registry.read_text())['selected']['r']=='revision'


def setup_review(tmp_path):
    from scripts.ui.api import register_api
    managed=tmp_path/'data/knowledge';managed.mkdir(parents=True)
    registry=managed/'registry.json'
    for identity,day in [('current','2026-10-13'),('proposal','2026-10-14')]:
        data=package_data();data['metadata'].update(dataset_id=identity,date=day)
        for frame in (data['terrain'],data['zones']):frame['dataset_id']=identity
        path=managed/identity/'knowledge.gpkg';path.parent.mkdir();write_package(data,path)
        if identity=='current':register_dataset(identity,path,registry);activate_dataset(identity,registry)
    app=Flask(__name__);register_api(app,tmp_path);manager=app.extensions['knowledge_jobs']
    spec=SimpleNamespace(dataset_id='proposal',region_id='r',date='2026-10-14')
    job=manager.submit(spec,lambda spec:{'package_path':str(managed/'proposal/knowledge.gpkg'),'validation':{'valid':True},'counts':{'terrain':1,'zones':1}})
    for _ in range(200):
        if manager.get(job['job_id'])['status']=='completed':break
        sleep(.01)
    assert manager.get(job['job_id'])['status']=='completed'
    return app.test_client(),manager,job['job_id'],registry


def test_completed_build_does_not_publish_without_map_review(tmp_path):
    client,manager,jid,registry=setup_review(tmp_path);before=registry.read_bytes()
    response=client.post('/api/knowledge/jobs/'+jid+'/publish',headers=HEADERS,json={})
    assert response.status_code==400 and 'preview' in response.json['error'].lower()
    assert registry.read_bytes()==before


def test_preview_is_unpublished_and_accept_requires_matching_preview(tmp_path):
    client,manager,jid,registry=setup_review(tmp_path)
    url='/api/knowledge/jobs/'+jid
    summary=client.get(url+'/preview',headers=HEADERS)
    assert summary.status_code==200,summary.json
    assert summary.json['proposed']['candidate_count']==1
    assert summary.json['current']['dataset_id']=='current'
    assert client.get('/api/datasets/proposal/terrain').status_code==404
    geometry=client.get(url+'/preview?format=geojson',headers=HEADERS)
    assert geometry.status_code==200 and len(geometry.json['features'])==1
    token=geometry.json['preview_token']
    rejected=client.post(url+'/accept',headers=HEADERS,json={'preview_token':'wrong'})
    assert rejected.status_code==400
    accepted=client.post(url+'/accept',headers=HEADERS,json={'preview_token':token})
    assert accepted.status_code==200,accepted.json
    assert json.loads(registry.read_text())['selected']['r']=='proposal'
    assert manager.get(jid)['review']['decision']=='accepted'


def test_reject_is_durable_preserves_current_and_cannot_later_accept(tmp_path):
    client,manager,jid,registry=setup_review(tmp_path);before=registry.read_bytes()
    response=client.post('/api/knowledge/jobs/'+jid+'/reject',headers=HEADERS,json={})
    assert response.status_code==200,response.json
    assert registry.read_bytes()==before
    assert client.post('/api/knowledge/jobs/'+jid+'/accept',headers=HEADERS,json={}).status_code==400
    assert Path(manager.get(jid)['result']['package_path']).is_file()
    from scripts.ui.jobs import JobManager
    recovered=JobManager(storage_dir=tmp_path/'data/knowledge/jobs')
    assert recovered.get(jid)['review']['decision']=='rejected'


def test_changed_current_invalidates_earlier_preview(tmp_path):
    client,manager,jid,registry=setup_review(tmp_path)
    token=client.get('/api/knowledge/jobs/'+jid+'/preview?format=geojson',headers=HEADERS).json['preview_token']
    state=json.loads(registry.read_text());state['selected']['r']='another-version';registry.write_text(json.dumps(state));before=registry.read_bytes()
    response=client.post('/api/knowledge/jobs/'+jid+'/accept',headers=HEADERS,json={'preview_token':token})
    assert response.status_code==400 and 'current' in response.json['error'].lower()
    assert registry.read_bytes()==before


def test_preview_rejects_foreign_role_and_modified_proposal(tmp_path):
    client,manager,jid,registry=setup_review(tmp_path)
    assert client.get('/api/knowledge/jobs/'+jid+'/preview').status_code==403
    token=client.get('/api/knowledge/jobs/'+jid+'/preview?format=geojson',headers=HEADERS).json['preview_token']
    p=Path(manager.get(jid)['result']['package_path'])
    with p.open('ab') as f:f.write(b'changed')
    response=client.post('/api/knowledge/jobs/'+jid+'/accept',headers=HEADERS,json={'preview_token':token})
    assert response.status_code==400 and 'changed' in response.json['error'].lower()
    assert json.loads(registry.read_text())['selected']['r']=='current'


def test_acceptance_decision_write_failure_rolls_back_selection(tmp_path,monkeypatch):
    client,manager,jid,registry=setup_review(tmp_path);before=registry.read_bytes()
    token=client.get('/api/knowledge/jobs/'+jid+'/preview?format=geojson',headers=HEADERS).json['preview_token']
    original=manager.update_review
    def fail_accept(identity,review):
        if review.get('decision')=='accepted':raise OSError('disk full')
        return original(identity,review)
    monkeypatch.setattr(manager,'update_review',fail_accept)
    response=client.post('/api/knowledge/jobs/'+jid+'/accept',headers=HEADERS,json={'preview_token':token})
    assert response.status_code==500
    assert registry.read_bytes()==before
    assert manager.get(jid)['review']['decision']=='pending'


def test_same_date_enrichment_requires_exact_preservation_and_explicit_review(tmp_path):
    from scripts.knowledge.enrichment import enrich_package
    from scripts.knowledge.sources import file_sha256
    from test_temporal_enrichment import fixture_package
    source_dir=tmp_path/'fixture';source_dir.mkdir();source,history=fixture_package(source_dir)
    managed=tmp_path/'data/knowledge';managed.mkdir(parents=True);registry=managed/'registry.json'
    register_dataset('d',source,registry);activate_dataset('d',registry)
    # source must be managed for API lookup
    import shutil
    original=managed/'d/knowledge.gpkg';original.parent.mkdir();shutil.copyfile(source,original)
    state=json.loads(registry.read_text());state['datasets']['d']['package_path']=str(original);registry.write_text(json.dumps(state))
    result=enrich_package(original,managed/'enriched','enriched',[history],log=lambda _:None)
    from scripts.ui.api import register_api
    app=Flask(__name__);register_api(app,tmp_path);manager=app.extensions['knowledge_jobs']
    jid=manager.submit(SimpleNamespace(dataset_id='enriched',region_id='r',date='2026-10-13'),lambda spec:result)['job_id']
    for _ in range(200):
        if manager.get(jid)['status']=='completed':break
        sleep(.01)
    client=app.test_client();token=client.get('/api/knowledge/jobs/'+jid+'/preview?format=geojson',headers=HEADERS).json['preview_token']
    assert json.loads(registry.read_text())['selected']['r']=='d'
    response=client.post('/api/knowledge/jobs/'+jid+'/accept',headers=HEADERS,json={'preview_token':token})
    assert response.status_code==200,response.json
    assert json.loads(registry.read_text())['selected']['r']=='enriched'
    assert file_sha256(original)==result['source_package_sha256']
