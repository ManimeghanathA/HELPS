"""Version-bound read APIs and loopback-only engineering mutations."""
import json, os, re, shutil
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse
from threading import RLock
from flask import Blueprint, jsonify, request, send_file
from .jobs import JobManager

KINDS={'aoi','dem','spectral','scl','osm','buildings','landcover','restriction','candidate_seed','reviewed_exclusions','water','industrial','facilities','roads'}

def register_api(app, root):
    bp=Blueprint('knowledge_ui',__name__); repository_cache={};terrain_cache={};repository_lock=RLock();root=Path(root).resolve(); managed=root/'data/knowledge'; assets=managed/'sources'; jobs=JobManager(storage_dir=managed/'jobs')
    from scripts.knowledge.review import BuildReview
    reviews=BuildReview(managed,jobs)
    def registry():
        path=managed/'registry.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'datasets':{},'selected':{}}
    def save_registry(r):
        managed.mkdir(parents=True,exist_ok=True);p=managed/'registry.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(r,indent=2,default=str),encoding='utf-8');os.replace(tmp,p)
    def guard():
        if request.headers.get('X-HELPS-Role')!='engineer':return jsonify(error='Data Engineer role required'),403
        if request.remote_addr not in ('127.0.0.1','::1'):return jsonify(error='Engineering is restricted to loopback'),403
        origin=request.headers.get('Origin')
        if origin and urlparse(origin).netloc!=request.host:return jsonify(error='Same local origin required'),403
    def package(dataset_id):
        record=registry()['datasets'].get(dataset_id)
        if not record:raise LookupError('Published dataset not found')
        p=Path(record['package_path']);p=p if p.is_absolute() else root/p;p=p.resolve()
        if not p.is_relative_to(managed.resolve()) or not p.is_file():raise LookupError('Published package is unavailable')
        return p
    def repo(dataset_id):
        p=package(dataset_id)
        from scripts.knowledge.repository import KnowledgeRepository
        key=(str(p),p.stat().st_mtime_ns)
        with repository_lock:
            if key not in repository_cache: repository_cache[key]=KnowledgeRepository(p)
        return repository_cache[key]
    app.extensions['helps_repository']=repo
    @bp.errorhandler(KeyError)
    def missing_field(e):return jsonify(error=f'Missing required field: {e.args[0]}'),400
    @bp.errorhandler(ValueError)
    def invalid(e):return jsonify(error=str(e)),400
    @bp.errorhandler(LookupError)
    def missing(e):return jsonify(error=str(e)),404
    @bp.get('/api/profiles')
    def profiles():
        from helicopter_profiles import get_ui_profiles, MISSION_CONTEXTS
        return jsonify(aircraft={p['id']:p for p in get_ui_profiles()}, missions=MISSION_CONTEXTS)
    @bp.get('/api/datasets/<dataset_id>/slope')
    def slope(dataset_id):
        p=package(dataset_id).parent/'rasters/slope.tif'
        if not p.is_file():
            reference=repo(dataset_id).get_metadata().get('rasters',{}).get('slope')
            if reference:
                text=str(reference).replace('\\','/')
                candidate=Path(reference)
                if '/data/knowledge/' in text:candidate=root/('data/knowledge/'+text.split('/data/knowledge/',1)[1])
                if candidate.resolve().is_relative_to(managed.resolve()):p=candidate
        if not p.is_file():raise LookupError('Measured slope raster unavailable')
        if request.args.get('download')=='true':return send_file(p,as_attachment=True)
        from .slope_layers import cached_slope_bands,band_properties,BREAKS,BAND_COUNT
        if request.args.get('format')=='geojson':
            source=package(dataset_id)
            response=jsonify(cached_slope_bands(str(source),source.stat().st_mtime_ns,p.stat().st_mtime_ns,str(p)))
            # Exact boundary vectors are sizeable. Lossless transport compression
            # changes neither geometry nor measured interval classification.
            if 'gzip' in request.accept_encodings:
                import gzip
                response.set_data(gzip.compress(response.get_data()))
                response.headers['Content-Encoding']='gzip'
                response.headers['Vary']='Accept-Encoding'
            return response
        import rasterio
        from rasterio.warp import transform_bounds,reproject,Resampling
        from rasterio.transform import from_bounds
        import numpy as np
        with rasterio.open(p) as ds:
            bounds=transform_bounds(ds.crs,'EPSG:4326',*ds.bounds)
            width=768;height=max(1,min(1024,round(width*(bounds[3]-bounds[1])/(bounds[2]-bounds[0]))))
            output=np.full((height,width),np.nan,dtype='float32')
            reproject(rasterio.band(ds,1),output,src_transform=ds.transform,src_crs=ds.crs,dst_transform=from_bounds(*bounds,width,height),dst_crs='EPSG:4326',dst_nodata=np.nan,resampling=Resampling.nearest)
        if request.args.get('image')=='true':
            raise ValueError('The cumulative overview image is retired; use the exclusive measured bands endpoint')
        return jsonify(bands_url=f'/api/datasets/{dataset_id}/slope?format=geojson',bounds=[[bounds[1],bounds[0]],[bounds[3],bounds[2]]],unit='degrees',legend=list(BREAKS),band_legend=[band_properties(i) for i in range(BAND_COUNT)],unknown='distinct gray',exclusive=True)
    @bp.get('/api/datasets')
    def datasets():
        r=registry();return jsonify(datasets=[dict(v,dataset_id=k,active=r.get('selected',{}).get(v['region_id'])==k) for k,v in r['datasets'].items()],selected=r.get('selected',{}))
    @bp.get('/api/datasets/<dataset_id>/terrain')
    def terrain(dataset_id):
        r=repo(dataset_id)
        if request.args.get('format')=='geojson':return jsonify(r.to_geojson(r.list_terrain()))
        cache_key=(dataset_id,package(dataset_id).stat().st_mtime_ns)
        if cache_key not in terrain_cache:terrain_cache[cache_key]=r.list_terrain(include_geometry=False)
        records=terrain_cache[cache_key];q=request.args.get('filter','').lower();records=[x for x in records if q in str(x).lower()]
        sort=request.args.get('sort','terrain_id')
        if sort not in ('terrain_id','area_m2','mean_slope_deg','dem_valid_fraction'):raise ValueError('Unsupported sort field')
        records.sort(key=lambda x:(x.get(sort) is None,str(x.get(sort)) if not isinstance(x.get(sort),(int,float)) else x.get(sort)))
        limit=max(1,min(100,int(request.args.get('limit',25))));offset=max(0,int(request.args.get('offset',0)));return jsonify(dataset_id=dataset_id,total=len(records),records=records[offset:offset+limit])
    @bp.get('/api/datasets/<dataset_id>/terrain/<terrain_id>')
    def detail(dataset_id,terrain_id):
        r=repo(dataset_id);record=r.get_terrain(terrain_id)
        if not record:raise LookupError('Unknown terrain identity')
        return jsonify(dataset_id=dataset_id,terrain=record,zones=r.list_zones(terrain_id=terrain_id),temporal_observations=r.temporal_observations('terrain',terrain_id))
    @bp.get('/api/datasets/<dataset_id>/zones')
    def zones(dataset_id):
        r=repo(dataset_id);threshold=float(request.args.get('threshold',6))
        if threshold not in (0,2,4,6,8,10,12,15):raise ValueError('Unsupported slope threshold')
        return jsonify(r.to_geojson(r.list_zones(slope_threshold_deg=threshold)))
    @bp.get('/api/datasets/<dataset_id>/download')
    def download(dataset_id):return send_file(package(dataset_id),as_attachment=True,download_name=f'{dataset_id}.gpkg')
    @bp.post('/api/recommendations')
    def recommend():
        from scripts.recommendation.inputs import validate_request
        from scripts.recommendation.engine import RecommendationEngine
        from scripts.recommendation.weather_policy import WeatherSnapshotCache
        req=validate_request(request.get_json(silent=True) or {});r=repo(req.dataset_id)
        if r.region_id!=req.region_id:raise ValueError('Dataset does not belong to selected region')
        if 'weather_snapshot_cache' not in app.extensions: app.extensions['weather_snapshot_cache']=WeatherSnapshotCache()
        return jsonify(RecommendationEngine(r,app.extensions['weather_snapshot_cache']).recommend(req).to_dict())
    def source_catalog(region_id='bhadra'):
        from .unified_api import region_catalog
        return region_catalog(root,region_id)
    history_cache={}
    def history_sources(region_id,before_date=None):
        from scripts.knowledge.temporal import discover_history,discover_managed_history
        relative=Path('data/processed/Bhadra/sentinel2/history_dates.json')
        original=root if (root/relative).is_file() else root.parent
        folder=original/'data/processed/Bhadra/sentinel2'
        tracked=list(folder.glob('history_dates.json'))+list(folder.glob('*/bhadra_*_mask*.tif'))+list(folder.glob('*/run.json'))+list(folder.glob('*/bhadra_scl.tif'))+list(folder.glob('*/bhadra_spectral.tif'))
        signature=tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in sorted(tracked))
        key=(region_id,signature)
        if key not in history_cache:
            history_cache.clear();history_cache[key]=discover_history(original,region_id)
        rows=[r for r in history_cache[key] if not before_date or r['date']<before_date]
        rows.extend(discover_managed_history(root,registry(),region_id,before_date))
        # Canonical validated published classification wins over an earlier import
        # for the same date. A failed source cannot erase available dated evidence.
        canonical={}
        for row in rows:
            if row['date'] not in canonical or row['status']=='available':canonical[row['date']]=row
        return [canonical[day] for day in sorted(canonical)]
    def named_sources(region_id='bhadra'):
        out=source_catalog(region_id)
        # Reuse reviewed context layers by their readable names, never client paths.
        for name in ('industrial','facilities'):
            if name not in out and out.get('osm_buildings'):
                out[name]={**out['osm_buildings'],'source_id':'catalog-osm-'+name,'layer':name}
        return out
    def safe_source_list(region_id='bhadra'):
        rows=[]
        for name,source in named_sources(region_id).items():
            available=(root/source['path']).is_file()
            if available and source.get('layer'):
                import pyogrio
                available=source['layer'] in {entry[0] for entry in pyogrio.list_layers(root/source['path'])}
            rows.append({'name':name,'slot':name,'catalog_id':name,'label':name.replace('_',' ').title(),'kind':source.get('kind'),'date':source.get('date'),'status':'available' if available else 'missing','available':available,'coverage_state':source.get('coverage_state','unknown'),'acquisition_available':name in ('spectral','scl','water','industrial','facilities','roads','buildings','osm_buildings','power','man_made','barriers')})
        for p in sorted(assets.glob('*.asset.json')):
            source=json.loads(p.read_text(encoding='utf-8'))
            if source.get('metadata',{}).get('region_id') not in (None,region_id):continue
            available=Path(source['path']).is_file()
            rows.append({'name':source['source_id'],'slot':'retained_seed' if source['kind']=='candidate_seed' else source['kind'],'catalog_id':source['source_id'],'label':source.get('metadata',{}).get('display_name',source.get('kind','Uploaded source')),'kind':source['kind'],'date':source.get('date'),'status':'available' if available else 'missing','available':available,'managed_upload':True,'coverage_state':source.get('coverage_state','unknown')})
        return rows
    @bp.get('/api/knowledge/workflow')
    def workflow():
        from datetime import timedelta
        from scripts.knowledge.chronology import current_entry,observation_date
        region_id=request.args.get('region_id','bhadra')
        if not re.fullmatch('[a-zA-Z0-9_-]{1,80}',region_id):raise ValueError('Invalid region identity')
        r=registry();identity,current=current_entry(r,region_id);day=current.get('date')
        from .inventory_qa import scl_inventory_quality
        aoi=source_catalog(region_id).get('aoi')
        def quality(scan_day):
            if not scan_day:return {'qa_state':'unknown'}
            # Original Bhadra observations retain their actual same-day SCL.
            candidates=[]
            if region_id=='bhadra':
                candidates.extend(base/'data/processed/Bhadra/sentinel2'/scan_day/'bhadra_scl.tif' for base in (root,root.parent))
            for entry in r.get('datasets',{}).values():
                if entry.get('region_id')!=region_id or entry.get('date')!=scan_day:continue
                package_path=Path(entry.get('package_path',''));package_path=package_path if package_path.is_absolute() else root/package_path
                manifest=package_path.parent/'manifest.json'
                if manifest.is_file():
                    records=json.loads(manifest.read_text(encoding='utf-8')).get('source_records',{})
                    # Enrichments store dated history as a list, whereas scan
                    # manifests key their input assets by slot. Earlier history
                    # must never be measured as the current day's cloud quality.
                    if isinstance(records,dict):records=[records.get('scl',{})]
                    elif isinstance(records,list):records=[item for item in records if isinstance(item,dict) and item.get('kind')=='scl' and item.get('date')==scan_day]
                    else:records=[]
                    for record in records:
                        if isinstance(record,dict) and record.get('path') and record.get('date') in (None,scan_day):candidates.append(root/record['path'])
            for path in candidates:
                if path.is_file():return scl_inventory_quality(root,aoi,path)
            return {'qa_state':'unknown'}
        history=[{**{k:v for k,v in row.items() if k in ('date','source_id','status','provenance_state','error','license_status','qa_state','cloud_fraction','cloud_shadow_fraction')},'qa_state':row.get('qa_state','unknown'),'cloud_fraction':row.get('cloud_fraction')} for row in history_sources(region_id)]
        versions=[{'dataset_id':key,'date':value.get('date'),'active':key==identity,'kind':'knowledge_version','qa_state':value.get('qa_state','unknown'),'cloud_fraction':value.get('cloud_fraction')} for key,value in r.get('datasets',{}).items() if value['region_id']==region_id]
        for row in history+versions:row.update(quality(row.get('date')))
        current_quality=quality(day)
        return jsonify(region_id=region_id,current_dataset_id=identity,current_date=day,minimum_new_date=(observation_date(day)+timedelta(days=1)).isoformat() if day else None,history=history,versions=versions,sources=safe_source_list(region_id),current_cloud_fraction=current_quality.get('cloud_fraction'),current_cloud_shadow_fraction=current_quality.get('cloud_shadow_fraction'),current_coverage_fraction=current_quality.get('coverage_fraction'),current_qa_state=current_quality['qa_state'])
    searches=JobManager(workers=1,capacity=2)
    search_cache={}
    @bp.post('/api/knowledge/imagery-search')
    def imagery_search():
        denied=guard()
        if denied:return denied
        from scripts.pipeline.monthly import month_buckets,catalog_search
        from scripts.knowledge.contracts import SourceAsset
        from scripts.knowledge.sources import read_vector
        from types import SimpleNamespace
        d=request.get_json(silent=True) or {}
        if not isinstance(d,dict):raise ValueError('Expected JSON object')
        region_id=d['region_id'];end_date=d['end_date'];month_buckets(end_date)
        from scripts.knowledge.chronology import current_entry,observation_date
        from datetime import timedelta
        current_day=current_entry(registry(),region_id)[1].get('date')
        start_date=d.get('start_date') if d.get('history_search') is True else ((observation_date(current_day)+timedelta(days=1)).isoformat() if current_day else None)
        month_buckets(end_date,start_date)
        source=named_sources(region_id).get('aoi')
        if not source:raise ValueError('Reviewed region boundary unavailable')
        inspect_quality=d.get('inspect_quality') is True
        key=(region_id,start_date,end_date,inspect_quality)
        previous=search_cache.get(key)
        if previous and searches.get(previous)['status']!='failed':return jsonify(search_id=previous,status=searches.get(previous)['status']),202
        aoi_source={**source,'path':str((root/source['path']).resolve())}
        def search_builder(spec,log):
            result=catalog_search(read_vector(SourceAsset.from_dict(aoi_source)),end_date,root,log=log,start_date=start_date,measure_shortlist=inspect_quality)
            return result
        job=searches.submit(SimpleNamespace(dataset_id='imagery-'+region_id,region_id=region_id),builder=search_builder)
        search_cache[key]=job['job_id']
        return jsonify(search_id=job['job_id'],status=job['status']),202
    @bp.get('/api/knowledge/imagery-search/<search_id>')
    def imagery_search_status(search_id):
        job=searches.get(search_id)
        if not job:raise LookupError('Unknown imagery search')
        result=job.get('result',{})
        return jsonify(search_id=search_id,status=result.get('status',job['status']),stage=job['stage'],months=result.get('months',[]),observations=result.get('observations',[]),errors=result.get('errors',([{'error':job['error']}] if job.get('error') else [])),qa_state=result.get('qa_state','unmeasured'))
    @bp.post('/api/knowledge/history-import')
    def history_import():
        denied=guard()
        if denied:return denied
        from scripts.knowledge.chronology import observation_date
        from datetime import date
        from types import SimpleNamespace
        d=request.get_json(silent=True) or {}
        if not isinstance(d,dict):raise ValueError('Expected JSON object')
        day=d['date'];region_id=d['region_id']
        if observation_date(day)>date.today():raise ValueError('Historical observation cannot be in the future')
        named_sources(region_id)
        if any(r['date']==day and r['status']=='available' for r in history_sources(region_id)):raise ValueError('Validated historical evidence already available for this date')
        search=searches.get(d['search_id'])
        if not search or search.get('region_id')!=region_id or search.get('status')!='completed' or not any(r['date']==day for r in search.get('result',{}).get('observations',[])):raise ValueError('Select an actual observation from a completed imagery search for this region')
        def importer(spec,log):
            from dotenv import load_dotenv
            from scripts.knowledge.contracts import SourceAsset
            from scripts.knowledge.sources import read_vector,file_sha256
            from scripts.knowledge.temporal import validate_history_raster,register_observation
            from scripts.pipeline.acquisition import sentinel
            from scripts.processing.open_land_detector import generate_possible_open_mask
            from .unified_api import load_credentials
            load_credentials(root)
            source=named_sources(region_id)['aoi'];aoi=read_vector(SourceAsset.from_dict({**source,'path':(root/source['path']).resolve()}))
            folder=managed/'historical-observations'/spec.dataset_id;folder.mkdir(parents=True,exist_ok=False)
            log('Acquiring historical spectral and SCL observation; current knowledge is preserved')
            sentinel(aoi,day,folder,log)
            log('Classifying actual historical observation for dated temporal overlap')
            state=folder/'classification.tif';generate_possible_open_mask(folder/'spectral.tif',folder/'scl.tif',state,cloud_buffer_pixels=3,screening_profile='conservative')
            record={'source_id':spec.dataset_id,'region_id':region_id,'date':day,'path':str(state.resolve()),'status':'available','provenance_state':'same_day_provider_acquisition','license_status':'Derived Copernicus Sentinel-2 classification','product_ids':sorted({pid for r in search['result']['observations'] if r['date']==day for pid in r['product_ids']}),'spectral_sha256':file_sha256(folder/'spectral.tif'),'scl_sha256':file_sha256(folder/'scl.tif'),**validate_history_raster(state)}
            register_observation(root,record)
            return {'historical_observation':{k:v for k,v in record.items() if k not in ('path','sha256','spectral_sha256','scl_sha256','transform')},'current_preserved':True}
        return jsonify(jobs.submit(SimpleNamespace(dataset_id='history-'+region_id+'-'+day+'-'+uuid4().hex[:8],region_id=region_id,date=day),builder=importer)),202
    def register_named_source(name,region_id='bhadra'):
        if re.fullmatch('[a-f0-9]{32}',str(name)):return asset(name)['source_id']
        source=named_sources(region_id).get(name)
        if not source:raise ValueError('Choose a named reviewed catalog source or managed upload')
        from scripts.knowledge.contracts import SourceAsset
        from scripts.knowledge.sources import inspect_source
        path=(root/source['path']).resolve()
        # Server-reviewed paths may point at original sources; clients cannot supply them.
        validation=inspect_source(SourceAsset.from_dict({**source,'path':path}))
        identity=uuid4().hex;assets.mkdir(parents=True,exist_ok=True)
        # Catalog files remain read-only in place; the managed record pins their hash.
        record={**source,'source_id':identity,'path':str(path),'sha256':validation['sha256'],'metadata':{**source.get('metadata',{}),'catalog_id':name,'region_id':region_id,'validation':validation}}
        (assets/(identity+'.asset.json')).write_text(json.dumps(record),encoding='utf-8')
        return identity
    @bp.post('/api/knowledge/build')
    def named_build():
        denied=guard()
        if denied:return denied
        from scripts.knowledge.chronology import validate_registry_date
        d=request.get_json(silent=True) or {}
        if not isinstance(d,dict):raise ValueError('Expected JSON object')
        date_only=d.get('source_mode')=='date_only'
        region_id=d.get('region_id','bhadra') if date_only else d['region_id']
        if date_only and (region_id!='bhadra' or d.get('refresh_obstacles') or d.get('source_choices')):
            raise ValueError('Date-only scans use Bhadra and the saved local baseline; supply only the new date')
        day=d['date'];validate_registry_date(registry(),region_id,day)
        source_catalog(region_id)
        choices=d.get('source_choices',{})
        if not isinstance(choices,dict):raise ValueError('source_choices must map source names to reviewed catalog choices')
        choices=dict(choices)
        if d.get('refresh_obstacles') is True and any(key in ('buildings','osm_buildings','water','industrial','facilities','roads','power','man_made','barriers') and re.fullmatch('[a-f0-9]{32}',str(value)) for key,value in choices.items()):
            raise ValueError('To refresh mapped obstacles, remove explicit obstacle overrides or keep refresh off to use your selected evidence')
        if 'candidate_seed' in choices:choices['retained_seed']=choices.pop('candidate_seed')
        mode='acquire' if date_only else d.get('source_mode','acquire')
        if mode not in ('acquire','import','retained'):raise ValueError('Choose acquire, import or labelled retained reanalysis')
        catalog=named_sources(region_id);selected={}
        for key in ('aoi','dem','reviewed_exclusions','retained_seed'):
            if key=='dem' and choices.get(key)=='automatic':continue
            name=choices.get(key,key if key in catalog else None)
            if name and (key!='retained_seed' or mode=='retained'):selected[key]=register_named_source(name,region_id)
        source_choices={key:choices.get(key,key) for key in catalog if key not in ('aoi','dem','reviewed_exclusions','retained_seed')}
        source_choices.update({key:value for key,value in choices.items() if key not in ('aoi','dem','reviewed_exclusions','retained_seed')})
        if choices.get('restrictions'):source_choices.pop('restriction',None)
        sources={}
        for key,name in source_choices.items():
            # Acquiring a new date must never inject the baseline spectral/SCL pair.
            if mode=='acquire' and key in ('spectral','scl'):continue
            if mode=='acquire' and key in ('water','industrial','facilities','roads','buildings','osm_buildings','power','man_made','barriers','landcover') and not re.fullmatch('[a-f0-9]{32}',str(name)):continue
            sources[key]=register_named_source(name,region_id)
        payload={'dataset_id':region_id+'-'+day.replace('-','')+'-'+uuid4().hex[:8],'region_id':region_id,'date':day,'aoi':selected.get('aoi'),'dem':selected.get('dem'),'candidate_seed':selected.get('retained_seed'),'reviewed_exclusions':selected.get('reviewed_exclusions'),'source_mode':'acquire' if mode=='acquire' else 'import','candidate_strategy':'retained' if mode=='retained' else 'new','sources':sources,'parameters':{'resolution_m':30,'min_area_m2':900,'min_width_m':30,'min_length_m':30,'min_clear_diameter_m':30,'environment_radius_m':200,'screening_profile':'neha-236c34c','refresh_obstacles':d.get('refresh_obstacles') is True}}
        if date_only:payload['parameters']['static_inputs_only']=True
        return submit(payload)
    @bp.get('/api/knowledge/source-catalog')
    def catalog():
        return jsonify(sources=[{'catalog_id':k,**{a:b for a,b in v.items() if a!='path'},'available':(root/v['path']).is_file()} for k,v in source_catalog().items()])
    @bp.post('/api/knowledge/sources/register')
    def register_source():
        denied=guard()
        if denied:return denied
        d=request.get_json(silent=True) or {}
        if not isinstance(d,dict):raise ValueError('Expected JSON object')
        catalog_id=d.get('catalog_id');source=source_catalog().get(catalog_id)
        if not source:raise ValueError('Select a server-defined catalog source')
        p=(root/source['path']).resolve()
        if not p.is_file():raise ValueError('Catalog evidence file unavailable')
        import hashlib
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        if source.get('sha256') and digest!=source['sha256']:raise ValueError('Source hash differs from reviewed catalog')
        assets.mkdir(parents=True,exist_ok=True);asset_id=uuid4().hex;target=assets/(asset_id+p.suffix);shutil.copyfile(p,target)
        record={**source,'source_id':asset_id,'path':str(target),'sha256':digest}
        from scripts.knowledge.contracts import SourceAsset
        from scripts.knowledge.sources import inspect_source
        try:validation=inspect_source(SourceAsset.from_dict(record))
        except Exception as exc:raise ValueError('Catalog source validation failed: '+str(exc)) from None
        record['metadata']={**record.get('metadata',{}),'catalog_id':catalog_id,'validation':validation}
        (assets/(asset_id+'.asset.json')).write_text(json.dumps(record),encoding='utf-8')
        return jsonify(asset_id=asset_id,source=record['kind'],validation=validation,coverage_state=record.get('coverage_state','unknown')),201
    @bp.post('/api/knowledge/sources')
    def upload():
        denied=guard()
        if denied:return denied
        kind=request.form.get('kind');file=request.files.get('file')
        from datetime import date
        try:date.fromisoformat(request.form.get('date',''))
        except ValueError:raise ValueError('Source reference date must use YYYY-MM-DD')
        if kind not in KINDS or not file:raise ValueError('Source kind and evidence file required')
        ext=Path(file.filename or '').suffix.lower()
        if ext not in ('.tif','.tiff','.gpkg','.geojson','.json','.zip'):raise ValueError('Unsupported evidence file extension')
        if kind in ('dem','spectral','scl','landcover') and ext not in ('.tif','.tiff'):raise ValueError('Raster evidence requires GeoTIFF')
        if kind in ('aoi','candidate_seed','osm','buildings','restriction','reviewed_exclusions','water','industrial','facilities','roads') and ext not in ('.gpkg','.geojson','.json'):raise ValueError('Vector evidence requires GeoPackage or GeoJSON')
        if kind=='dem' and request.form.get('units','').lower() not in ('m','metre','meter','metres','meters'):raise ValueError('DEM units must be declared metres')
        assets.mkdir(parents=True,exist_ok=True);asset_id=uuid4().hex;p=assets/(asset_id+ext);file.save(p)
        try:
            if ext in ('.tif','.tiff'):
                import rasterio
                with rasterio.open(p) as ds:
                    if not ds.crs:raise ValueError('Raster CRS missing')
                    report={'crs':str(ds.crs),'bands':ds.count,'resolution':ds.res,'nodata':ds.nodata,'bounds':list(ds.bounds)}
            elif ext!='.zip':
                import geopandas as gpd
                frame=gpd.read_file(p,layer=request.form.get('layer') or None)
                if frame.crs is None or frame.empty:raise ValueError('Vector requires CRS and nonempty geometry')
                report={'crs':str(frame.crs),'features':len(frame),'bounds':frame.total_bounds.tolist()}
            else:raise ValueError('Upload extracted evidence files instead of archives')
        except Exception as exc:
            p.unlink(missing_ok=True)
            if isinstance(exc,ValueError):raise
            from rasterio.errors import RasterioError
            from pyogrio.errors import DataSourceError, DataLayerError
            if isinstance(exc,(RasterioError,DataSourceError,DataLayerError,OSError)):raise ValueError(f'Cannot read {kind} evidence: invalid or unreadable {ext} file') from exc
            raise
        band_map={}
        if kind=='spectral':
            for band in ('blue','green','red','nir'):
                try:index=int(request.form.get('band_'+band,''))
                except ValueError:p.unlink(missing_ok=True);raise ValueError(f'Declare spectral {band} band number')
                if index<1 or index>report['bands']:p.unlink(missing_ok=True);raise ValueError(f'Spectral {band} band number outside available raster bands')
                band_map[band]=index
        import hashlib
        record={'source_id':asset_id,'path':str(p),'kind':kind,'date':request.form.get('date'),'units':request.form.get('units'),'layer':request.form.get('layer') or None,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'coverage_state':'unknown','metadata':{'display_name':Path(file.filename or kind).name,'validation':report,**({'band_map':band_map} if band_map else {})}}
        region_id=request.form.get('region_id')
        if region_id:
            from scripts.pipeline.source_store import safe_id
            safe_id(region_id);source_catalog(region_id)
            folder_kind={'spectral':'sentinel','scl':'sentinel','buildings':'overture','aoi':'boundary'}.get(kind,kind)
            # Each manual source has its own immutable upload identity. It is not
            # advertised as a complete automatic Sentinel pair or OSM bundle.
            relative=Path(region_id)/folder_kind
            if kind in ('spectral','scl'):relative=relative/request.form['date']
            raw=root/'data/raw'/relative/('upload-'+asset_id)
            processed=root/'data/processed'/relative/('upload-'+asset_id)
            raw.mkdir(parents=True,exist_ok=False);processed.mkdir(parents=True,exist_ok=False)
            original=raw/('original'+ext);ready=processed/('evidence'+ext)
            shutil.copyfile(p,original);shutil.copyfile(p,ready)
            record['path']=str(ready)
            record['metadata'].update(region_id=region_id,raw_path=str(original),raw_sha256=record['sha256'],regional_upload=True,
                preparation='Format/CRS validated; bytes preserved. Build performs region/date/semantic checks.')
            from scripts.knowledge.repository import _atomic_json
            _atomic_json(raw/'upload.json',{'asset_id':asset_id,'sha256':record['sha256'],'origin':'user supplied source'})
            _atomic_json(processed/'upload.json',record)
            p.unlink()
        (assets/(asset_id+'.asset.json')).write_text(json.dumps(record),encoding='utf-8')
        return jsonify(asset_id=asset_id,validation=report,coverage_state='unknown'),201
    def asset(asset_id):
        if not re.fullmatch('[a-f0-9]{32}',str(asset_id)):raise ValueError('Use registered asset IDs')
        p=assets/(asset_id+'.asset.json')
        if not p.is_file():raise ValueError('Unknown registered asset ID')
        d=json.loads(p.read_text());path=Path(d['path']).resolve()
        if not path.is_relative_to(assets.resolve()):
            metadata=d.get('metadata',{})
            if metadata.get('regional_upload'):
                from scripts.pipeline.source_store import safe_id
                from scripts.knowledge.sources import file_sha256
                region_id=safe_id(metadata.get('region_id'));raw=Path(metadata.get('raw_path','')).resolve()
                if not path.is_relative_to(root/'data/processed'/region_id) or not raw.is_relative_to(root/'data/raw'/region_id):raise ValueError('Upload outside region storage')
                if not raw.is_file() or file_sha256(raw)!=metadata.get('raw_sha256') or not path.is_file() or file_sha256(path)!=d['sha256']:raise ValueError('Uploaded source evidence changed')
            else:
                catalog_id=metadata.get('catalog_id');reviewed=named_sources(metadata.get('region_id','bhadra')).get(catalog_id)
                if not reviewed or (root/reviewed['path']).resolve()!=path:raise ValueError('Asset outside managed sources')
        return d
    @bp.post('/api/knowledge/jobs')
    def submit(payload=None):
        denied=guard()
        if denied:return denied
        d=payload if payload is not None else (request.get_json(silent=True) or {})
        if not isinstance(d,dict):raise ValueError('Expected JSON object')
        identity=d.get('dataset_id','')
        if not re.fullmatch('[a-zA-Z0-9_-]{1,80}',identity):raise ValueError('Invalid dataset identity')
        if identity in registry()['datasets'] or (managed/identity).exists():raise ValueError('Dataset identity already exists; choose a new version')
        from datetime import date
        try:date.fromisoformat(d['date'])
        except ValueError:raise ValueError('Observation date must use YYYY-MM-DD')
        if not re.fullmatch('[a-zA-Z0-9_-]{1,80}',d['region_id']):raise ValueError('Invalid region identity')
        from scripts.knowledge.chronology import validate_registry_date,validate_imagery_dates
        validate_registry_date(registry(),d['region_id'],d['date'])
        if not isinstance(d.get('sources',{}),dict) or not isinstance(d.get('parameters',{}),dict):raise ValueError('sources and parameters must be JSON objects')
        from scripts.knowledge.contracts import KnowledgeBuildSpec
        spec=KnowledgeBuildSpec.from_dict(dict(dataset_id=identity,region_id=d['region_id'],date=d['date'],aoi=asset(d['aoi']),retained_seed=asset(d['candidate_seed']) if d.get('candidate_strategy','retained')=='retained' else None,dem=asset(d['dem']) if d.get('dem') else None,output_dir=str(managed/identity),sources={k:asset(v) for k,v in d.get('sources',{}).items()},parameters=d.get('parameters',{}),source_mode=d.get('candidate_strategy','retained'),reviewed_exclusions=asset(d['reviewed_exclusions']) if d.get('reviewed_exclusions') else None))
        spec.parameters['harmonize_history']=True
        for source in [spec.aoi,spec.retained_seed,spec.reviewed_exclusions,*spec.sources.values()]:
            if source is not None and source.metadata.get('region_id') not in (None,spec.region_id):raise ValueError('Selected source belongs to another region')
        spec.parameters['_history_sources']=history_sources(spec.region_id,spec.date)
        validate_imagery_dates(spec)
        mode=d.get('source_mode','import')
        if mode not in ('import','acquire'):raise ValueError('Unknown source mode')
        if mode!='acquire' and not {'spectral','scl'}.issubset(spec.sources):raise ValueError('New observation and retained reanalysis require date-matched spectral and SCL evidence')
        strategy=d.get('candidate_strategy','retained')
        if strategy not in ('retained','new'):raise ValueError('Unknown candidate strategy')
        builder=None
        if mode=='acquire' or strategy=='new':
            def builder(spec,log):
                from scripts.pipeline.region_inputs import resolve_region_inputs,RegionInputs
                from scripts.pipeline.inputs import load_aoi
                from scripts.knowledge.contracts import SourceAsset
                from scripts.knowledge.build import build_knowledge
                spec.parameters['_history_sources']=history_sources(spec.region_id,spec.date)
                validate_registry_date(registry(),spec.region_id,spec.date)
                from dotenv import load_dotenv
                from .unified_api import load_credentials
                load_credentials(root)
                from scripts.pipeline.elevation import acquire_dem,verify_dem_coverage
                aoi_frame=load_aoi(spec.aoi.path)
                static_only=spec.parameters.get('static_inputs_only',False)
                spec.dem=RegionInputs(root,spec.region_id,aoi_frame).resolve_dem(spec.dem,log,**({'local_only':True} if static_only else {}))
                log('Resolving processed inputs, raw evidence and missing downloads for declared region/date')
                acquired,manifest=resolve_region_inputs(root,spec.region_id,aoi_frame,spec.date,log=log,refresh=spec.parameters.get('refresh_obstacles',False),existing=spec.sources,**({'static_only':True} if static_only else {})) if mode=='acquire' else ({},{})
                for key,path in acquired.items():
                    if key=='osm':
                        import pyogrio
                        layers={entry[0] for entry in pyogrio.list_layers(path)}
                        for layer,target in {'buildings':'osm_buildings','roads':'roads','water':'water','industrial':'industrial','facilities':'facilities','water_polygons':'water','power':'power','man_made':'man_made','barriers':'barriers'}.items():
                            if layer in layers and target not in spec.sources:spec.sources[target]=SourceAsset(f'acquired-osm-{layer}',path,kind='vector',layer=layer,date=None,coverage_state='supplied',metadata={'acquisition_manifest':manifest,'date_status':'acquisition-time mapped snapshot; not the imagery observation date'})
                            elif layer not in layers and target not in spec.sources:log(f'Context layer {layer} unavailable; evidence remains unknown')
                    else:
                        target='buildings' if key=='overture' else key
                        source_date='2021-01-01' if key=='landcover' else spec.date if key in ('spectral','scl') else None
                        snapshot=manifest.get('input_snapshots',{}).get('overture' if key=='overture' else 'landcover' if key=='landcover' else 'sentinel',{})
                        metadata={'acquisition_manifest':manifest,'input_snapshot':snapshot}
                        if key=='spectral':metadata.update(band_map={'blue':1,'green':2,'red':3,'nir':4},band_names=['B02','B03','B04','B08','B11','B12'])
                        if key=='landcover':metadata.update(reference_year=2021,date_status='annual historical product; not current obstacle clearance',license='CC BY 4.0')
                        if key=='overture':metadata['date_status']='acquisition-time mapped snapshot; source edition is not the imagery observation date'
                        if target not in spec.sources:spec.sources[target]=SourceAsset(f'acquired-{key}',path,kind=key,date=source_date,coverage_state='supplied',metadata=metadata)
                return build_knowledge(spec,log=log)
        else:
            def builder(spec,log):
                from scripts.knowledge.build import build_knowledge
                spec.parameters['_history_sources']=history_sources(spec.region_id,spec.date)
                validate_registry_date(registry(),spec.region_id,spec.date)
                from scripts.pipeline.elevation import acquire_dem,verify_dem_coverage
                from scripts.knowledge.sources import read_vector
                from scripts.pipeline.region_inputs import RegionInputs
                spec.dem=RegionInputs(root,spec.region_id,read_vector(spec.aoi)).resolve_dem(spec.dem,log)
                return build_knowledge(spec,log=log)
        return jsonify(jobs.submit(spec,builder=builder)),202
    @bp.post('/api/knowledge/enrich-current')
    def enrich_current():
        denied=guard()
        if denied:return denied
        d=request.get_json(silent=True) or {}
        if not isinstance(d,dict):raise ValueError('Expected JSON object')
        region_id=d['region_id'];r=registry();current_id=r.get('selected',{}).get(region_id)
        if not current_id:raise ValueError('This region has no current knowledge to enrich')
        if any(j['status'] in ('queued','running') and j.get('date')==r['datasets'][current_id]['date'] for j in jobs.list(region_id,include_unfinished=True)):raise ValueError('An enrichment of this observation is already processing; inspect its progress')
        if any(j.get('region_id')==region_id and j.get('review',{}).get('decision')=='pending' and j.get('result',{}).get('enrichment_of')==current_id for j in jobs.list(region_id)):raise ValueError('An enrichment is already ready for review')
        source=package(current_id);entry=r['datasets'][current_id]
        from types import SimpleNamespace
        spec=SimpleNamespace(dataset_id=region_id+'-temporal-'+uuid4().hex[:12],region_id=region_id,date=entry['date'])
        def enrich(spec,log):
            from scripts.knowledge.history import harmonize_history
            from scripts.knowledge.enrichment import enrich_package
            from scripts.knowledge.sources import file_sha256
            if registry().get('selected',{}).get(region_id)!=current_id or file_sha256(source)!=entry['package_sha256']:raise ValueError('Current knowledge changed before enrichment; start again')
            historical=history_sources(region_id,spec.date)
            if not historical:raise ValueError('No earlier observations available for temporal enrichment')
            historical=harmonize_history(historical,managed/'history-cache','calibrated',log)
            return enrich_package(source,managed/spec.dataset_id,spec.dataset_id,historical,log)
        return jsonify(jobs.submit(spec,builder=enrich)),202
    @bp.get('/api/knowledge/jobs/<job_id>')
    def job(job_id):
        j=jobs.get(job_id)
        if not j:raise LookupError('Unknown build job')
        return jsonify(j)
    @bp.post('/api/knowledge/jobs/<job_id>/publish')
    def publish(job_id):
        denied=guard()
        if denied:return denied
        d=request.get_json(silent=True) or {}
        if not isinstance(d,dict):raise ValueError('Expected JSON object')
        return jsonify(reviews.accept(job_id,d.get('preview_token')))
    @bp.get('/api/knowledge/jobs')
    def completed_jobs():
        denied=guard()
        if denied:return denied
        return jsonify(jobs=jobs.list(request.args.get('region_id'),include_unfinished=True))
    @bp.get('/api/knowledge/jobs/<job_id>/preview')
    def preview_job(job_id):
        denied=guard()
        if denied:return denied
        return jsonify(reviews.preview(job_id) if request.args.get('format')=='geojson' else reviews.summary(job_id))
    @bp.post('/api/knowledge/jobs/<job_id>/accept')
    def accept_job(job_id):return publish(job_id)
    @bp.post('/api/knowledge/jobs/<job_id>/reject')
    def reject_job(job_id):
        denied=guard()
        if denied:return denied
        return jsonify(reviews.reject(job_id))
    @bp.post('/api/datasets/<dataset_id>/activate')
    def activate(dataset_id):
        denied=guard()
        if denied:return denied
        package(dataset_id)
        from scripts.knowledge.sources import file_sha256
        if file_sha256(package(dataset_id))!=registry()['datasets'][dataset_id].get('package_sha256'):raise ValueError('immutable package hash mismatch')
        raise ValueError('Inspect the build map preview and confirm replacement through its review action')
    app.register_blueprint(bp);app.extensions['knowledge_jobs']=jobs
    from .input_workspace import register_input_workspace
    register_input_workspace(app,root,source_catalog,guard)
