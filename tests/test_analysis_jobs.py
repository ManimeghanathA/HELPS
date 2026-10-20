import json
import time
from flask import Flask


def setup_app(tmp_path, factory=None):
    from scripts.ui.analysis_jobs import register_analysis_api
    p=tmp_path/'data/knowledge/registry.json';p.parent.mkdir(parents=True)
    p.write_text(json.dumps({'datasets':{'current':{'region_id':'bhadra'}},'selected':{'bhadra':'current'}}))
    app=Flask(__name__)
    register_analysis_api(app,tmp_path,repository_loader=lambda identity:identity,engine_factory=factory)
    return app,p


def request_payload():
    return {'dataset_id':'current','region_id':'bhadra','model_id':'hal_luh','mission':'hybrid_balanced',
            'latitude':13.6,'longitude':75.6,'requested_at':'2026-10-17T10:00:00Z'}


def poll(client, identity):
    for _ in range(150):
        r=client.get('/api/recommendation-jobs/'+identity)
        if r.json['status'] in ('completed','failed'):return r.json
        time.sleep(.01)
    raise AssertionError('Analysis did not finish')


def test_analysis_reports_actual_work_and_exact_result(tmp_path):
    class Engine:
        def recommend(self,request,progress=None):
            progress({'phase':'hard_checks','completed':3,'total':4})
            return {'dataset_id':request.dataset_id,'research_candidates':[{'zone_id':'zone','score':75}]}
    app,_=setup_app(tmp_path,lambda repo:Engine());c=app.test_client()
    r=c.post('/api/recommendation-jobs',json=request_payload())
    assert r.status_code==202
    result=poll(c,r.json['job_id'])
    assert result['status']=='completed'
    assert result['result']['research_candidates']==[{'zone_id':'zone','score':75}]
    assert any(row['phase']=='hard_checks' and row['completed']==3 and row['total']==4 for row in result['history'])


def test_analysis_rejects_old_dataset_and_foreign_origin(tmp_path):
    app,_=setup_app(tmp_path);c=app.test_client();p=request_payload();p['dataset_id']='old'
    r=c.post('/api/recommendation-jobs',json=p)
    assert r.status_code==400 and 'current' in r.json['error'].lower()
    assert c.post('/api/recommendation-jobs',json=request_payload(),headers={'Origin':'https://foreign.example'}).status_code==403


def test_changed_current_dataset_does_not_publish_stale_analysis(tmp_path):
    app,path=setup_app(tmp_path)
    class Engine:
        def recommend(self,request,progress=None):
            state=json.loads(path.read_text());state['selected']['bhadra']='new'
            path.write_text(json.dumps(state))
            return {'research_candidates':[{'zone_id':'old'}]}
    # A fresh app binds the supplied engine while sharing the same registry.
    from scripts.ui.analysis_jobs import register_analysis_api
    other=Flask('other');register_analysis_api(other,tmp_path,repository_loader=lambda identity:identity,engine_factory=lambda repo:Engine())
    c=other.test_client();r=c.post('/api/recommendation-jobs',json=request_payload())
    result=poll(c,r.json['job_id'])
    assert result['status']=='failed' and 'changed' in result['error'].lower()
    assert 'result' not in result
