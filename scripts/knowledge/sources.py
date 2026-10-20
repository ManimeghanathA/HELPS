"""Read-only source verification and retained topology import."""
import hashlib
import json
from pathlib import Path
import numpy as np
import geopandas as gpd
import rasterio
from pyproj import CRS
from .contracts import json_safe

RASTER_KINDS = {'raster','dem','spectral','scl','landcover'}

def file_sha256(path):
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()

def read_vector(asset):
    frame=gpd.read_file(asset.path,layer=asset.layer) if asset.layer else gpd.read_file(asset.path)
    if frame.crs is None: raise ValueError(f'{asset.source_id}: missing CRS')
    if any(g is None or g.is_empty or not g.is_valid or not np.isfinite(g.bounds).all() for g in frame.geometry):
        raise ValueError(f'{asset.source_id}: invalid geometry or coordinates')
    if 'attributes' in frame:
        for index,value in frame['attributes'].items():
            if not isinstance(value,(str,dict)):continue
            try:attributes=json.loads(value) if isinstance(value,str) else value
            except ValueError:raise ValueError(f'{asset.source_id}: invalid attributes JSON') from None
            if not isinstance(attributes,dict):raise ValueError(f'{asset.source_id}: attributes must be an object')
            # Regional extracts retain the original tag map; Overpass/OSMnx
            # stores flat attributes. Expose both through the same contract.
            if isinstance(attributes.get('tags'),dict):attributes={**attributes['tags'],**attributes}
            for key,tag in attributes.items():
                if key=='geometry':continue
                if key not in frame:frame[key]=None
                existing=frame.at[index,key]
                if existing is None or (isinstance(existing,float) and np.isnan(existing)):
                    frame.at[index,key]=json.dumps(tag) if isinstance(tag,(list,dict)) else tag
    # Keep legacy closed-way facility exports consistent with their area tags.
    # This also ensures proximity/density features use the footprint interior,
    # rather than only its outline. Explicit area=no and linear infrastructure
    # (power lines/pipelines) retain their original geometry.
    area_tags={'power':{'plant','substation','generator'},
               'man_made':{'water_works','wastewater_plant','works','storage_tank','reservoir_covered','water_tower'}}
    for index,geometry in frame.geometry.items():
        if geometry.geom_type!='LineString' or not geometry.is_ring:continue
        row=frame.loc[index]
        if row.get('area')=='no':continue
        if any(isinstance(row.get(key),str) and row[key] in values for key,values in area_tags.items()):
            from shapely.geometry import Polygon
            frame.at[index,'geometry']=Polygon(geometry.coords)
    return frame

def inspect_source(asset):
    if not asset.path.is_file(): raise ValueError(f'{asset.source_id}: missing file {asset.path}')
    digest=file_sha256(asset.path)
    if asset.sha256 and digest.lower()!=asset.sha256.lower(): raise ValueError(f'{asset.source_id}: hash mismatch')
    record={'source_id':asset.source_id,'path':str(asset.path.resolve()),'sha256':digest,'date':asset.date,'kind':asset.kind,'units':asset.units,'coverage_state':asset.coverage_state,'metadata':asset.metadata,'layer':asset.layer}
    if asset.kind in RASTER_KINDS or asset.path.suffix.lower() in ('.tif','.tiff'):
        with rasterio.open(asset.path) as ds:
            if ds.crs is None: raise ValueError(f'{asset.source_id}: missing CRS')
            if ds.count<1 or ds.width<1 or ds.height<1: raise ValueError(f'{asset.source_id}: empty raster')
            record.update(crs=ds.crs.to_string(),bounds=list(ds.bounds),resolution=list(ds.res),nodata=ds.nodata,bands=ds.count,dtype=ds.dtypes[0],width=ds.width,height=ds.height,transform=list(ds.transform),tags=ds.tags())
    else:
        frame=read_vector(asset)
        record.update(crs=frame.crs.to_string(),bounds=list(frame.total_bounds),count=len(frame),fields=list(frame.columns))
    if asset.crs and CRS.from_user_input(asset.crs)!=CRS.from_user_input(record['crs']): raise ValueError(f'{asset.source_id}: declared CRS mismatch')
    if asset.coverage_path:
        coverage=read_vector(type(asset)('coverage',asset.coverage_path))
        record['coverage_path']=str(asset.coverage_path.resolve())
        record['coverage_sha256']=file_sha256(asset.coverage_path)
    return json_safe(record)

def validate_build_spec(spec):
    errors=[]; records={}
    if spec.source_mode not in ('retained','new'): errors.append('unknown source_mode')
    if spec.source_mode=='new':
        required={'spectral','scl','water','industrial','facilities'}
        absent=required-set(spec.sources)
        if absent: errors.append(f'new candidate generation missing required sources {sorted(absent)}')
        if not {'buildings','osm_buildings'}&set(spec.sources): errors.append('new candidate generation requires buildings evidence')
    if spec.dem.units not in ('m','metre','meter','ft','feet','foot'):
        errors.append('DEM vertical units must be declared metres or feet')
    assets={'aoi':spec.aoi,'dem':spec.dem,**spec.sources}
    if spec.source_mode=='retained': assets['retained_seed']=spec.retained_seed
    if spec.reviewed_exclusions: assets['reviewed_exclusions']=spec.reviewed_exclusions
    for key,asset in assets.items():
        try: records[key]=inspect_source(asset)
        except Exception as exc: errors.append(str(exc))
    if 'spectral' in records and 'scl' in records:
        spectral,scl=records['spectral'],records['scl']
        if any(spectral.get(k)!=scl.get(k) for k in ('crs','width','height','transform')): errors.append('spectral/SCL grids do not match')
        if spectral['bands']<4: errors.append('spectral requires declared blue, green, red and NIR bands')
    if 'spectral' in records:
        band_map=spec.sources['spectral'].metadata.get('band_map',{})
        if any(key not in band_map for key in ('blue','green','red','nir')):
            errors.append('spectral band_map must declare blue, green, red and nir band numbers')
        elif any(not isinstance(index,int) or index<1 or index>records['spectral']['bands'] for index in band_map.values()):
            errors.append('spectral declared band number outside available raster bands')
        if spec.source_mode=='new' and (records['spectral']['bands']<6 or any(band_map.get(key)!=number for key,number in {'blue':1,'green':2,'red':3,'nir':4}.items())):
            errors.append('new classification requires six Sentinel bands ordered blue, green, red, NIR, SWIR1, SWIR2; supplied band mapping is incompatible')
    completeness={key:(asset.coverage_state if asset else 'unknown') for key,asset in [('restrictions',spec.sources.get('restrictions') or spec.sources.get('restriction')),('roads',spec.sources.get('roads')),('water',spec.sources.get('water')),('buildings',spec.sources.get('buildings'))]}
    if 'retained_seed' in records:
        try: load_retained_terrain(spec)
        except Exception as exc: errors.append(str(exc))
    return {'valid':not errors,'errors':errors,'sources':records,'completeness':completeness}

def load_retained_terrain(spec):
    frame=read_vector(spec.retained_seed).copy()
    if not all(frame.geom_type.isin(['Polygon','MultiPolygon'])): raise ValueError('candidate seed requires polygon geometry')
    id_key=next((k for k in ('source_zone_id','zone_id','terrain_id') if k in frame),None)
    if id_key is None: raise ValueError('candidate seed requires source_zone_id or zone_id')
    if frame[id_key].isna().any(): raise ValueError('source IDs must be nonnull and unique')
    ids=frame[id_key].astype(str)
    if ids.duplicated().any(): raise ValueError('source IDs must be unique')
    frame['source_zone_id']=ids; frame['terrain_id']=ids; frame['dataset_id']=spec.dataset_id
    frame['source_geometry_sha256']=[hashlib.sha256(g.wkb).hexdigest() for g in frame.geometry]
    if spec.reviewed_exclusions:
        review=read_vector(spec.reviewed_exclusions)
        if 'source_zone_id' not in review: raise ValueError('reviewed exclusions require source_zone_id')
        mask=review['status'].isin(['quarantined','excluded']) if 'status' in review else np.ones(len(review),bool)
        excluded=set(review.loc[mask,'source_zone_id'].astype(str))
        missing=excluded-set(ids)
        if missing: raise ValueError(f'reviewed IDs absent from seed: {sorted(missing)}')
        frame=frame.loc[~frame.source_zone_id.isin(excluded)].copy()
    return frame.reset_index(drop=True)
