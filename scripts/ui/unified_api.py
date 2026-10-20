"""Local unified-workspace region and credential services.

Credentials are deliberately never returned by these endpoints.
"""
import json
import os
import re
from datetime import date
from pathlib import Path
from threading import RLock
from urllib.parse import urlparse
from uuid import uuid4
from flask import Blueprint, jsonify, request

_lock=RLock()
CREDENTIALS=('CDSE_CLIENT_ID','CDSE_CLIENT_SECRET')


def region_records(root):
    path=Path(root)/'data/knowledge/regions.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def region_catalog(root,region_id):
    root=Path(root)
    if region_id=='bhadra':
        path=root/'docs/examples/bhadra-retained-build.json'
        if not path.exists():return {}
        spec=json.loads(path.read_text(encoding='utf-8'))
        return {**{k:spec[k] for k in ('aoi','retained_seed','dem','reviewed_exclusions') if spec.get(k)},**spec.get('sources',{})}
    region=region_records(root).get(region_id)
    if not region:raise ValueError('Choose an existing region or upload its boundary first')
    return {'aoi':region['aoi']}


def registered_region_features(root):
    """Published regions use their uploaded boundary in consumer map overviews."""
    root=Path(root).resolve();path=root/'data/knowledge/registry.json'
    registry=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    features=[]
    for identity,region in region_records(root).items():
        selected=registry.get('selected',{}).get(identity)
        current=registry.get('datasets',{}).get(selected,{})
        if current.get('region_id')!=identity:continue
        boundary=Path(region['aoi']['path']);boundary=boundary if boundary.is_absolute() else root/boundary
        if not boundary.is_file():continue
        import geopandas as gpd
        from shapely.geometry import mapping
        frame=gpd.read_file(boundary,layer=region['aoi'].get('layer') or None).to_crs(4326)
        geometry=frame.geometry.union_all()
        features.append({'type':'Feature','geometry':mapping(geometry),'properties':{'id':identity,'region_id':identity,'name':region['name'],'status':'ready','status_label':'Current knowledge available','dataset_id':selected,'date':current.get('date'),'center':[geometry.centroid.y,geometry.centroid.x]}})
    return features


def credential_values(root):
    from dotenv import dotenv_values
    root=Path(root)
    # The original project is read-only fallback while consolidation is pending.
    return {**dotenv_values(root.parent/'.env'),**{k:v for k,v in os.environ.items() if k in CREDENTIALS},**dotenv_values(root/'.env')}


def load_credentials(root):
    for key,value in credential_values(root).items():
        if key in CREDENTIALS and value:os.environ[key]=value


def register_unified_api(app,root):
    root=Path(root).resolve();bp=Blueprint('unified_workspace',__name__)
    def guard():
        if request.remote_addr not in ('127.0.0.1','::1'):return jsonify(error='This workspace is restricted to this computer'),403
        if request.headers.get('X-HELPS-Role')!='engineer':return jsonify(error='Local workflow header required'),403
        origin=request.headers.get('Origin')
        if origin and urlparse(origin).netloc!=request.host:return jsonify(error='Same local origin required'),403
    @bp.errorhandler(ValueError)
    def invalid(exc):return jsonify(error=str(exc)),400
    @bp.get('/api/knowledge/credentials')
    def credentials():
        if request.remote_addr not in ('127.0.0.1','::1'):return jsonify(error='Local access required'),403
        values=credential_values(root)
        return jsonify(credentials={key:{'configured':bool(values.get(key)),'masked':'Saved locally' if values.get(key) else 'Not configured'} for key in CREDENTIALS},weather='Open-Meteo is used without an API key')
    @bp.post('/api/knowledge/credentials')
    def save_credentials():
        denied=guard()
        if denied:return denied
        payload=request.get_json(silent=True)
        if not isinstance(payload,dict) or set(payload)-set(CREDENTIALS):raise ValueError('Supply only the supported Copernicus credential fields')
        updates={}
        for key,value in payload.items():
            if not isinstance(value,str) or len(value)>4096 or any(c in value for c in '\r\n\0'):raise ValueError('Credential contains invalid characters')
            if value.strip():updates[key]=value.strip()
        from dotenv import dotenv_values
        with _lock:
            target=root/'.env';existing=dict(dotenv_values(target))
            existing.update(updates)
            # Quoted dotenv values preserve punctuation without executing it.
            content='\n'.join(k+"='"+str(v or '').replace('\\','\\\\').replace("'","\\'")+"'" for k,v in existing.items())+'\n'
            temporary=target.with_name('.env.'+uuid4().hex+'.tmp')
            descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'w',encoding='utf-8') as stream:stream.write(content)
            os.replace(temporary,target)
            if os.name!='nt':target.chmod(0o600)
            for key,value in updates.items():os.environ[key]=value
        return credentials()
    @bp.get('/api/knowledge/regions')
    def regions():
        rows=[{'region_id':'bhadra','name':'Bhadra','existing':True}]
        rows.extend({k:v for k,v in row.items() if k not in ('aoi',)} for row in region_records(root).values())
        return jsonify(regions=rows)
    @bp.post('/api/knowledge/regions')
    def upload_region():
        denied=guard()
        if denied:return denied
        name=request.form.get('name','').strip();file=request.files.get('file')
        if not name or len(name)>80 or not file:raise ValueError('Region name and GeoJSON or GeoPackage boundary required')
        suffix=Path(file.filename or '').suffix.lower()
        if suffix not in ('.geojson','.json','.gpkg'):raise ValueError('Upload a polygon boundary as GeoJSON or GeoPackage')
        folder=root/'data/knowledge/regions';folder.mkdir(parents=True,exist_ok=True)
        temporary=folder/(uuid4().hex+suffix);file.save(temporary)
        try:
            if temporary.stat().st_size>20_000_000:raise ValueError('Boundary exceeds 20 MB; simplify the polygon')
            import geopandas as gpd
            import numpy as np
            frame=gpd.read_file(temporary,layer=request.form.get('layer') or None)
            if frame.empty or frame.crs is None:raise ValueError('Boundary requires a declared CRS and nonempty polygons')
            if not frame.geom_type.isin(['Polygon','MultiPolygon']).all() or not frame.is_valid.all() or frame.geometry.is_empty.any():raise ValueError('Boundary must contain valid Polygon or MultiPolygon geometry')
            frame=frame.to_crs(4326);bounds=frame.total_bounds
            if not np.isfinite(bounds).all() or bounds[0]<-180 or bounds[2]>180 or bounds[1]<-80 or bounds[3]>84 or bounds[2]-bounds[0]>5 or bounds[3]-bounds[1]>5:raise ValueError('Boundary extent is outside supported local processing limits')
            area=frame.to_crs(6933).geometry.union_all().area
            if not 100<=area<=400_000_000:raise ValueError('Boundary area must be between 100 m² and 400 km²')
            identity=re.sub('[^a-z0-9]+','-',name.lower()).strip('-')[:60]
            if not identity:raise ValueError('Region name must contain letters or numbers')
            with _lock:
                records=region_records(root)
                if identity=='bhadra' or identity in records:raise ValueError('A region with this name already exists')
                from scripts.pipeline.source_store import SourceStore
                import shutil
                store=SourceStore(root,identity,frame)
                def original(directory):
                    shutil.copyfile(temporary,directory/('boundary'+suffix))
                    return {'boundary':'boundary'+suffix},{'layer':request.form.get('layer') or None,'origin':'user uploaded boundary'}
                def prepare_boundary(raw,directory,metadata):
                    frame.to_file(directory/'boundary.geojson',driver='GeoJSON')
                    return {'boundary':'boundary.geojson'},metadata
                result=store.resolve('boundary',None,original,prepare_boundary,lambda paths,metadata:None,log=lambda _:None)
                target=result['paths']['boundary']
                from scripts.knowledge.sources import file_sha256
                record={'region_id':identity,'name':name,'existing':False,'bounds':bounds.tolist(),'area_m2':area,'aoi':{'source_id':'region-'+identity,'path':str(target),'kind':'aoi','crs':'EPSG:4326','coverage_state':'supplied','sha256':file_sha256(target)}}
                records[identity]=record;registry=folder.parent/'regions.json';stage=registry.with_suffix('.tmp');stage.write_text(json.dumps(records,indent=2),encoding='utf-8');os.replace(stage,registry)
        except ValueError:raise
        except Exception:raise ValueError('Boundary could not be read; check its format, CRS and layer') from None
        finally:temporary.unlink(missing_ok=True)
        return jsonify(region={k:v for k,v in record.items() if k!='aoi'}),201
    app.register_blueprint(bp)
