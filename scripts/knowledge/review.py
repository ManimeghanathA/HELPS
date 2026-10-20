"""Map preview and explicit immutable-package acceptance; scans never activate themselves."""
import datetime
import json
import sqlite3
from pathlib import Path
from threading import RLock
from uuid import uuid4

from .sources import file_sha256
from .repository import KnowledgeRepository,registry_guard,_register_dataset,_activate_dataset,_atomic_json


class BuildReview:
    def __init__(self,managed,jobs):
        self.managed=Path(managed).resolve();self.jobs=jobs;self.registry_path=self.managed/'registry.json'
        self.lock=RLock();self.cache={}

    def registry(self):
        return json.loads(self.registry_path.read_text(encoding='utf-8')) if self.registry_path.exists() else {'datasets':{},'selected':{}}

    def proposal(self,job_id):
        job=self.jobs.get(job_id)
        if not job or job['status']!='completed' or not job.get('result',{}).get('package_path'):raise ValueError('Only completed knowledge builds can be previewed')
        path=Path(job['result']['package_path']).resolve()
        if not path.is_relative_to(self.managed) or not path.is_file():raise ValueError('Proposed package unavailable in managed knowledge')
        digest=file_sha256(path);key=(str(path),digest)
        if key not in self.cache:
            self.cache[key]=KnowledgeRepository(path)
            if len(self.cache)>4:self.cache.pop(next(iter(self.cache)))
        repo=self.cache[key]
        if repo.dataset_id!=job['dataset_id'] or repo.region_id!=job.get('region_id'):raise ValueError('Proposed package identity differs from build job')
        registered=self.registry().get('datasets',{}).get(repo.dataset_id)
        if registered and registered.get('package_sha256')==digest and job.get('review',{}).get('decision')=='pending':
            # Recover a crash between registry publication and decision persistence.
            self.jobs.update_review(job_id,{**job['review'],'decision':'accepted','recovered_from_registry':True})
            job=self.jobs.get(job_id)
        return job,path,digest,repo

    def summary(self,job_id):
        job,path,digest,repo=self.proposal(job_id);registry=self.registry();current_id=registry.get('selected',{}).get(repo.region_id)
        current=registry.get('datasets',{}).get(current_id,{})
        records=repo.list_terrain(include_geometry=False,internal=True)
        area=sum(r['metric_geometry'].area for r in records)
        metadata=repo.get_metadata()
        current_counts=None
        if current.get('package_path'):
            cp=Path(current['package_path'])
            with sqlite3.connect(cp.resolve().as_uri()+'?mode=ro',uri=True) as db:
                current_counts={table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('terrain','zones')}
        return {'job_id':job_id,'decision':job.get('review',{}).get('decision','pending'),
                'proposed':{'dataset_id':repo.dataset_id,'date':metadata['date'],'region_id':repo.region_id,'candidate_count':len(records),'slope_zone_count':metadata['counts']['zones'],'total_area_m2':area,'sha256':digest,'enrichment_of':job['result'].get('enrichment_of'),'refinement_of':job['result'].get('refinement_of')},
                'current':{'dataset_id':current_id,'date':current.get('date'),'counts':current_counts},
                'validation':{'valid':True},'source_completeness':metadata.get('source_completeness',{}),'temporal_summary':metadata.get('temporal_summary',{}),
                'parameters':metadata.get('build_spec',{}).get('parameters',{}),'evidence_note':'Candidate terrain and mapped/DEM evidence; no claim of complete obstacle clearance.'}

    def preview(self,job_id):
        with self.lock:
            job,path,digest,repo=self.proposal(job_id)
            current=self.registry().get('selected',{}).get(repo.region_id)
            review=job.get('review',{'decision':'pending'})
            if review.get('decision','pending')=='pending':
                review={**review,'decision':'pending','preview_token':uuid4().hex,'reviewed_sha256':digest,'expected_current':current}
                self.jobs.update_review(job_id,review)
            collection=repo.to_geojson(repo.list_terrain())
            collection.update(preview_token=review.get('preview_token') if review.get('decision')=='pending' else None,decision=review.get('decision'))
            return collection

    def reject(self,job_id):
        with self.lock:
            job,path,digest,repo=self.proposal(job_id);review=job.get('review',{'decision':'pending'})
            if review.get('decision')=='accepted':raise ValueError('Accepted knowledge cannot be rejected as an unpublished build')
            if repo.dataset_id in self.registry().get('datasets',{}):raise ValueError('Published knowledge cannot be rejected as an unpublished build')
            review={'decision':'rejected','decided_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
            self.jobs.update_review(job_id,review)
            return {'decision':'rejected','current_preserved':True,'dataset_id':repo.dataset_id}

    @staticmethod
    def verify_enrichment(source,target,source_digest):
        if file_sha256(source)!=source_digest:raise ValueError('Source knowledge changed since enrichment')
        with sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True) as old,sqlite3.connect(Path(target).resolve().as_uri()+'?mode=ro',uri=True) as new:
            for table,key in (('terrain','terrain_id'),('zones','zone_id'),('terrain_characteristics','terrain_id'),('zone_environment','zone_id'),('lineage','id')):
                def records(db):
                    columns=[r[1] for r in db.execute('PRAGMA table_info('+table+')')]
                    for row in db.execute('SELECT * FROM '+table+' ORDER BY '+key):
                        value=dict(zip(columns,row));value.pop('dataset_id',None)
                        if 'record_json' in value:
                            record=json.loads(value['record_json']);record.pop('dataset_id',None);value['record_json']=record
                        yield value
                if list(records(old))!=list(records(new)):raise ValueError('Same-date enrichment changed retained geometry or measured features')

    @staticmethod
    def verify_refinement(source,target,result):
        if file_sha256(source)!=result.get('source_package_sha256'):raise ValueError('Source knowledge changed since vision refinement')
        old=KnowledgeRepository(source);new=KnowledgeRepository(target)
        policy=new.get_metadata().get('build_spec',{}).get('parameters',{}).get('cv_refinement',{})
        if (not policy.get('same_observation_revision') or policy.get('base_dataset_id')!=old.dataset_id
                or new.region_id!=old.region_id or new.get_metadata()['date']!=old.get_metadata()['date']
                or policy.get('source_package_sha256')!=result['source_package_sha256']):raise ValueError('Vision refinement provenance does not match current knowledge')
        audit=Path(result.get('refinement_audit_path',''))
        if (not audit.is_file() or file_sha256(audit)!=result.get('refinement_audit_sha256')
                or policy.get('geometry_audit_sha256')!=result.get('refinement_audit_sha256')):raise ValueError('Vision refinement geometry audit changed or is missing')
        checks=json.loads(audit.read_text(encoding='utf-8'))
        if (checks.get('passed') is not True or checks.get('vision_sha256')!=policy.get('vision_sha256')
                or checks.get('inward_contraction_m')!=5 or policy.get('new_inward_contraction_m')!=5
                or checks.get('new_site_max_slope_deg')!=policy.get('new_max_slope_deg')
                or checks.get('all_other_classes_excluded')!=[1,2,5,6,7,8]):raise ValueError('Vision refinement strict policy or audit is invalid')
        vision=Path(policy.get('vision_path',''))
        if not vision.is_file() or file_sha256(vision)!=policy.get('vision_sha256'):raise ValueError('Vision source changed since refinement')

    def accept(self,job_id,token):
        with self.lock:
            job,path,digest,repo=self.proposal(job_id);review=job.get('review',{})
            if review.get('decision')=='rejected':raise ValueError('Rejected builds cannot be accepted; create a new proposal')
            if not token or token!=review.get('preview_token'):raise ValueError('Load the polygon map preview before confirming replacement')
            if digest!=review.get('reviewed_sha256'):raise ValueError('Proposed package changed after preview; inspect it again')
            with registry_guard(self.registry_path):
                registry=self.registry();current_id=registry.get('selected',{}).get(repo.region_id)
                if review.get('decision')=='accepted' and current_id==repo.dataset_id:return {'decision':'accepted','selected':registry['selected']}
                if current_id!=review.get('expected_current'):raise ValueError('Current knowledge changed after preview; load a fresh preview before confirming')
                enrichment=job['result'].get('enrichment_of')
                refinement=job['result'].get('refinement_of')
                if refinement:
                    if refinement!=current_id:raise ValueError('Vision refinement no longer matches current knowledge')
                    self.verify_refinement(registry['datasets'][current_id]['package_path'],path,job['result'])
                if enrichment:
                    current=registry.get('datasets',{}).get(current_id,{})
                    if enrichment!=current_id or current.get('date')!=repo.get_metadata()['date']:raise ValueError('Enrichment no longer matches the current observation')
                    self.verify_enrichment(current['package_path'],path,job['result']['source_package_sha256'])
                existed=self.registry_path.exists();before=registry
                try:
                    _register_dataset(repo.dataset_id,path,self.registry_path,require_forward=not bool(enrichment or refinement))
                    _activate_dataset(repo.dataset_id,self.registry_path,administrative_recovery=bool(enrichment or refinement))
                    self.jobs.update_review(job_id,{**review,'decision':'accepted','decided_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
                except Exception:
                    if existed:_atomic_json(self.registry_path,before)
                    else:self.registry_path.unlink(missing_ok=True)
                    raise
                return {'decision':'accepted','published':repo.dataset_id,'selected':self.registry()['selected']}
