"""Immutable standard GeoPackage hierarchy and explicit atomic registry.

Feature geometries use the GeoPackage binary header and registered RTree
extensions. The SQLite relationships are actual foreign keys, not ID conventions.
"""
from pathlib import Path
from contextlib import closing,contextmanager
import datetime
import hashlib
import json
import os
import sqlite3
import struct
import uuid
import time
import math
from threading import RLock
import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from shapely import wkb
from shapely.geometry import mapping, shape, box, Point
from shapely.ops import transform as transform_geometry
from .contracts import json_safe

_registry_lock=RLock()

@contextmanager
def registry_guard(registry_path):
    """Serialize atomic registry mutations across threads and local processes."""
    path=Path(registry_path);path.parent.mkdir(parents=True,exist_ok=True)
    with _registry_lock,open(str(path)+'.lock','a+b') as handle:
        handle.seek(0)
        if handle.read(1)==b'':handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            deadline=time.monotonic()+120
            while True:
                try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError:
                    if time.monotonic()>deadline:raise ValueError('Knowledge registry is busy; retry after the current publication')
                    time.sleep(.05)
            try:yield
            finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
            try:yield
            finally:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def dumps(value): return json.dumps(json_safe(value),sort_keys=True,separators=(',',':'))

def _replace_file(source,target):
    # Windows indexers/OneDrive may briefly hold an otherwise closed target.
    for attempt in range(10):
        try:
            os.replace(source,target); return
        except PermissionError:
            if attempt==9: raise
            time.sleep(.05)

def geometry_blob(geometry,srs_id):
    x0,y0,x1,y1=geometry.bounds
    return b'GP'+bytes([0,3])+struct.pack('<i4d',srs_id,x0,x1,y0,y1)+geometry.wkb

def decode_geometry(blob):
    if not isinstance(blob,bytes) or blob[:2]!=b'GP': raise ValueError('invalid GeoPackage geometry header')
    envelope=(blob[3]>>1)&7
    size={0:0,1:32,2:48,3:48,4:64}.get(envelope)
    if size is None: raise ValueError('unsupported geometry envelope')
    return wkb.loads(blob[8+size:])


def _prevalidate(data):
    terrain=data['terrain']; zones=data['zones']
    for frame,key in ((terrain,'terrain_id'),(zones,'zone_id')):
        if key not in frame or frame[key].isna().any() or frame[key].astype(str).duplicated().any(): raise ValueError(f'{key} must be nonnull unique')
        if frame.crs is None: raise ValueError('feature CRS missing')
        if any(g is None or g.is_empty or not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon') for g in frame.geometry): raise ValueError('invalid feature geometry')
    if not set(zones.terrain_id.astype(str)).issubset(set(terrain.terrain_id.astype(str))): raise ValueError('zone references absent parent')
    crs=CRS.from_user_input(terrain.crs)
    if not crs.is_projected or not all(abs(a.unit_conversion_factor-1)<1e-8 for a in crs.axis_info[:2]): raise ValueError('knowledge geometry requires metric CRS')
    if CRS.from_user_input(zones.crs)!=crs: raise ValueError('parent/child CRS mismatch')
    parent_geoms=dict(zip(terrain.terrain_id.astype(str),terrain.geometry))
    for _,row in zones.iterrows():
        if row.geometry.difference(parent_geoms[str(row.terrain_id)]).area>1e-5: raise ValueError('child outside parent')
    for frame,key in ((data.get('characteristics',pd.DataFrame()),'terrain_id'),(data.get('environment',pd.DataFrame()),'zone_id')):
        if not frame.empty and (frame[key].duplicated().any() or frame[key].isna().any()): raise ValueError(f'{key} attribute keys must be unique')
    from .temporal import aggregate_observations
    entities={('terrain',str(row.terrain_id)):row.geometry.area for _,row in terrain.iterrows()}
    entities.update({('zones',str(row.zone_id)):row.geometry.area for _,row in zones.iterrows()})
    observed={}
    for row in data.get('temporal_observations',[]):
        key=(row['entity_type'],row['entity_id'])
        if key not in entities:raise ValueError('temporal observation references absent entity')
        areas=[row.get(name) for name in ('open_area_m2','valid_area_m2','unknown_area_m2')]
        if any(not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 for value in areas):raise ValueError('temporal areas must be finite and nonnegative')
        opened,valid,unknown=areas
        if opened>valid+1e-5 or not math.isclose(valid+unknown,entities[key],rel_tol=1e-7,abs_tol=1e-4):raise ValueError('temporal valid/unknown areas do not conserve entity area')
        observed.setdefault(key,[]).append(row)
    for key,rows in observed.items():aggregate_observations(entities[key],rows)
    aggregates=data.get('temporal_aggregates',[])
    if len({(r['entity_type'],r['entity_id']) for r in aggregates})!=len(aggregates):raise ValueError('duplicate temporal aggregate entity')
    for row in aggregates:
        key=(row['entity_type'],row['entity_id'])
        if key not in entities:raise ValueError('temporal aggregate references absent entity')
        expected=aggregate_observations(entities[key],observed.get(key,[]))
        if 'available_history_date_count' in row:
            from .chronology import observation_date
            declared=row.get('history_dates',[])
            if not isinstance(declared,list) or declared!=sorted(set(declared)) or not set(expected['history_dates']).issubset(declared):raise ValueError('invalid requested historical dates')
            current_date=data.get('metadata',{}).get('date') or getattr(data.get('spec'),'date',None)
            if not current_date:raise ValueError('temporal evidence requires an observation date')
            if any(observation_date(day)>=observation_date(current_date) for day in declared):raise ValueError('historical date must precede observation')
            available=len(expected['history_dates'])
            if row['available_history_date_count']!=available:raise ValueError('available history count differs from dated observations')
            expected['temporal_support']*=available/len(declared) if declared else 0
            expected.update(history_dates=declared,history_date_count=len(declared))
        for name,value in expected.items():
            actual=row.get(name)
            if isinstance(value,float):
                if not isinstance(actual,(int,float)) or not math.isclose(value,actual,rel_tol=1e-9,abs_tol=1e-9):raise ValueError('temporal aggregate differs from normalized dated observations')
            elif actual!=value:raise ValueError('temporal aggregate differs from normalized dated observations')


def write_package(build_data,output_path):
    _prevalidate(build_data)
    output_path=Path(output_path)
    if output_path.exists(): raise FileExistsError(f'immutable package exists: {output_path}')
    output_path.parent.mkdir(parents=True,exist_ok=True)
    staged=output_path.with_name(output_path.name+'.'+uuid.uuid4().hex+'.staging')
    terrain=build_data['terrain']; zones=build_data['zones']; crs=CRS.from_user_input(terrain.crs)
    srs_id=crs.to_epsg() or 100000
    metadata=dict(build_data.get('metadata',{}))
    if 'spec' in build_data:
        spec=build_data['spec']; metadata.update(dataset_id=spec.dataset_id,region_id=spec.region_id,date=spec.date,build_spec=spec.to_dict())
    dataset_id=metadata.get('dataset_id') or str(terrain.dataset_id.iloc[0])
    metadata.update(dataset_id=dataset_id,crs=crs.to_string(),counts={'terrain':len(terrain),'zones':len(zones)},schema_version=1)
    try:
        with closing(sqlite3.connect(staged)) as db:
            db.execute('PRAGMA application_id=1196444487'); db.execute('PRAGMA user_version=10300'); db.execute('PRAGMA foreign_keys=ON')
            db.executescript('''
CREATE TABLE gpkg_spatial_ref_sys (srs_name TEXT NOT NULL,srs_id INTEGER NOT NULL PRIMARY KEY,organization TEXT NOT NULL,organization_coordsys_id INTEGER NOT NULL,definition TEXT NOT NULL,description TEXT);
CREATE TABLE gpkg_contents (table_name TEXT NOT NULL PRIMARY KEY,data_type TEXT NOT NULL,identifier TEXT UNIQUE,description TEXT DEFAULT '',last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),min_x DOUBLE,min_y DOUBLE,max_x DOUBLE,max_y DOUBLE,srs_id INTEGER,FOREIGN KEY(srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id));
CREATE TABLE gpkg_geometry_columns(table_name TEXT NOT NULL,column_name TEXT NOT NULL,geometry_type_name TEXT NOT NULL,srs_id INTEGER NOT NULL,z TINYINT NOT NULL,m TINYINT NOT NULL,PRIMARY KEY(table_name,column_name),FOREIGN KEY(srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id),FOREIGN KEY(table_name) REFERENCES gpkg_contents(table_name));
CREATE TABLE gpkg_extensions(table_name TEXT,column_name TEXT,extension_name TEXT NOT NULL,definition TEXT NOT NULL,scope TEXT NOT NULL,UNIQUE(table_name,column_name,extension_name));
CREATE TABLE aois(region_id TEXT PRIMARY KEY,record_json TEXT NOT NULL);
CREATE TABLE dataset_versions(dataset_id TEXT PRIMARY KEY,region_id TEXT NOT NULL REFERENCES aois(region_id),date TEXT,record_json TEXT NOT NULL);
CREATE TABLE analysis_runs(run_id TEXT PRIMARY KEY,dataset_id TEXT NOT NULL REFERENCES dataset_versions(dataset_id),record_json TEXT NOT NULL);
CREATE TABLE sources(source_id TEXT PRIMARY KEY,dataset_id TEXT NOT NULL REFERENCES dataset_versions(dataset_id),sha256 TEXT NOT NULL,record_json TEXT NOT NULL);
CREATE TABLE analysis_parameters(dataset_id TEXT PRIMARY KEY REFERENCES dataset_versions(dataset_id),record_json TEXT NOT NULL);
CREATE TABLE terrain(fid INTEGER PRIMARY KEY AUTOINCREMENT,terrain_id TEXT UNIQUE NOT NULL,source_zone_id TEXT NOT NULL,dataset_id TEXT NOT NULL REFERENCES dataset_versions(dataset_id),geom BLOB NOT NULL,record_json TEXT NOT NULL);
CREATE TABLE zones(fid INTEGER PRIMARY KEY AUTOINCREMENT,zone_id TEXT UNIQUE NOT NULL,terrain_id TEXT NOT NULL REFERENCES terrain(terrain_id),dataset_id TEXT NOT NULL REFERENCES dataset_versions(dataset_id),slope_threshold_deg REAL NOT NULL CHECK(slope_threshold_deg>=0 AND slope_threshold_deg<=90),geom BLOB NOT NULL,record_json TEXT NOT NULL);
CREATE TABLE terrain_characteristics(terrain_id TEXT PRIMARY KEY REFERENCES terrain(terrain_id),record_json TEXT NOT NULL);
CREATE TABLE zone_environment(zone_id TEXT PRIMARY KEY REFERENCES zones(zone_id),record_json TEXT NOT NULL);
CREATE TABLE lineage(id INTEGER PRIMARY KEY,terrain_id TEXT NOT NULL REFERENCES terrain(terrain_id),zone_id TEXT,record_json TEXT NOT NULL);
CREATE TABLE entity_sources(entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,source_id TEXT NOT NULL REFERENCES sources(source_id),PRIMARY KEY(entity_type,entity_id,source_id));
CREATE TABLE package_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE temporal_observations(dataset_id TEXT NOT NULL REFERENCES dataset_versions(dataset_id),entity_type TEXT NOT NULL CHECK(entity_type IN ('terrain','zones')),entity_id TEXT NOT NULL,date TEXT NOT NULL,source_id TEXT NOT NULL REFERENCES sources(source_id),record_json TEXT NOT NULL,PRIMARY KEY(dataset_id,entity_type,entity_id,date));
CREATE TABLE temporal_aggregates(dataset_id TEXT NOT NULL REFERENCES dataset_versions(dataset_id),entity_type TEXT NOT NULL CHECK(entity_type IN ('terrain','zones')),entity_id TEXT NOT NULL,record_json TEXT NOT NULL,PRIMARY KEY(dataset_id,entity_type,entity_id));
CREATE INDEX idx_zones_parent_threshold ON zones(terrain_id,slope_threshold_deg);
CREATE INDEX idx_zones_threshold ON zones(slope_threshold_deg);
''')
            for row in [('Undefined Cartesian',-1,'NONE',-1,'undefined',''),('Undefined geographic',0,'NONE',0,'undefined',''),('WGS 84',4326,'EPSG',4326,CRS.from_epsg(4326).to_wkt(),''),(crs.name,srs_id,'EPSG' if crs.to_epsg() else 'NONE',srs_id,crs.to_wkt(),'processing metric CRS')]:
                db.execute('INSERT OR IGNORE INTO gpkg_spatial_ref_sys VALUES (?,?,?,?,?,?)',row)
            region_id=metadata.get('region_id','unknown')
            db.execute('INSERT INTO aois VALUES (?,?)',(region_id,dumps(build_data.get('aoi_record',{'region_id':region_id}))))
            db.execute('INSERT INTO dataset_versions VALUES (?,?,?,?)',(dataset_id,region_id,metadata.get('date'),dumps(metadata)))
            db.execute('INSERT INTO analysis_runs VALUES (?,?,?)',(dataset_id,dataset_id,dumps(build_data.get('run',{}))))
            db.execute('INSERT INTO analysis_parameters VALUES (?,?)',(dataset_id,dumps(build_data.get('parameters',{}))))
            source_ids=[]
            for key,source in build_data.get('sources',{}).items():
                source=dict(source); source_id=source.get('source_id',key)
                if source_id in source_ids: continue
                if not source.get('sha256'): raise ValueError('source missing hash')
                source_ids.append(source_id)
                db.execute('INSERT INTO sources VALUES (?,?,?,?)',(source_id,dataset_id,source['sha256'],dumps(source)))
            for table,frame,id_key in [('terrain',terrain,'terrain_id'),('zones',zones,'zone_id')]:
                bounds=list(frame.total_bounds) if len(frame) else [None]*4
                db.execute('INSERT INTO gpkg_contents(table_name,data_type,identifier,min_x,min_y,max_x,max_y,srs_id) VALUES (?,?,?,?,?,?,?,?)',(table,'features',table,*bounds,srs_id))
                db.execute('INSERT INTO gpkg_geometry_columns VALUES (?,?,?,?,0,0)',(table,'geom','GEOMETRY',srs_id))
                db.execute(f'CREATE VIRTUAL TABLE rtree_{table}_geom USING rtree(id,minx,maxx,miny,maxy)')
                db.execute('INSERT INTO gpkg_extensions VALUES (?,?,?,?,?)',(table,'geom','gpkg_rtree_index','http://www.geopackage.org/spec/#extension_rtree','write-only'))
                for _,row in frame.iterrows():
                    geometry=row.geometry; record=row.drop(labels=['geometry']).to_dict(); record['crs']=crs.to_string()
                    if str(record.get('dataset_id',dataset_id))!=dataset_id: raise ValueError('mixed dataset IDs')
                    record['dataset_id']=dataset_id
                    blob=geometry_blob(geometry,srs_id)
                    if table=='terrain':
                        cursor=db.execute('INSERT INTO terrain(terrain_id,source_zone_id,dataset_id,geom,record_json) VALUES (?,?,?,?,?)',(str(row[id_key]),str(row.get('source_zone_id',row[id_key])),dataset_id,blob,dumps(record)))
                    else:
                        cursor=db.execute('INSERT INTO zones(zone_id,terrain_id,dataset_id,slope_threshold_deg,geom,record_json) VALUES (?,?,?,?,?,?)',(str(row[id_key]),str(row.terrain_id),dataset_id,float(row.slope_threshold_deg),blob,dumps(record)))
                    x0,y0,x1,y1=geometry.bounds
                    db.execute(f'INSERT INTO rtree_{table}_geom VALUES (?,?,?,?,?)',(cursor.lastrowid,x0,x1,y0,y1))
                    for source_id in source_ids: db.execute('INSERT INTO entity_sources VALUES (?,?,?)',(table,str(row[id_key]),source_id))
            for table,frame,key in [('terrain_characteristics',build_data.get('characteristics',pd.DataFrame()),'terrain_id'),('zone_environment',build_data.get('environment',pd.DataFrame()),'zone_id')]:
                for _,row in frame.iterrows(): db.execute(f'INSERT INTO {table} VALUES (?,?)',(str(row[key]),dumps(row.to_dict())))
            for _,row in build_data.get('lineage',pd.DataFrame()).iterrows():
                record=row.to_dict(); zid=record.get('zone_id')
                db.execute('INSERT INTO lineage(terrain_id,zone_id,record_json) VALUES (?,?,?)',(str(row.terrain_id),None if pd.isna(zid) else str(zid),dumps(record)))
            entity_ids={'terrain':set(terrain.terrain_id.astype(str)),'zones':set(zones.zone_id.astype(str))}
            for row in build_data.get('temporal_observations',[]):
                if row['entity_id'] not in entity_ids.get(row['entity_type'],set()):raise ValueError('temporal observation references absent entity')
                if row['date']>=metadata.get('date',''):raise ValueError('temporal observation must precede dataset observation date')
                db.execute('INSERT INTO temporal_observations VALUES (?,?,?,?,?,?)',(dataset_id,row['entity_type'],row['entity_id'],row['date'],row['source_id'],dumps(row)))
            for row in build_data.get('temporal_aggregates',[]):
                if row['entity_id'] not in entity_ids.get(row['entity_type'],set()):raise ValueError('temporal aggregate references absent entity')
                db.execute('INSERT INTO temporal_aggregates VALUES (?,?,?,?)',(dataset_id,row['entity_type'],row['entity_id'],dumps(row)))
            db.execute('INSERT INTO package_metadata VALUES (?,?)',('metadata',dumps(metadata)))
            db.commit()
        report=validate_package(staged)
        if not report['valid']: raise ValueError('package validation failed: '+ '; '.join(report['errors']))
        if output_path.exists(): raise FileExistsError(f'immutable package exists: {output_path}')
        _replace_file(staged,output_path)
        return {**report,'package_path':str(output_path.resolve()),'dataset_id':dataset_id}
    except Exception:
        staged.unlink(missing_ok=True)
        raise


def validate_package(path):
    path=Path(path); errors=[]; counts={}; metadata={}
    if not path.is_file(): return {'valid':False,'errors':['package missing'],'counts':{}}
    try:
        with closing(sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro',uri=True)) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': errors.append('SQLite integrity failure')
            if db.execute('PRAGMA foreign_key_check').fetchall(): errors.append('foreign key violation')
            metadata=json.loads(db.execute("SELECT value FROM package_metadata WHERE key='metadata'").fetchone()[0])
            parent_geoms={}
            for table,key in [('terrain','terrain_id'),('zones','zone_id')]:
                rows=db.execute(f'SELECT fid,{key},geom,record_json FROM {table}').fetchall(); counts[table]=len(rows)
                indexed=dict((row[0],row[1:]) for row in db.execute(f'SELECT id,minx,maxx,miny,maxy FROM rtree_{table}_geom'))
                if len(indexed)!=len(rows): errors.append(f'{table} RTree count mismatch')
                for fid,entity_id,blob,record_json in rows:
                    try:
                        geometry=decode_geometry(blob); record=json.loads(record_json)
                        if table=='terrain':
                            characteristic=db.execute('SELECT record_json FROM terrain_characteristics WHERE terrain_id=?',(entity_id,)).fetchone()
                            if characteristic:record={**record,**json.loads(characteristic[0])}
                        if not geometry.is_valid or geometry.is_empty or not np.isfinite(geometry.bounds).all(): errors.append(f'{table} invalid geometry {entity_id}')
                        if fid not in indexed: errors.append(f'{table} missing spatial index {entity_id}')
                        else:
                            minx,maxx,miny,maxy=indexed[fid]; x0,y0,x1,y1=geometry.bounds
                            if minx>x0+1e-5 or maxx<x1-1e-5 or miny>y0+1e-5 or maxy<y1-1e-5: errors.append(f'{table} spatial index bounds mismatch {entity_id}')
                        if record.get('dataset_id')!=metadata.get('dataset_id'): errors.append('mixed dataset identity')
                        area=record.get('area_m2')
                        if area is not None and not np.isclose(area,geometry.area,atol=1e-4,rtol=1e-9): errors.append(f'{table} stored area mismatch {entity_id}')
                        radius=record.get('max_clear_radius_m')
                        if radius is not None:
                            px,py=record.get('poi_easting'),record.get('poi_northing')
                            if px is None or py is None or not np.isfinite([px,py,radius]).all(): errors.append(f'{table} missing/invalid MIC center {entity_id}')
                            else:
                                center=Point(px,py)
                                if not geometry.covers(center) or abs(center.distance(geometry.boundary)-radius)>1e-4: errors.append(f'{table} stored clearance mismatch {entity_id}')
                            diameter=record.get('max_clear_diameter_m')
                            if diameter is not None and abs(diameter-2*radius)>1e-4: errors.append(f'{table} diameter/radius mismatch {entity_id}')
                        if table=='terrain': parent_geoms[entity_id]=geometry
                        else:
                            parent=parent_geoms.get(record.get('terrain_id'))
                            if parent is None or geometry.difference(parent).area>1e-5: errors.append(f'zone outside/missing parent {entity_id}')
                            maximum=record.get('max_slope_deg'); threshold=record.get('slope_threshold_deg')
                            if maximum is not None and maximum>threshold+1e-4: errors.append(f'zone exceeds slope threshold {entity_id}')
                    except Exception as exc: errors.append(f'{table} geometry decode failed {entity_id}: {exc}')
            if counts!=metadata.get('counts'): errors.append('manifest count mismatch')
            if db.execute('SELECT COUNT(*) FROM sources WHERE sha256 IS NULL OR sha256=""').fetchone()[0]: errors.append('source hash missing')
            for table in ('terrain','zones'):
                key='terrain_id' if table=='terrain' else 'zone_id'
                if db.execute(f'SELECT COUNT(*) FROM {table} WHERE {key} IS NULL').fetchone()[0]: errors.append('null entity ID')
            # No same-parent/same-threshold overlaps, while nesting across thresholds is legal.
            for terrain_id,threshold in db.execute('SELECT DISTINCT terrain_id,slope_threshold_deg FROM zones'):
                blobs=db.execute('SELECT geom FROM zones WHERE terrain_id=? AND slope_threshold_deg=?',(terrain_id,threshold)).fetchall()
                if len(blobs)>1:
                    from shapely.ops import unary_union
                    geoms=[decode_geometry(row[0]) for row in blobs]
                    if sum(g.area for g in geoms)-unary_union(geoms).area>1e-4: errors.append('same-threshold child overlap')
    except Exception as exc: errors.append(f'package unreadable: {exc}')
    return {'valid':not errors,'errors':errors,'counts':counts,'metadata':metadata}


def _atomic_json(path,payload):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with open(temp,'w',encoding='utf-8') as stream:
            json.dump(json_safe(payload),stream,indent=2); stream.flush(); os.fsync(stream.fileno())
        _replace_file(temp,path)
    finally: temp.unlink(missing_ok=True)


def register_dataset(dataset_id,package_path,registry_path,require_forward=False):
    # Administrative import remains available; ordinary publication is forward only.
    with registry_guard(registry_path):
        return _register_dataset(dataset_id,package_path,registry_path,require_forward)


def _require_current_history(registry,region_id,package_path,candidate_date):
    from .chronology import current_entry
    _,current=current_entry(registry,region_id)
    source=current.get('observation_source')
    if not source or source['date']>=candidate_date:return
    with closing(sqlite3.connect(f'{Path(package_path).resolve().as_uri()}?mode=ro',uri=True)) as db:
        rows=db.execute('SELECT source_id,sha256,record_json FROM sources').fetchall()
        identities=[]
        for identity,digest,record in rows:
            record=json.loads(record)
            same_source=digest==source['sha256']
            harmonized=record.get('original_classification_sha256')==source['sha256'] and record.get('original_source_id')==source.get('source_id')
            if record.get('date')==source['date'] and (same_source or harmonized):identities.append(identity)
        has_table=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='temporal_observations'").fetchone()
        count=0
        if identities and has_table:
            placeholders=','.join('?' for _ in identities)
            count=db.execute(f'SELECT COUNT(*) FROM temporal_observations WHERE date=? AND source_id IN ({placeholders})',(source['date'],*identities)).fetchone()[0]
        expected=sum(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('terrain','zones'))
        if not identities or not has_table or count!=expected:raise ValueError('History changed since build; rebuild with the current observation before publication or activation')


def _register_dataset(dataset_id,package_path,registry_path,require_forward):
    report=validate_package(package_path)
    if not report['valid'] or report['metadata'].get('dataset_id')!=dataset_id: raise ValueError('cannot register unvalidated/mismatched dataset')
    registry_path=Path(registry_path)
    registry=json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.exists() else {'datasets':{},'selected':{}}
    if require_forward:
        from .chronology import validate_registry_date
        validate_registry_date(registry,report['metadata']['region_id'],report['metadata'].get('date'))
        _require_current_history(registry,report['metadata']['region_id'],package_path,report['metadata'].get('date'))
    entry={'package_path':str(Path(package_path).resolve()),'region_id':report['metadata']['region_id'],'date':report['metadata'].get('date'),'validation':{'valid':True,'errors':[]},'package_sha256':hashlib.sha256(Path(package_path).read_bytes()).hexdigest(),'observation_source':report['metadata'].get('observation_source'),'temporal_summary':report['metadata'].get('temporal_summary')}
    previous=registry['datasets'].get(dataset_id)
    if previous and previous.get('package_sha256')!=entry['package_sha256']: raise ValueError('registered dataset ID is immutable')
    registry['datasets'][dataset_id]=entry
    _atomic_json(registry_path,registry)
    return entry


def activate_dataset(dataset_id,registry_path,administrative_recovery=False):
    with registry_guard(registry_path):
        return _activate_dataset(dataset_id,registry_path,administrative_recovery)


def _activate_dataset(dataset_id,registry_path,administrative_recovery):
    registry_path=Path(registry_path)
    registry=json.loads(registry_path.read_text(encoding='utf-8'))
    entry=registry.get('datasets',{}).get(dataset_id)
    if not entry: raise ValueError('dataset is not explicitly registered')
    report=validate_package(entry['package_path'])
    if not report['valid'] or report['metadata'].get('dataset_id')!=dataset_id: raise ValueError('dataset failed activation validation')
    digest=hashlib.sha256(Path(entry['package_path']).read_bytes()).hexdigest()
    if digest!=entry.get('package_sha256'): raise ValueError('immutable package hash mismatch')
    registry=json.loads(registry_path.read_text(encoding='utf-8'))
    if not administrative_recovery:
        from .chronology import validate_registry_date
        validate_registry_date(registry,entry['region_id'],entry.get('date'))
        _require_current_history(registry,entry['region_id'],entry['package_path'],entry.get('date'))
    previous=registry.setdefault('selected',{}).get(entry['region_id'])
    registry.setdefault('selected',{})[entry['region_id']]=dataset_id
    registry.setdefault('timeline',[]).append({'region_id':entry['region_id'],'dataset_id':dataset_id,'date':entry.get('date'),'previous_dataset_id':previous,'activated_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    _atomic_json(registry_path,registry)
    return {'dataset_id':dataset_id,'region_id':entry['region_id'],'package_path':entry['package_path'],'validation':report}


class KnowledgeRepository:
    def __init__(self,path):
        self.path=Path(path)
        self.metadata=validate_package(path)
        if not self.metadata['valid']: raise ValueError('invalid knowledge package: '+'; '.join(self.metadata['errors']))
        self.metadata={**self.metadata['metadata'],'validation':{'valid':True,'errors':[]}}
        self.dataset_id=self.metadata['dataset_id']; self.region_id=self.metadata['region_id']; self.crs=self.metadata['crs']

    def _connect(self):
        connection=sqlite3.connect(f'{self.path.resolve().as_uri()}?mode=ro',uri=True)
        connection.row_factory=sqlite3.Row
        return connection

    def get_metadata(self): return json_safe(self.metadata)

    def temporal_observations(self,entity_type,entity_id):
        if entity_type not in ('terrain','zones'):raise ValueError('Unknown temporal entity type')
        with closing(self._connect()) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='temporal_observations'").fetchone():return []
            return [json.loads(row[0]) for row in db.execute('SELECT record_json FROM temporal_observations WHERE dataset_id=? AND entity_type=? AND entity_id=? ORDER BY date',(self.dataset_id,entity_type,str(entity_id)))]

    def _records(self,table,where='',params=(),limit=None,offset=0,include_geometry=True,internal=False):
        key='terrain_id' if table=='terrain' else 'zone_id'
        query=f'SELECT e.* FROM {table} e'+(' WHERE '+where if where else '')+f' ORDER BY e.{key}'
        values=list(params)
        if limit is not None: query+=' LIMIT ? OFFSET ?'; values.extend([int(limit),int(offset)])
        elif offset: query+=' LIMIT -1 OFFSET ?'; values.append(int(offset))
        records=[]
        with closing(self._connect()) as db:
            has_temporal=bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='temporal_aggregates'").fetchone())
            for row in db.execute(query,values).fetchall():
                record=json.loads(row['record_json']); entity_id=row[key]
                terrain_id=entity_id if table=='terrain' else row['terrain_id']
                feature=db.execute('SELECT record_json FROM terrain_characteristics WHERE terrain_id=?',(terrain_id,)).fetchone()
                characteristics=json.loads(feature[0]) if feature else {}
                if table=='zones':
                    environmental=db.execute('SELECT record_json FROM zone_environment WHERE zone_id=?',(entity_id,)).fetchone()
                    environment=json.loads(environmental[0]) if environmental else {}
                    record={**characteristics,**record,**environment}
                    # Child geometry/slope take precedence, environment contributes evidence.
                    record['terrain_characteristics']=characteristics; record['environment']=environment
                else:
                    record={**record,**characteristics}
                    record['child_zone_count']=db.execute('SELECT count(*) FROM zones WHERE terrain_id=?',(entity_id,)).fetchone()[0]
                    record['child_threshold_counts']={str(th):count for th,count in db.execute('SELECT slope_threshold_deg,count(*) FROM zones WHERE terrain_id=? GROUP BY slope_threshold_deg',(entity_id,))}
                record['crs']=self.crs
                if has_temporal:
                    temporal=db.execute('SELECT record_json FROM temporal_aggregates WHERE dataset_id=? AND entity_type=? AND entity_id=?',(self.dataset_id,table,str(entity_id))).fetchone()
                    if temporal:record.update(json.loads(temporal[0]))
                if include_geometry or internal:
                    geometry=decode_geometry(row['geom'])
                    if include_geometry: record['geometry']=mapping(geometry)
                    if internal: record['metric_geometry']=geometry
                records.append(record)
        return records

    def list_terrain(self,limit=None,offset=0,include_geometry=True,internal=False):
        return self._records('terrain',limit=limit,offset=offset,include_geometry=include_geometry,internal=internal)

    def get_terrain(self,terrain_id,include_geometry=True,internal=False):
        rows=self._records('terrain','e.terrain_id=?',(str(terrain_id),),include_geometry=include_geometry,internal=internal)
        return rows[0] if rows else None

    def list_zones(self,terrain_id=None,slope_threshold_deg=None,limit=None,offset=0,include_geometry=True,internal=False):
        where=[]; params=[]
        if terrain_id is not None: where.append('e.terrain_id=?'); params.append(str(terrain_id))
        if slope_threshold_deg is not None: where.append('e.slope_threshold_deg=?'); params.append(float(slope_threshold_deg))
        return self._records('zones',' AND '.join(where),params,limit,offset,include_geometry,internal)

    def get_zone(self,zone_id,include_geometry=True,internal=False):
        rows=self._records('zones','e.zone_id=?',(str(zone_id),),include_geometry=include_geometry,internal=internal)
        return rows[0] if rows else None

    def get_environment(self,zone_id):
        with closing(self._connect()) as db:
            row=db.execute('SELECT record_json FROM zone_environment WHERE zone_id=?',(str(zone_id),)).fetchone()
        return json.loads(row[0]) if row else None

    def query_zones(self,bounds=None,latitude=None,longitude=None,radius_m=None,max_slope_deg=None,limit=None,internal=False):
        center=None
        if latitude is not None or longitude is not None:
            if None in (latitude,longitude,radius_m) or not np.isfinite([latitude,longitude,radius_m]).all() or radius_m<=0: raise ValueError('finite location and positive radius required')
            x,y=Transformer.from_crs(4326,self.crs,always_xy=True).transform(longitude,latitude)
            center=Point(x,y); bounds=(x-radius_m,y-radius_m,x+radius_m,y+radius_m)
        where=[]; params=[]
        if bounds is not None:
            x0,y0,x1,y1=bounds
            where.append('e.fid IN (SELECT id FROM rtree_zones_geom WHERE maxx>=? AND minx<=? AND maxy>=? AND miny<=?)'); params.extend([x0,x1,y0,y1])
        if max_slope_deg is not None: where.append('e.slope_threshold_deg<=?'); params.append(float(max_slope_deg))
        records=self._records('zones',' AND '.join(where),params,internal=True)
        if bounds is not None:
            search=box(*bounds)
            records=[r for r in records if r['metric_geometry'].intersects(search)]
        if center is not None:
            records=[r for r in records if r['metric_geometry'].distance(center)<=radius_m]
            for record in records: record['query_distance_m']=float(record['metric_geometry'].distance(center))
        if limit is not None: records=records[:int(limit)]
        if not internal:
            for record in records: record.pop('metric_geometry',None)
        return records

    def to_geojson(self,records):
        transformer=Transformer.from_crs(self.crs,4326,always_xy=True)
        features=[]
        for record in records:
            geometry=record.get('metric_geometry')
            if geometry is None and record.get('geometry'): geometry=shape(record['geometry'])
            if geometry is None: continue
            properties={key:value for key,value in record.items() if key not in ('geometry','metric_geometry')}
            features.append({'type':'Feature','id':record.get('zone_id',record.get('terrain_id')),'geometry':mapping(transform_geometry(transformer.transform,geometry)),'properties':json_safe(properties)})
        return {'type':'FeatureCollection','features':features,'dataset_id':self.dataset_id,'crs':'EPSG:4326'}

