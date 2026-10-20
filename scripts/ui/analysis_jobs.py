"""Bounded asynchronous recommendation work with observed phase progress."""
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
from copy import deepcopy
import json
from flask import Blueprint, request, jsonify

STAGES={'retrieval':'Finding nearby candidate polygons','weather':'Retrieving weather evidence',
        'hard_checks':'Checking measured terrain and aircraft compatibility',
        'ranking':'Scoring and comparing candidate locations','geometry':'Preparing map boundaries',
        'complete':'Analysis complete'}


def register_analysis_api(app,root,repository_loader=None,engine_factory=None):
    root=Path(root).resolve();jobs={};lock=RLock();executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='helps-analysis')
    bp=Blueprint('analysis_jobs',__name__)
    def selected(region):
        p=root/'data/knowledge/registry.json'
        return json.loads(p.read_text(encoding='utf-8')).get('selected',{}).get(region) if p.exists() else None
    def engine(identity):
        if repository_loader is not None:repo=repository_loader(identity)
        else:repo=app.extensions['helps_repository'](identity)
        if engine_factory is not None:return engine_factory(repo)
        from scripts.recommendation.engine import RecommendationEngine
        from scripts.recommendation.weather_policy import WeatherSnapshotCache
        with lock:
            if 'weather_snapshot_cache' not in app.extensions:app.extensions['weather_snapshot_cache']=WeatherSnapshotCache()
            weather=app.extensions['weather_snapshot_cache']
        return RecommendationEngine(repo,weather)
    def run(job,req):
        def progress(row):
            row=deepcopy(row);phase=row.get('phase','retrieval')
            completed=row.get('completed');total=row.get('total')
            row['percent']=round(100*completed/total,1) if isinstance(total,(int,float)) and total>0 and isinstance(completed,(int,float)) else None
            with lock:
                job.update(status='running',stage=STAGES.get(phase,phase),progress=row)
                job['history'].append(row)
        try:
            progress({'phase':'retrieval'})
            result=engine(req.dataset_id).recommend(req,progress=progress)
            if selected(req.region_id)!=req.dataset_id:raise ValueError('Current dataset changed during analysis. Run the analysis again.')
            result=result.to_dict() if hasattr(result,'to_dict') else result
            with lock:job.update(status='completed',stage=STAGES['complete'],result=result)
        except Exception as exc:
            with lock:job.update(status='failed',stage='Analysis could not finish',error=str(exc))
    @bp.post('/api/recommendation-jobs')
    def submit():
        if request.remote_addr not in ('127.0.0.1','::1'):return jsonify(error='Analysis is restricted to this local application'),403
        origin=request.headers.get('Origin')
        if origin and urlparse(origin).netloc!=request.host:return jsonify(error='Use the same application origin'),403
        from scripts.recommendation.inputs import validate_request
        try:
            req=validate_request(request.get_json(silent=True) or {})
            if selected(req.region_id)!=req.dataset_id:raise ValueError('Choose the current dataset for this region')
        except ValueError as exc:return jsonify(error=str(exc)),400
        with lock:
            if sum(j['status'] in ('queued','running') for j in jobs.values())>=2:
                return jsonify(error='Analysis queue is full. Wait for the current analysis to finish.'),429
            # Retain only a bounded recent history in memory.
            for identity in list(jobs):
                if len(jobs)<=24:break
                if jobs[identity]['status'] not in ('queued','running'):jobs.pop(identity)
            job={'job_id':uuid4().hex,'status':'queued','stage':'Waiting for analysis','history':[]}
            jobs[job['job_id']]=job
            initial=deepcopy(job)
        executor.submit(run,job,req)
        return jsonify(initial),202
    @bp.get('/api/recommendation-jobs/<identity>')
    def inspect(identity):
        with lock:result=deepcopy(jobs.get(identity))
        return (jsonify(result),200) if result is not None else (jsonify(error='Analysis not found; start a new analysis'),404)
    app.register_blueprint(bp)
