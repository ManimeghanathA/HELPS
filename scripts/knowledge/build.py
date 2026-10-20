"""Offline knowledge builder. Building never activates or replaces source data.

Usage: python -m scripts.knowledge.build --spec path/to/spec.json
"""
from pathlib import Path
from dataclasses import replace
import argparse
import datetime
import hashlib
import json
import time
import sys
from importlib.metadata import version
import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping
from .contracts import KnowledgeBuildSpec,KnowledgeBuildResult,SourceAsset,TerrainRasterAssets,THRESHOLDS,json_safe
from .sources import validate_build_spec,read_vector,load_retained_terrain,inspect_source
from .dem import prepare_terrain_rasters
from .characterization import characterize_terrain
from .slope_zones import generate_slope_zones
from .environment import characterize_environment
from .repository import write_package,validate_package,_atomic_json


def runtime_versions():
    return {'python':sys.version.split()[0],**{name:version(name) for name in ('numpy','geopandas','shapely','rasterio','pyproj','pyogrio','scipy')}}


def algorithm_fingerprint():
    """Checkpoint identity includes implementation, not only unchanged inputs."""
    digest=hashlib.sha256()
    digest.update(json.dumps(runtime_versions(),sort_keys=True).encode())
    for directory in (Path(__file__).parent,Path(__file__).parent.parent/'processing',Path(__file__).parent.parent/'pipeline'):
        for path in sorted(directory.glob('*.py')):
            digest.update((directory.name+'/'+path.name).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _save_frame(frame,path):
    if isinstance(frame,gpd.GeoDataFrame):
        records=[]
        for _,row in frame.iterrows(): records.append({'type':'Feature','geometry':mapping(row.geometry),'properties':json_safe(row.drop(labels=['geometry']).to_dict())})
        _atomic_json(path,{'type':'FeatureCollection','features':records,'processing_crs':frame.crs.to_string(),'columns':list(frame.columns)})
    else: _atomic_json(path,{'records':json_safe(frame.to_dict('records')),'columns':list(frame.columns)})


def _load_frame(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if 'features' in data:
        if data['features']: return gpd.GeoDataFrame.from_features(data['features'],crs=data['processing_crs'])
        return gpd.GeoDataFrame({k:[] for k in data['columns']},geometry='geometry',crs=data['processing_crs'])
    return pd.DataFrame(data['records'],columns=data['columns'])


def _generate_new_seed(spec,aoi,output,log):
    from scripts.pipeline.processing import process_inputs
    required={'spectral','scl','water','industrial','facilities'}
    absent=required-set(spec.sources)
    if absent: raise ValueError(f'new candidate generation missing required sources {sorted(absent)}')
    building_frames=[read_vector(asset).to_crs(aoi.crs) for key,asset in spec.sources.items() if key in ('buildings','osm_buildings')]
    if not building_frames: raise ValueError('new candidate generation requires buildings evidence')
    buildings=gpd.GeoDataFrame(pd.concat(building_frames,ignore_index=True),crs=aoi.crs)
    exclusion_keys=('water','industrial') if spec.parameters.get('screening_profile')=='neha-236c34c' else ('water','industrial','facilities')
    exclusions={key:read_vector(spec.sources[key]) for key in exclusion_keys}
    if spec.reviewed_exclusions:
        review=read_vector(spec.reviewed_exclusions)
        if 'status' in review:review=review.loc[review['status'].isin(['quarantined','excluded'])].copy()
        # New zone IDs differ from the retained map. Carry known negatives by
        # location before polygonization/refinement rather than by the old ID.
        exclusions['reviewed']=review
    process_inputs(spec.sources['spectral'].path,spec.sources['scl'].path,buildings,exclusions,aoi,output,spec.region_id,log,screening_profile=spec.parameters.get('screening_profile','conservative'),landcover_path=spec.sources['landcover'].path if 'landcover' in spec.sources else None)
    asset=SourceAsset(spec.dataset_id+'-generated-seed',output/'final_zones.gpkg',kind='candidate_seed',layer='final_open_land_zones',date=spec.date,metadata={'generated_by':'scripts.pipeline.processing.process_inputs','screening_profile':spec.parameters.get('screening_profile','conservative')})
    return load_retained_terrain(replace(spec,retained_seed=asset,source_mode='retained',reviewed_exclusions=None)),asset


def build_knowledge(spec,log=print,progress=None):
    if isinstance(spec,dict): spec=KnowledgeBuildSpec.from_dict(spec)
    output=spec.output_dir; output.mkdir(parents=True,exist_ok=True)
    status_path=output/'build-status.json'; manifest_path=output/'manifest.json'; package_path=output/'knowledge.gpkg'
    status={'dataset_id':spec.dataset_id,'status':'running','started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stages':{},'spec':spec.to_dict()}
    old_fingerprint=None
    if status_path.exists():
        old=json.loads(status_path.read_text(encoding='utf-8'))
        if old.get('spec')==spec.to_dict():
            status['stages']=old.get('stages',{})
            old_fingerprint=old.get('source_fingerprint')
    def record(message):
        with (output/'build.log').open('a',encoding='utf-8') as stream: stream.write(str(message)+'\n')
        log(str(message))
    def stage(name,function,checkpoint=None):
        previous=status['stages'].get(name,{})
        if checkpoint and previous.get('status')=='complete' and Path(checkpoint).exists() and previous.get('checkpoint_sha256')==hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest():
            record(f'{name}: reuse verified stage checkpoint'); return _load_frame(checkpoint)
        status['stages'][name]={'status':'running'}; _atomic_json(status_path,status)
        if progress: progress({'stage':name,'status':'running'})
        record(f'{name}: starting'); started=time.perf_counter()
        result=function()
        status['stages'][name]={'status':'complete','duration_s':time.perf_counter()-started}
        if checkpoint:
            _save_frame(result,checkpoint); status['stages'][name]['checkpoint_sha256']=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()
        _atomic_json(status_path,status); record(f'{name}: complete ({status["stages"][name]["duration_s"]:.2f}s)')
        if progress: progress({'stage':name,'status':'complete','duration_s':status['stages'][name]['duration_s']})
        return result
    try:
        from .chronology import validate_imagery_dates
        validate_imagery_dates(spec)
        validation=stage('sources',lambda:validate_build_spec(spec))
        if not validation['valid']: raise ValueError('source validation failed: '+'; '.join(validation['errors']))
        implementation_hash=algorithm_fingerprint()
        fingerprint=hashlib.sha256(json.dumps({'spec':spec.to_dict(),'sources':validation['sources'],'algorithm_fingerprint':implementation_hash},sort_keys=True).encode()).hexdigest()
        # A changed source invalidates every downstream checkpoint, even if the spec path is unchanged.
        if old_fingerprint and old_fingerprint!=fingerprint: status['stages']={'sources':status['stages']['sources']}
        status['source_fingerprint']=fingerprint; status['algorithm_fingerprint']=implementation_hash; status['runtime_versions']=runtime_versions(); _atomic_json(status_path,status)
        if package_path.exists():
            if not manifest_path.exists(): raise FileExistsError('package exists without complete build manifest')
            manifest=json.loads(manifest_path.read_text(encoding='utf-8')); report=validate_package(package_path)
            if manifest.get('source_fingerprint')!=fingerprint or not report['valid']: raise FileExistsError('immutable dataset exists with different spec or invalid package')
            record('package: reuse verified immutable completed build')
            status.update(status='complete',completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()); _atomic_json(status_path,status)
            return KnowledgeBuildResult(spec.dataset_id,package_path,manifest_path,manifest['counts'],report,validation['completeness'])
        aoi=read_vector(spec.aoi)
        if spec.source_mode=='new':
            terrain,generated=stage('terrain',lambda:_generate_new_seed(spec,aoi,output/'generated-candidates',record))
            validation['sources']['generated_seed']=inspect_source(generated)
        else: terrain=stage('terrain',lambda:load_retained_terrain(spec),output/'terrain-checkpoint.json')
        rasters_dir=output/'rasters'; raster_manifest=rasters_dir/'rasters.json'
        raster_stage=status['stages'].get('dem',{})
        raster_paths={name:rasters_dir/(name+'.tif') for name in ('elevation','slope','roughness','valid')}
        hashes=raster_stage.get('output_sha256',{})
        if raster_stage.get('status')=='complete' and raster_manifest.exists() and hashes and all(path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==hashes.get(name) for name,path in raster_paths.items()):
            record('dem: reuse verified raster checkpoint')
            raster_record=json.loads(raster_manifest.read_text())
            assets=TerrainRasterAssets(*raster_paths.values(),raster_record['crs'],raster_record['resolution_m'],raster_record,raster_manifest)
        else:
            assets=stage('dem',lambda:prepare_terrain_rasters(spec.dem,aoi,rasters_dir,float(spec.parameters.get('resolution_m',30))))
            status['stages']['dem']['output_sha256']={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in raster_paths.items()}; _atomic_json(status_path,status)
        terrain=terrain.to_crs(assets.crs)
        characteristics=stage('characteristics',lambda:characterize_terrain(terrain,assets,spec.sources,spec.parameters),output/'characteristics-checkpoint.json')
        exclusion_names={'buildings','osm_buildings','water','restrictions','restriction','industrial','facilities','obstacles','power','man_made','barriers'}
        exclusions={key:source for key,source in spec.sources.items() if key in exclusion_names}
        zones_checkpoint=output/'zones-checkpoint.json'
        zones_stage=status['stages'].get('zones',{})
        related_paths={name:output/(name+'-checkpoint.json') for name in ('lineage','centres')}
        related_hashes=zones_stage.get('related_sha256',{})
        related_verified=bool(related_hashes) and all(path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==related_hashes.get(name) for name,path in related_paths.items())
        if zones_stage.get('status')=='complete' and related_verified and zones_checkpoint.exists() and zones_stage.get('checkpoint_sha256')==hashlib.sha256(zones_checkpoint.read_bytes()).hexdigest():
            record('zones: reuse verified stage checkpoint'); zones=_load_frame(zones_checkpoint); lineage=_load_frame(output/'lineage-checkpoint.json')
        else:
            status['stages'].pop('zones',None)
            def make_zones():
                zones,centres,lineage=generate_slope_zones(terrain,assets,exclusions,thresholds=spec.parameters.get('slope_thresholds_deg',THRESHOLDS),parameters=spec.parameters)
                _save_frame(centres,output/'centres-checkpoint.json'); _save_frame(lineage,output/'lineage-checkpoint.json')
                return zones
            zones=stage('zones',make_zones,zones_checkpoint); lineage=_load_frame(output/'lineage-checkpoint.json')
            status['stages']['zones']['related_sha256']={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in related_paths.items()}
            _atomic_json(status_path,status)
        environment=stage('environment',lambda:characterize_environment(zones,spec.sources,float(spec.parameters.get('environment_radius_m',200))),output/'environment-checkpoint.json')
        from .temporal import compute_temporal,validate_history_raster
        history=spec.parameters.get('_history_sources',[])
        if spec.parameters.get('harmonize_history',False):
            from .history import harmonize_history
            history=harmonize_history(history,output.parent/'history-cache',spec.parameters.get('screening_profile','conservative'),record)
        for source in history:
            if source.get('status')=='available':
                inspected=validate_history_raster(source['path'],source.get('encoding'))
                if inspected['sha256']!=source['sha256']:raise ValueError('Historical classification changed after discovery')
                validation['sources'][source['source_id']]={**source,'kind':'historical_classification'}
        temporal_observations,temporal_aggregates=stage('temporal',lambda:compute_temporal(terrain,zones,history,spec.date,spec.dataset_id))
        observation_source=None
        state_path=output/'generated-candidates/archive/screened_open.tif'
        if not state_path.exists():state_path=output/'generated-candidates/archive/possible_open.tif'
        if not state_path.exists() and {'spectral','scl'}.issubset(spec.sources):
            from scripts.processing.open_land_detector import generate_possible_open_mask
            import rasterio
            with rasterio.open(spec.sources['spectral'].path) as spectral:
                if spectral.count<6:raise ValueError('Dated classification requires six Sentinel bands: blue, green, red, NIR, SWIR1, SWIR2')
            state_path=output/'rasters/observation-state.tif'
            generate_possible_open_mask(spec.sources['spectral'].path,spec.sources['scl'].path,state_path,cloud_buffer_pixels=3,screening_profile=spec.parameters.get('screening_profile','conservative'))
        if state_path.exists():
            observation_source={'source_id':spec.dataset_id+'-classification','path':str(state_path.resolve()),'region_id':spec.region_id,'date':spec.date,'status':'available','provenance_state':'generated_from_date_validated_sources','license_status':'Derived Copernicus Sentinel-2 classification; original acquisition provenance retained','spectral_path':str(spec.sources['spectral'].path.resolve()),'scl_path':str(spec.sources['scl'].path.resolve()),'classification_policy':spec.parameters.get('screening_profile','conservative'),'cloud_buffer_pixels':3,**validate_history_raster(state_path)}
            observation_source.update(spectral_sha256=validation['sources']['spectral']['sha256'],scl_sha256=validation['sources']['scl']['sha256'])
            validation['sources'][observation_source['source_id']]={**observation_source,'kind':'classification','spectral_source_id':spec.sources['spectral'].source_id,'scl_source_id':spec.sources['scl'].source_id}
        data={'spec':spec,'terrain':terrain,'zones':zones,'characteristics':characteristics,'environment':environment,'lineage':lineage,'sources':validation['sources'],'parameters':spec.parameters,'aoi_record':{'region_id':spec.region_id,'source_id':spec.aoi.source_id,'geometry':mapping(aoi.to_crs(assets.crs).geometry.union_all()),'crs':assets.crs},'run':status,'metadata':{'source_completeness':validation['completeness'],'rasters':{name:str(path.resolve()) for name,path in raster_paths.items()},'raster_manifest':assets.manifest,'source_fingerprint':fingerprint}}
        data.update(temporal_observations=temporal_observations,temporal_aggregates=temporal_aggregates)
        data['metadata']['observation_source']=observation_source
        data['metadata']['temporal_summary']={'history_dates':sorted({r['date'] for r in temporal_observations}),'observation_count':len(temporal_observations),'entities_with_valid_history':sum(r['valid_history_count']>0 for r in temporal_aggregates),'mean_valid_support':sum(r['temporal_support'] for r in temporal_aggregates)/len(temporal_aggregates) if temporal_aggregates else 0,'source_limitations':[{'date':r['date'],'status':r['status'],'provenance_state':r.get('provenance_state'),'error':r.get('error')} for r in history]}
        report=stage('package',lambda:write_package(data,package_path))
        counts={'terrain':len(terrain),'zones':len(zones),'thresholds':{str(float(th)):int((zones.slope_threshold_deg==th).sum()) for th in spec.parameters.get('slope_thresholds_deg',THRESHOLDS)},'rejected_fragments':int((lineage.status=='rejected').sum()) if len(lineage) else 0}
        status.update(status='complete',counts=counts,completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        manifest={**status,'package_path':str(package_path.resolve()),'validation':report,'source_completeness':validation['completeness'],'source_records':validation['sources'],'rasters':data['metadata']['rasters'],'raster_manifest':assets.manifest,'analysis_parameters':spec.parameters,'activation':'not selected; activation is an explicit separate action'}
        _atomic_json(manifest_path,manifest); _atomic_json(status_path,status)
        record(f'Complete immutable dataset {spec.dataset_id}: {len(terrain)} terrain, {len(zones)} zones')
        return KnowledgeBuildResult(spec.dataset_id,package_path,manifest_path,counts,report,validation['completeness'])
    except Exception as exc:
        status.update(status='failed',error=str(exc),failed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()); _atomic_json(status_path,status)
        record(f'Failed: {exc}'); raise


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--spec',required=True)
    args=parser.parse_args(); spec=KnowledgeBuildSpec.from_dict(json.loads(Path(args.spec).read_text(encoding='utf-8')))
    result=build_knowledge(spec); print(json.dumps(result.to_dict(),indent=2))

if __name__=='__main__': main()
