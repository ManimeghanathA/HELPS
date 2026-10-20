"""Offline, source-pinned CV refinement; completed knowledge requires map review."""
import argparse
import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import geopandas as gpd
import rasterio
from .contracts import KnowledgeBuildSpec,SourceAsset
from .sources import read_vector,file_sha256
from .repository import KnowledgeRepository,_atomic_json
from .slope_zones import exclusion_frames
from .vision_refinement import VisionStore,prepare_seed
from .build import build_knowledge

VISION_SHA256='575b980a4225eda768fd83fee29fbee2ae073bc8a578b8b256fb50290c14f634'


def run(root,dataset_id,max_slope_deg,log=print):
    root=Path(root).resolve();managed=root/'data/knowledge'
    registry=json.loads((managed/'registry.json').read_text(encoding='utf-8'))
    base_id=registry['selected']['bhadra'];base_path=Path(registry['datasets'][base_id]['package_path'])
    base_hash=file_sha256(base_path);base=KnowledgeRepository(base_path);day=base.get_metadata()['date']
    if day!='2026-06-01':raise ValueError('This approved refinement targets the selected June 1 baseline')
    output=managed/dataset_id;output.mkdir(parents=True,exist_ok=True)
    configuration=json.loads((managed/'bhadra-20261012-f73274d5/manifest.json').read_text(encoding='utf-8'))['spec']
    configuration=copy.deepcopy(configuration)
    template=json.loads((root/'docs/examples/bhadra-retained-build.json').read_text(encoding='utf-8'))
    def asset(value):
        value=copy.deepcopy(value);p=Path(value['path']);value['path']=str(p if p.is_absolute() else root/p)
        return SourceAsset.from_dict(value)
    sources={k:asset(v) for k,v in configuration['sources'].items()}
    for key in ('spectral','scl'):sources[key]=asset(template['sources'][key])
    reviewed=asset(template['reviewed_exclusions'])
    if reviewed.sha256 and file_sha256(reviewed.path)!=reviewed.sha256:raise ValueError('Reviewed exclusion snapshot changed')
    sources['reviewed_site_exclusions']=reviewed
    parameters={**template['parameters'],'screening_profile':'neha-236c34c','harmonize_history':True,
                'facilities_buffer_m':20,'slope_tolerance_deg':0.0}
    static_names={'buildings','osm_buildings','water','industrial','facilities','restrictions','restriction','reviewed_site_exclusions'}
    frames=exclusion_frames({k:v for k,v in sources.items() if k in static_names},'EPSG:32643',parameters)
    # Enriched immutable metadata may retain original checkout raster paths.
    # Recompute from the pinned DEM/AOI using the exact knowledge-build method,
    # rather than guessing a relocated file or changing the original package.
    from .dem import prepare_terrain_rasters
    log('Preparing measured slope from the pinned FABDEM and AOI for strict 12-degree screening')
    prepared=prepare_terrain_rasters(asset(configuration['dem']),read_vector(asset(template['aoi'])),output/'preparation-terrain',30)
    slope_path=prepared.slope_path
    log('Preparing strict source-pinned CV refinement; current knowledge remains selected')
    vision=VisionStore(root/'probably_final.qgz/probably_final.gpkg',VISION_SHA256)
    current=gpd.read_file(base_path,layer='terrain')
    source_stat=vision.path.stat()
    seed_dir=output/'refinement-input'
    with rasterio.open(slope_path) as slope:
        frame,seed_path,audit=prepare_seed(current,vision,slope,frames,seed_dir,max_slope_deg,log)
    vision.db.close()
    if vision.path.stat().st_size!=source_stat.st_size or vision.path.stat().st_mtime_ns!=source_stat.st_mtime_ns:raise ValueError('Vision source changed during refinement')
    from .temporal import discover_history
    historical=[r for r in discover_history(root,'bhadra') if r['date']<day]
    parameters['_history_sources']=historical
    parameters['cv_refinement']={'base_dataset_id':base_id,'source_package_sha256':base_hash,
        'vision_path':str(vision.path),'vision_sha256':VISION_SHA256,'vision_acquisition_date':None,
        'new_inward_contraction_m':5,'new_max_slope_deg':max_slope_deg,'same_observation_revision':True,
        'slope_filter_source_sha256':file_sha256(slope_path),'original_observation_date':day,
        'vision_date_status':'unknown; new sites are vision-derived, not demonstrated June Sentinel openings',
        'geometry_audit_sha256':file_sha256(seed_dir/'refinement-audit.json')}
    sources['vision_context']=SourceAsset('cv-vision-source-context',seed_path,kind='vector',layer='vision_extent',coverage_state='supplied',
        metadata={'original_path':str(vision.path),'original_sha256':VISION_SHA256,'imagery_observation_date':None,'semantic_accuracy':'unverified'})
    spec=KnowledgeBuildSpec(dataset_id,'bhadra',day,asset(template['aoi']),
        SourceAsset(dataset_id+'-seed',seed_path,kind='candidate_seed',layer='candidate_seed',metadata={'derived_from':base_id,'vision_acquisition_date':None}),
        asset(configuration['dem']),output,sources=sources,parameters=parameters,source_mode='retained')
    _atomic_json(output/'refinement-spec.json',spec.to_dict())
    if file_sha256(base_path)!=base_hash:raise ValueError('Selected baseline changed during geometry preparation')
    result=build_knowledge(spec,log).to_dict()
    if file_sha256(output/'rasters/slope.tif')!=file_sha256(slope_path):raise ValueError('Built terrain differs from the slope filter grid')
    result.update(refinement_of=base_id,source_package_sha256=base_hash,refinement_audit_path=str(seed_dir/'refinement-audit.json'),
                  refinement_audit_sha256=file_sha256(seed_dir/'refinement-audit.json'),refinement_summary=audit)
    _atomic_json(output/'refinement-result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--max-slope',type=float,default=12);args=parser.parse_args()
    if not 0<=args.max_slope<=90:raise ValueError('Slope ceiling must be between zero and 90 degrees')
    from scripts.ui.jobs import JobManager
    root=Path(__file__).resolve().parents[2];identity='bhadra-cv-20260601-'+uuid4().hex[:8]
    manager=JobManager(storage_dir=root/'data/knowledge/jobs')
    spec=SimpleNamespace(dataset_id=identity,region_id='bhadra',date='2026-06-01')
    job=manager.submit(spec,lambda spec,log:run(root,spec.dataset_id,args.max_slope,log))
    _atomic_json(root/'data/reviews/2026-10-20-cv/refinement-job.json',job)
    print(json.dumps(job),flush=True)
    while manager.get(job['job_id'])['status'] in ('queued','running'):time.sleep(1)
    final=manager.get(job['job_id']);print(json.dumps(final,indent=2),flush=True)
    manager.executor.shutdown(wait=True)
    if final['status']!='completed':raise RuntimeError(final.get('error','Refinement failed'))


if __name__=='__main__':main()
