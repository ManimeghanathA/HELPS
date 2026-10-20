"""Four-connected slope opportunities, separate from retained terrain."""
from contextlib import ExitStack
import hashlib
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.windows import from_bounds, Window
from rasterio.features import shapes
from shapely.geometry import shape
from shapely.ops import unary_union
from .contracts import THRESHOLDS, SourceAsset
from .sources import read_vector
from .characterization import geometry_features, raster_stats


def polygon_parts(geometry):
    if geometry.is_empty: return []
    if geometry.geom_type=='Polygon': return [geometry]
    if hasattr(geometry,'geoms'):
        return [p for child in geometry.geoms for p in polygon_parts(child)]
    return []


def exclusion_frames(sources,crs,parameters=None):
    parameters=parameters or {}; frames={}
    for name,source in (sources or {}).items():
        if source is None: continue
        frame=read_vector(source) if isinstance(source,SourceAsset) else source.copy()
        frame=frame.to_crs(crs)
        if name=='water':
            line_mask=frame.geom_type.isin(['LineString','MultiLineString'])
            if line_mask.any():
                frame.loc[line_mask,'geometry']=frame.loc[line_mask].geometry.buffer(float(parameters.get('water_line_buffer_m',5)))
        buffer_m=float(parameters.get(name+'_buffer_m',parameters.get('water_setback_m',0) if name=='water' else 0))
        if buffer_m>0: frame.geometry=frame.geometry.buffer(buffer_m)
        frames[name]=frame
    return frames


def local_exclusion(geometry,frames):
    geometries=[]
    for frame in frames.values():
        if frame.empty: continue
        indexes=frame.sindex.query(geometry,predicate='intersects')
        geometries.extend(frame.geometry.iloc[indexes])
    return unary_union(geometries) if geometries else None


def generate_slope_zones(terrain,assets,exclusion_sources,thresholds=THRESHOLDS,parameters=None):
    parameters=parameters or {}
    thresholds=tuple(float(t) for t in thresholds)
    if any(not np.isfinite(t) or t<0 or t>90 for t in thresholds) or len(set(thresholds))!=len(thresholds): raise ValueError('thresholds must be unique finite degree angles')
    parents=terrain.to_crs(assets.crs)
    exclusions=exclusion_frames(exclusion_sources,assets.crs,parameters)
    zones=[]; centres=[]; audit=[]
    gates={'area_m2':('min_area_m2',900,'area_below_minimum'),'width_m':('min_width_m',30,'width_below_minimum'),'length_m':('min_length_m',30,'length_below_minimum'),'max_clear_radius_m':('min_clear_radius_m',15,'clearance_below_minimum')}
    if 'min_clear_diameter_m' in parameters and 'min_clear_radius_m' not in parameters:
        parameters={**parameters,'min_clear_radius_m':float(parameters['min_clear_diameter_m'])/2}
    with ExitStack() as stack:
        slope=stack.enter_context(rasterio.open(assets.slope_path)); rough=stack.enter_context(rasterio.open(assets.roughness_path)); elevation=stack.enter_context(rasterio.open(assets.elevation_path)); support=stack.enter_context(rasterio.open(assets.valid_path))
        for _,parent in parents.iterrows():
            geom=parent.geometry; clipped=geom
            excluded=local_exclusion(geom,exclusions)
            if excluded is not None: clipped=geom.difference(excluded)
            raw=from_bounds(*geom.bounds,transform=slope.transform)
            c0=max(0,int(np.floor(raw.col_off))); r0=max(0,int(np.floor(raw.row_off)))
            c1=min(slope.width,int(np.ceil(raw.col_off+raw.width))); r1=min(slope.height,int(np.ceil(raw.row_off+raw.height)))
            has_window=c1>c0 and r1>r0
            if has_window:
                window=Window(c0,r0,c1-c0,r1-r0)
                values=slope.read(1,window=window,masked=True)
                supported=support.read(1,window=window)>0
                valid=supported&(~np.ma.getmaskarray(values))&np.isfinite(values.data)
                transform=slope.window_transform(window)
            for threshold in thresholds:
                base={'terrain_id':parent.terrain_id,'dataset_id':parent.dataset_id,'slope_threshold_deg':threshold}
                if not has_window:
                    audit.append({**base,'zone_id':None,'status':'no_child','reason':'no_valid_slope_cells'}); continue
                selected=valid&(values.data<=threshold+float(parameters.get('slope_tolerance_deg',1e-5)))
                fragments=[]
                if selected.any() and not clipped.is_empty:
                    for mapping,_ in shapes(selected.astype('uint8'),mask=selected,transform=transform,connectivity=4):
                        fragments.extend(polygon_parts(shape(mapping).intersection(clipped)))
                fragments.sort(key=lambda g:(g.bounds,hashlib.sha256(g.wkb).hexdigest()))
                kept=0
                for fragment in fragments:
                    if fragment.area<=0: continue
                    metrics=geometry_features(fragment,assets.crs,parameters.get('mic_tolerance_m',.5))
                    reasons=[reason for key,(parameter,default,reason) in gates.items() if metrics[key]+1e-8<float(parameters.get(parameter,default))]
                    zone_id=f"{parent.dataset_id}:{parent.terrain_id}:s{threshold:g}:{hashlib.sha256(fragment.wkb).hexdigest()[:16]}"
                    if reasons:
                        audit.append({**base,'zone_id':zone_id,'status':'rejected','reason':';'.join(reasons),'area_m2':fragment.area}); continue
                    record={**base,'zone_id':zone_id,'source_zone_id':parent.source_zone_id,**metrics,'geometry':fragment,'dem_valid_fraction':1.0,'dem_resolution_m':assets.resolution_m,'restriction_state':'unknown','obstacle_height_state':'unknown'}
                    for key,ds in [('slope',slope),('roughness',rough),('elevation',elevation)]:
                        stats=raster_stats(ds,fragment,assets.crs,total_area=fragment.area)
                        record[key+'_valid_fraction']=stats['valid_fraction']
                        record[key+'_sample_count']=stats['sample_count']
                        for agg in ('min','mean','max'): record[f'{agg}_{key}_{"deg" if key=="slope" else "m"}']=stats[agg]
                    record['dem_valid_fraction']=record['slope_valid_fraction']
                    record['evidence']={'slope':'measured','geometry':'derived','restrictions':'unknown','obstacle_height':'unknown'}
                    zones.append(record); kept+=1
                    from shapely.geometry import Point
                    centres.append({'zone_id':zone_id,'terrain_id':parent.terrain_id,'slope_threshold_deg':threshold,'max_clear_radius_m':metrics['max_clear_radius_m'],'geometry':Point(metrics['poi_easting'],metrics['poi_northing'])})
                    audit.append({**base,'zone_id':zone_id,'status':'accepted','reason':'measured_slope_and_geometry_gates','area_m2':fragment.area})
                if not kept and not fragments:
                    reason='fully_excluded' if clipped.is_empty else 'no_valid_slope_cells'
                    audit.append({**base,'zone_id':None,'status':'no_child','reason':reason})
    zone_columns=['zone_id','terrain_id','dataset_id','slope_threshold_deg','geometry']
    return (gpd.GeoDataFrame(zones if zones else {key:[] for key in zone_columns},geometry='geometry',crs=assets.crs),gpd.GeoDataFrame(centres if centres else {'zone_id':[],'geometry':[]},geometry='geometry',crs=assets.crs),pd.DataFrame(audit))
