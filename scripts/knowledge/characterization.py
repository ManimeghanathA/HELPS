"""Area-weighted raster observations; spectral indicators are not firmness."""
from contextlib import ExitStack
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds, Window
import shapely
from pyproj import Transformer
from shapely.ops import transform as transform_geometry
from scripts.processing.candidate_geometry_filter import measure_candidate_geometry


def weighted_samples(dataset, geometry, geometry_crs, band=1):
    """Return intersecting cell values, square-unit overlap weights and masks.

    Cell intersections rather than centers preserve support for tiny polygons.
    Weight CRS is the raster CRS; callers use local metric rasters for metric
    area and native observations for dimensionless coverage fractions.
    """
    if str(geometry_crs)!=str(dataset.crs):
        transformer=Transformer.from_crs(geometry_crs,dataset.crs,always_xy=True)
        geometry=transform_geometry(transformer.transform,geometry)
    if geometry.is_empty: return np.array([]),np.array([]),np.array([],bool)
    if dataset.transform.b or dataset.transform.d: raise ValueError('rotated raster sampling requires a rectified grid')
    raw=from_bounds(*geometry.bounds,transform=dataset.transform)
    left=max(0,int(np.floor(raw.col_off))); top=max(0,int(np.floor(raw.row_off)))
    right=min(dataset.width,int(np.ceil(raw.col_off+raw.width))); bottom=min(dataset.height,int(np.ceil(raw.row_off+raw.height)))
    if right<=left or bottom<=top: return np.array([]),np.array([]),np.array([],bool)
    window=Window(left,top,right-left,bottom-top)
    array=dataset.read(band,window=window,masked=True)
    rows,cols=np.indices(array.shape); rows=rows.ravel()+top; cols=cols.ravel()+left
    tr=dataset.transform
    x0=tr.c+cols*tr.a; y0=tr.f+rows*tr.e
    cells=shapely.box(np.minimum(x0,x0+tr.a),np.minimum(y0,y0+tr.e),np.maximum(x0,x0+tr.a),np.maximum(y0,y0+tr.e))
    # Exact area weighting: interior cells need no polygon overlay. Prepared
    # predicates limit expensive intersection operations to boundary cells.
    shapely.prepare(geometry)
    interior=shapely.contains(geometry,cells)
    weights=np.zeros(len(cells),dtype='float64')
    weights[interior]=abs(tr.a*tr.e)
    boundary=(~interior)&shapely.intersects(geometry,cells)
    weights[boundary]=shapely.area(shapely.intersection(cells[boundary],geometry))
    selected=weights>0
    values=array.data.ravel()[selected]
    valid=(~np.ma.getmaskarray(array).ravel()[selected])&np.isfinite(values)
    return values,weights[selected],valid


def surface_observation(values,weights,valid,total,source,label):
    fractions={str(int(value)):float(weights[valid&(values==value)].sum()/total) for value in np.unique(values[valid])} if total else {}
    observed=valid&np.isin(values,[4,5,6]) if label=='scl' else valid&(values!=0)
    raw_support=min(1,float(weights[valid].sum()/total)) if total else 0
    support=min(1,float(weights[observed].sum()/total)) if total else 0
    return {'source_id':source.source_id,'date':source.date,'class_fractions':fractions,'valid_fraction':raw_support,'raw_unknown_fraction':1-raw_support,'observable_fraction':support,'unknown_fraction':1-support,'state':'measured' if support else 'unknown','sample_count':int(observed.sum())}


def raster_stats(dataset,geometry,crs,band=1,total_area=None):
    values,weights,valid=weighted_samples(dataset,geometry,crs,band)
    if total_area is None:
        if str(crs)!=str(dataset.crs):
            geometry=transform_geometry(Transformer.from_crs(crs,dataset.crs,always_xy=True).transform,geometry)
        total_area=geometry.area
    supported=float(weights[valid].sum())
    fraction=min(1.0,supported/total_area) if total_area else 0.0
    return {'min':float(values[valid].min()) if valid.any() else None,'mean':float(np.average(values[valid],weights=weights[valid])) if valid.any() else None,'max':float(values[valid].max()) if valid.any() else None,'std':float(np.sqrt(np.average((values[valid]-np.average(values[valid],weights=weights[valid]))**2,weights=weights[valid]))) if valid.any() else None,'valid_fraction':fraction,'sample_count':int(valid.sum()),'supported_area':supported,'state':'measured' if valid.any() else 'unknown'}


def geometry_features(geometry,crs,tolerance_m=.5):
    metrics=measure_candidate_geometry(geometry)
    # GEOS implements the same bounded-tolerance search without the Python
    # priority queue. Compute the actual full-boundary distance, including holes.
    line=shapely.maximum_inscribed_circle(geometry,tolerance=tolerance_m)
    center=shapely.Point(line.coords[0])
    radius=float(center.distance(geometry.boundary))
    lon,lat=Transformer.from_crs(crs,4326,always_xy=True).transform(center.x,center.y)
    return {**metrics,'max_clear_radius_m':radius,'max_clear_diameter_m':radius*2,'poi_easting':center.x,'poi_northing':center.y,'longitude':lon,'latitude':lat,'bounds':list(geometry.bounds)}


def characterize_terrain(terrain,assets,sources,parameters):
    from .environment import context_frames,nearest
    terrain_metric=terrain.to_crs(assets.crs); records=[]
    context_sources={key:source for key,source in sources.items() if key in ('roads','water')}
    frames,context_coverage,provenance=context_frames(context_sources,assets.crs)
    with ExitStack() as stack:
        rasters={key:stack.enter_context(rasterio.open(path)) for key,path in [('elevation',assets.elevation_path),('slope',assets.slope_path),('roughness',assets.roughness_path)]}
        evidence={key:stack.enter_context(rasterio.open(asset.path)) for key,asset in sources.items() if key in ('scl','landcover','worldcover','spectral')}
        for _,parent in terrain_metric.iterrows():
            geom=parent.geometry
            record={'terrain_id':parent.terrain_id,'source_zone_id':parent.source_zone_id,'dataset_id':parent.dataset_id,**geometry_features(geom,assets.crs,parameters.get('mic_tolerance_m',.5))}
            record['mapped_context_sources']=provenance
            record['road_access_state']='unknown'
            record['road_access']=None
            record['road_tags']={}
            for source_name,prefix in (('roads','road'),('water','water')):
                distance,closest=nearest(frames.get(source_name),geom)
                record[prefix+'_distance_m']=distance
                record[prefix+'_coverage_state']=context_coverage.get(source_name,('unknown',None))[0]
                record[prefix+'_state']='measured_mapped_proximity' if closest is not None else 'unknown'
                if source_name=='roads' and closest is not None:
                    tags={key:closest.get(key) for key in ('highway','access','motor_vehicle','surface','bridge') if key in closest and pd.notna(closest.get(key))}
                    record['road_tags']=tags
                    if 'access' in tags or 'motor_vehicle' in tags:
                        record['road_access_state']='mapped_tag'
                        record['road_access']=tags.get('access',tags.get('motor_vehicle'))
            for key,ds in rasters.items():
                stats=raster_stats(ds,geom,assets.crs,total_area=geom.area)
                unit='deg' if key=='slope' else 'm'
                for agg in ('min','mean','max','std'): record[f'{agg}_{key}_{unit}']=stats[agg]
                record[key+'_state']=stats['state']; record[key+'_valid_fraction']=stats['valid_fraction']; record[key+'_sample_count']=stats['sample_count']
            record['dem_valid_fraction']=record['slope_valid_fraction']; record['elevation_valid_fraction']=record['elevation_valid_fraction']; record['dem_sample_count']=record['slope_sample_count']; record['dem_resolution_m']=assets.resolution_m
            record['dem_source_id']=assets.manifest.get('source_id'); record['dem_source_date']=assets.manifest.get('source_date')
            observations={}
            for key,ds in evidence.items():
                if key=='spectral': continue
                vals,weights,valid=weighted_samples(ds,geom,assets.crs)
                raster_geom=transform_geometry(Transformer.from_crs(assets.crs,ds.crs,always_xy=True).transform,geom)
                total=raster_geom.area
                observations[key]=surface_observation(vals,weights,valid,total,sources[key],key)
            record['surface_observations']=observations; record['surface_state']='measured' if any(o['observable_fraction']>0 for o in observations.values()) else 'unknown'
            record['ground_firmness_state']='unknown'; record['ground_firmness']=None
            scl=observations.get('scl',{}); classes=scl.get('class_fractions',{})
            record['vegetation_fraction']=classes.get('4',0.0) if scl.get('observable_fraction',0)>0 else None
            record['water_fraction']=classes.get('6',0.0) if scl.get('observable_fraction',0)>0 else None
            record['bare_surface_fraction']=classes.get('5',0.0) if scl.get('observable_fraction',0)>0 else None
            record['surface_observable_fraction']=scl.get('observable_fraction',0)
            record['surface_evidence_date']=scl.get('date')
            record['ndvi_mean']=None; record['ndvi_valid_fraction']=0.0
            if 'spectral' in evidence:
                ds=evidence['spectral']; band_map=sources['spectral'].metadata.get('band_map',{})
                red=int(band_map.get('red',3)); nir=int(band_map.get('nir',4))
                r,w,rv=weighted_samples(ds,geom,assets.crs,red); n,nw,nv=weighted_samples(ds,geom,assets.crs,nir)
                if len(r)==len(n):
                    r=r.astype('float64'); n=n.astype('float64')
                    valid=rv&nv&((n+r)!=0)
                    record['ndvi_raw_mean']=float(np.average((n[valid]-r[valid])/(n[valid]+r[valid]),weights=w[valid])) if valid.any() else None
                    record['ndvi_observability_state']='unknown_without_scl'
                    if 'scl' in evidence:
                        scl_ds=evidence['scl']
                        if (ds.crs,ds.transform,ds.width,ds.height)!=(scl_ds.crs,scl_ds.transform,scl_ds.width,scl_ds.height):raise ValueError('spectral/SCL grids differ')
                        sv,sw,sm=weighted_samples(scl_ds,geom,assets.crs)
                        valid&=sm&np.isin(sv,[4,5,6])
                        record['ndvi_observability_state']='scl_ground_observability'
                    if valid.any():
                        record['ndvi_mean']=float(np.average((n[valid]-r[valid])/(n[valid]+r[valid]),weights=w[valid]))
                        total=transform_geometry(Transformer.from_crs(assets.crs,ds.crs,always_xy=True).transform,geom).area
                        record['ndvi_valid_fraction']=min(1,float(w[valid].sum()/total))
                record['ndvi_source_date']=sources['spectral'].date
            record['evidence']={'dem':record['slope_state'],'surface':record['surface_state'],'ground_firmness':'unknown','obstacle_height':'unknown'}
            records.append(record)
    return pd.DataFrame(records)
