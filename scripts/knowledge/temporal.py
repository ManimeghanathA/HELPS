"""Exact dated classification overlap on immutable current geometries.

States: 0 non-open, 1 possible-open, 255 unknown. Unknown and outside raster
support never become non-open evidence. Windows bound memory, cell intersections
preserve fractional edges, holes and overlapping threshold geometries.
"""
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds
from pyproj import CRS,Transformer
from shapely.ops import transform as transform_geometry
from shapely.geometry import Polygon
from shapely.geometry import shape,box
from rasterio.features import shapes
from .sources import file_sha256
from .chronology import observation_date

ENCODING={'not_open':0,'open':1,'unknown':255}


def validate_history_raster(path,encoding=None):
    encoding=encoding or ENCODING
    if encoding!=ENCODING:raise ValueError('incompatible classification state encoding')
    with rasterio.open(path) as ds:
        if ds.crs is None:raise ValueError('classification CRS missing')
        crs=CRS.from_user_input(ds.crs)
        if not crs.is_projected or any(abs(axis.unit_conversion_factor-1)>1e-8 for axis in crs.axis_info[:2]):raise ValueError('classification requires metric projected CRS')
        if ds.count!=1:raise ValueError('classification must contain one state band')
        if ds.nodata not in (None,255):raise ValueError('classification nodata conflicts with valid state encoding')
        if not np.isfinite(tuple(ds.transform)).all() or abs(ds.transform.a*ds.transform.e-ds.transform.b*ds.transform.d)==0:raise ValueError('invalid classification grid')
        for _,window in ds.block_windows(1):
            if not set(np.unique(ds.read(1,window=window))).issubset(set(encoding.values())):raise ValueError('unsupported classification class; declare compatible encoding')
        return {'crs':str(ds.crs),'width':ds.width,'height':ds.height,'transform':list(ds.transform),'encoding':encoding,'sha256':file_sha256(path),'bounds':list(ds.bounds)}


def measure_overlap(geometry,geometry_crs,path):
    with rasterio.open(path) as ds:
        entity_crs=CRS.from_user_input(geometry_crs)
        if not entity_crs.is_projected or any(abs(axis.unit_conversion_factor-1)>1e-8 for axis in entity_crs.axis_info[:2]):raise ValueError('temporal entity area requires metric projected CRS')
        source_crs=CRS.from_user_input(ds.crs)
        if not source_crs.is_projected or any(abs(axis.unit_conversion_factor-1)>1e-8 for axis in source_crs.axis_info[:2]):raise ValueError('classification area requires metric projected CRS')
        same_crs=entity_crs==source_crs
        raster_geometry=geometry if same_crs else transform_geometry(Transformer.from_crs(entity_crs,ds.crs,always_xy=True).transform,geometry)
        to_entity=None if same_crs else Transformer.from_crs(ds.crs,entity_crs,always_xy=True).transform
        def entity_geometry(g):return g if same_crs else transform_geometry(to_entity,g)
        if not geometry.is_valid or geometry.is_empty:raise ValueError('invalid temporal geometry')
        if ds.transform.b or ds.transform.d:raise ValueError('rotated historical grid unsupported')
        bounds=raster_geometry.bounds
        raw=from_bounds(*bounds,transform=ds.transform)
        c0=max(0,int(np.floor(raw.col_off)));r0=max(0,int(np.floor(raw.row_off)))
        c1=min(ds.width,int(np.ceil(raw.col_off+raw.width)));r1=min(ds.height,int(np.ceil(raw.row_off+raw.height)))
        open_area=not_open=0.0
        covered=geometry.intersection(entity_geometry(box(*ds.bounds))).area
        for row in range(r0,r1,256):
            for col in range(c0,c1,256):
                window=Window(col,row,min(256,c1-col),min(256,r1-row))
                states=ds.read(1,window=window)
                if not set(np.unique(states)).issubset({0,1,255}):raise ValueError('unsupported classification class')
                for polygon,state in shapes(states,mask=states!=255,transform=ds.window_transform(window)):
                    area=geometry.intersection(entity_geometry(shape(polygon))).area
                    if state==1:open_area+=area
                    elif state==0:not_open+=area
        valid=open_area+not_open
        return {'open_area_m2':open_area,'not_open_area_m2':not_open,'valid_area_m2':valid,'unknown_area_m2':max(0.0,geometry.area-valid),'coverage_fraction':min(1.0,covered/geometry.area),'qa_state':'measured','valid_fraction':min(1.0,valid/geometry.area)}


def aggregate_observations(candidate_area_m2,rows):
    dates=[r['date'] for r in rows]
    if len(set(dates))!=len(dates):raise ValueError('duplicate temporal observation date; mosaic same-day products before measuring')
    valid=sum(r['valid_area_m2'] for r in rows);opened=sum(r['open_area_m2'] for r in rows)
    denominator=candidate_area_m2*len(rows)
    return {'history_dates':sorted(dates),'history_date_count':len(rows),'valid_history_count':sum(r['valid_area_m2']>0 for r in rows),'temporal_open_confidence':opened/valid if valid else None,'temporal_support':min(1.0,valid/denominator) if denominator else 0.0,'temporal_source_ids':sorted({r['source_id'] for r in rows})}


def discover_history(original_root,region_id='bhadra',before_date=None):
    """Read original artifacts only; preserve unknown provenance as explicit QA."""
    if region_id.lower()!='bhadra':return []
    folder=Path(original_root)/'data/processed/Bhadra/sentinel2'
    index=folder/'history_dates.json'
    if not index.exists():return []
    config=json.loads(index.read_text(encoding='utf-8'))
    dates=sorted(set(config['history_dates']+[config['current_reference_date']]))
    records=[]
    for day in dates:
        observation_date(day)
        if before_date and day>=before_date:continue
        date_dir=folder/day
        path=next((date_dir/name for name in ('bhadra_possible_open_mask.tif','bhadra_possible_open_mask_v2.tif') if (date_dir/name).is_file()),None)
        row={'date':day,'source_id':f'original-bhadra-state-{day}','path':str(path) if path else None,'status':'missing','provenance_state':'unknown','license_status':'classification derived from Copernicus Sentinel-2; processing provenance retained'}
        if path:
            try:
                run_path=date_dir/'run.json';run=json.loads(run_path.read_text(encoding='utf-8')) if run_path.exists() else {}
                if run and (run.get('date')!=day or run.get('provenance',{}).get('date',day)!=day):raise ValueError('history manifest observation date mismatch')
                row.update(validate_history_raster(path),status='available',provenance_state='manifest_date_verified' if run else 'unknown')
                row['manifest_sha256']=file_sha256(run_path) if run_path.exists() else None
                row['source_links']=run.get('provenance',{}).get('files',{})
                for key in ('spectral','scl'):
                    source=date_dir/f'bhadra_{key}.tif'
                    if source.exists():
                        with rasterio.open(source) as src:
                            if str(src.crs)!=row['crs'] or src.width!=row['width'] or src.height!=row['height'] or list(src.transform)!=row['transform']:raise ValueError(f'historical {key}/classification grid mismatch')
                        actual=file_sha256(source)
                        declared=row['source_links'].get(key,{}).get('sha256')
                        if declared and actual!=declared:raise ValueError(f'historical {key} hash differs from acquisition provenance')
                        row[key+'_sha256']=actual
            except (ValueError,OSError,rasterio.errors.RasterioError) as exc:row.update(status='failed',error=str(exc))
        records.append(row)
    return records


def compute_temporal(terrain,zones,history,current_date,dataset_id):
    observations=[];aggregates=[]
    requested_dates=sorted({r['date'] for r in history if r['date']<current_date})
    usable=[r for r in history if r['status']=='available' and r['date']<current_date]
    if len({r['date'] for r in usable})!=len(usable):raise ValueError('duplicate historical source date')
    for entity_type,frame,key in (('terrain',terrain,'terrain_id'),('zones',zones,'zone_id')):
        for _,entity in frame.iterrows():
            rows=[]
            for source in usable:
                measured=measure_overlap(entity.geometry,frame.crs,source['path'])
                row={'dataset_id':dataset_id,'entity_type':entity_type,'entity_id':str(entity[key]),'date':source['date'],'source_id':source['source_id'],'source_sha256':source['sha256'],'provenance_state':source['provenance_state'],**measured}
                rows.append(row);observations.append(row)
            aggregate=aggregate_observations(entity.geometry.area,rows)
            aggregate['available_history_date_count']=len(usable)
            aggregate['temporal_support']*=len(usable)/len(requested_dates) if requested_dates else 0
            aggregate.update(history_dates=requested_dates,history_date_count=len(requested_dates))
            aggregates.append({'dataset_id':dataset_id,'entity_type':entity_type,'entity_id':str(entity[key]),**aggregate})
    return observations,aggregates


def discover_managed_history(root,registry,region_id,before_date=None):
    """Published classification and explicit history imports are reusable evidence."""
    managed=(Path(root)/'data/knowledge').resolve();records=[]
    candidates=[entry.get('observation_source') for entry in registry.get('datasets',{}).values() if entry.get('region_id')==region_id]
    imports=managed/'observations.json'
    if imports.exists():candidates.extend(row for row in json.loads(imports.read_text(encoding='utf-8')).get('observations',[]) if row['region_id']==region_id)
    for source in candidates:
        if not source or (before_date and source['date']>=before_date):continue
        row=dict(source)
        try:
            path=Path(row['path']).resolve()
            if not path.is_relative_to(managed):raise ValueError('Historical classification outside managed knowledge')
            inspected=validate_history_raster(path,row.get('encoding'))
            if inspected['sha256']!=row['sha256']:raise ValueError('Published historical classification hash changed')
            row.update(inspected,status='available')
        except (OSError,ValueError,rasterio.errors.RasterioError) as exc:row.update(status='failed',error=str(exc))
        records.append(row)
    return records


def register_observation(root,source):
    """Historical evidence import never registers or activates a knowledge package."""
    from .repository import registry_guard,_atomic_json
    path=Path(root)/'data/knowledge/observations.json'
    inspected=validate_history_raster(source['path'],source.get('encoding'))
    if source['sha256']!=inspected['sha256']:raise ValueError('Historical import hash mismatch')
    with registry_guard(path):
        payload=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'observations':[]}
        rows=payload['observations']
        if any(r['region_id']==source['region_id'] and r['date']==source['date'] for r in rows):raise ValueError('Historical date already imported; evidence remains immutable')
        rows.append(source);_atomic_json(path,payload)
    return source
