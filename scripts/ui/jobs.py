"""Bounded, inspectable background build jobs. No build activates knowledge."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from datetime import datetime, timezone
from uuid import uuid4
from copy import deepcopy
from pathlib import Path
import json

class JobManager:
    def __init__(self, workers=1, capacity=3, storage_dir=None):
        self.executor=ThreadPoolExecutor(max_workers=workers,thread_name_prefix='knowledge-build')
        self.capacity=capacity; self.jobs={}; self.lock=Lock()
        self.storage_dir=Path(storage_dir) if storage_dir else None
        if self.storage_dir:
            for path in self.storage_dir.glob('*.json'):
                try:
                    job=json.loads(path.read_text(encoding='utf-8'))
                    if job['job_id']!=path.stem:continue
                    if job['status'] in ('queued','running'):
                        job.update(status='failed',error='Server stopped during processing; current knowledge preserved',stage='Interrupted build')
                    self.jobs[job['job_id']]=job
                except (ValueError,KeyError,OSError):continue
    def _persist(self,job):
        if self.storage_dir:
            from scripts.knowledge.repository import _atomic_json
            self.storage_dir.mkdir(parents=True,exist_ok=True)
            _atomic_json(self.storage_dir/(job['job_id']+'.json'),job)
    def submit(self, spec, builder=None):
        with self.lock:
            if sum(j['status'] in ('queued','running') for j in self.jobs.values())>=self.capacity:
                raise ValueError('Build queue is full. Wait for a current job to finish.')
            job={'job_id':uuid4().hex,'dataset_id':spec.dataset_id,'status':'queued','stage':'queued','history':[], 'progress':{'percent':None,'completed_stages':[],'total_stages':8,'indeterminate':True},'created_at':datetime.now(timezone.utc).isoformat()}
            job.update(region_id=getattr(spec,'region_id',None),date=getattr(spec,'date',None))
            self.jobs[job['job_id']]=job
            self._persist(job)
        self.executor.submit(self._run,job,spec,builder)
        return dict(job)
    def _run(self,job,spec,builder):
        try:
            if builder is None:
                from scripts.knowledge.build import build_knowledge
                builder=build_knowledge
            self._event(job,'running','Validating sources and building terrain knowledge')
            import inspect
            kwargs={}
            if 'log' in inspect.signature(builder).parameters: kwargs['log']=lambda message:self._event(job,'running',message)
            elif 'progress' in inspect.signature(builder).parameters: kwargs['progress']=lambda *args:self._event(job,'running',' · '.join(map(str,args)))
            elif 'progress_callback' in inspect.signature(builder).parameters: kwargs['progress_callback']=lambda *args:self._event(job,'running',' · '.join(map(str,args)))
            result=builder(spec,**kwargs)
            from dataclasses import asdict,is_dataclass
            job['result']=result.to_dict() if hasattr(result,'to_dict') else (asdict(result) if is_dataclass(result) else result)
            if isinstance(job['result'],dict) and job['result'].get('package_path'):
                job['review']={'decision':'pending'}
            self._event(job,'completed','Build complete — inspect validation before publication')
        except Exception as exc:
            job['error']=str(exc);self._event(job,'failed','Build failed; published datasets preserved')
    def _event(self,job,status,stage):
        with self.lock:
            import re
            match=re.match(r'^(sources|terrain|dem|characteristics|zones|environment|temporal|package): (complete|reuse verified stage checkpoint)',str(stage))
            progress=job['progress']
            if match and match[1] not in progress['completed_stages']:
                progress['completed_stages'].append(match[1])
                progress.update(percent=round(len(progress['completed_stages'])*100/8),indeterminate=False)
            if status=='completed':progress.update(percent=100,indeterminate=False)
            job.update(status=status,stage=stage);job['history'].append({'time':datetime.now(timezone.utc).isoformat(),'stage':stage})
            self._persist(job)
    def update_review(self,job_id,review):
        with self.lock:
            updated={**self.jobs[job_id],'review':deepcopy(review)}
            self._persist(updated);self.jobs[job_id]=updated
    def list(self,region_id=None,include_unfinished=False):
        with self.lock:
            return deepcopy([j for j in self.jobs.values() if (region_id is None or j.get('region_id')==region_id) and ((isinstance(j.get('result'),dict) and j['result'].get('package_path')) or (include_unfinished and j['status'] in ('queued','running')))])
    def get(self,job_id):
        with self.lock:
            j=self.jobs.get(job_id)
            return deepcopy(j) if j else None
