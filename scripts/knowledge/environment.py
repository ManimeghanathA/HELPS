"""Mapped surrounding occupancy/proximity with coverage and access uncertainty."""
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from contextlib import ExitStack
from shapely.ops import unary_union
from .contracts import SourceAsset
from .sources import read_vector
from .characterization import weighted_samples,surface_observation
from pyproj import Transformer
from shapely.ops import transform as transform_geometry


def context_frames(sources,crs):
    frames={}; coverage={}; provenance={}
    for name,source in sources.items():
        if isinstance(source,SourceAsset):
            if source.kind in ('raster','dem','spectral','scl','landcover') or source.path.suffix.lower() in ('.tif','.tiff'): continue
            frame=read_vector(source).to_crs(crs)
            coverage_geometry=read_vector(SourceAsset('coverage',source.coverage_path)).to_crs(crs).geometry.union_all() if source.coverage_path else None
            coverage[name]=(source.coverage_state,coverage_geometry)
            provenance[name]={'source_id':source.source_id,'date':source.date,'coverage_state':source.coverage_state}
        elif isinstance(source,gpd.GeoDataFrame):
            frame=source.to_crs(crs)
            coverage[name]=(source.attrs.get('coverage_state','unknown'),source.attrs.get('coverage_geometry'))
            provenance[name]={'source_id':name,'date':None,'coverage_state':coverage[name][0]}
        else: continue
        frames[name]=frame
    return frames,coverage,provenance


def coverage_fraction(name,geometry,coverage):
    state,extent=coverage.get(name,('unknown',None))
    if extent is None: return None
    return min(1,float(geometry.intersection(extent).area/geometry.area)) if geometry.area else None


def nearest(frame,geometry):
    if frame is None or frame.empty: return None,None
    indexes=frame.sindex.nearest(geometry,return_all=False)[1]
    index=int(indexes[0]); row=frame.iloc[index]
    return float(geometry.distance(row.geometry)),row


def _road_components(frame):
    if frame is None or frame.empty: return {},{}
    parents=list(range(len(frame)))
    def find(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]]; i=parents[i]
        return i
    pairs=frame.sindex.query(frame.geometry,predicate='intersects')
    for left,right in zip(*pairs):
        a,b=find(int(left)),find(int(right))
        if a!=b: parents[b]=a
    membership={frame.index[i]:find(i) for i in range(len(frame))}
    counts={}
    for component in membership.values(): counts[component]=counts.get(component,0)+1
    return membership,counts


def characterize_environment(zones,sources,analysis_radius_m=200.0):
    with ExitStack() as stack:
        rasters={key:(stack.enter_context(rasterio.open(source.path)),source) for key,source in sources.items() if key in ('scl','landcover','worldcover') and isinstance(source,SourceAsset)}
        return _characterize_environment(zones,sources,analysis_radius_m,rasters)


def _characterize_environment(zones,sources,analysis_radius_m,raster_context):
    if not np.isfinite(analysis_radius_m) or analysis_radius_m<=0: raise ValueError('analysis radius must be finite positive metres')
    if zones.crs is None or not zones.crs.is_projected or not all(abs(a.unit_conversion_factor-1)<1e-8 for a in zones.crs.axis_info[:2]): raise ValueError('environment requires metric zones')
    frames,coverage,provenance=context_frames(sources,zones.crs); records=[]
    road_membership,road_counts=_road_components(frames.get('roads'))
    cached={}
    obstacle_names=('buildings','osm_buildings','obstacles','vegetation','power','man_made','barriers')
    for _,zone in zones.iterrows():
        geometry=zone.geometry; surrounding=geometry.buffer(analysis_radius_m)
        cache_key=geometry.wkb
        if cache_key in cached:
            records.append({**cached[cache_key],'zone_id':zone.zone_id,'terrain_id':zone.terrain_id}); continue
        record={'zone_id':zone.zone_id,'terrain_id':zone.terrain_id,'analysis_radius_m':analysis_radius_m,'context_sources':provenance,'obstacle_height_state':'unknown','approach_corridor_state':'unknown','road_access_state':'unknown','road_connectivity_state':'unknown','restriction_state':'unknown'}
        for name in ('roads','water','hospitals','settlements','infrastructure'):
            frame=frames.get(name); distance,closest=nearest(frame,geometry)
            prefix={'roads':'road','hospitals':'hospital','settlements':'settlement'}.get(name,name)
            record[prefix+'_distance_m']=distance
            fraction=coverage_fraction(name,surrounding,coverage)
            record[prefix+'_coverage_fraction']=fraction
            complete=coverage.get(name,('unknown',None))[0]=='verified' and fraction is not None and fraction>=1-1e-8
            record[prefix+'_state']='measured_mapped_proximity' if closest is not None else ('verified_no_mapped_features' if frame is not None and complete else 'unknown')
            if name=='roads' and closest is not None:
                record['road_mapped_component_count']=len(road_counts)
                record['road_nearest_component_segment_count']=road_counts.get(road_membership.get(closest.name))
                record['road_connectivity_state']='derived_mapped_graph'
                tags={key:closest.get(key) for key in ('highway','access','motor_vehicle','surface','bridge') if key in closest and pd.notna(closest.get(key))}
                record['road_tags']=tags
                if 'access' in tags or 'motor_vehicle' in tags:
                    record['road_access_state']='mapped_tag'; record['road_access']=tags.get('access',tags.get('motor_vehicle'))
            if name=='water':
                hits=frame.sindex.query(geometry,predicate='intersects') if frame is not None and not frame.empty else []
                water_union=unary_union(frame.geometry.iloc[hits]) if len(hits) else None
                record['water_intersection_fraction']=float(geometry.intersection(water_union).area/geometry.area) if water_union is not None else (0.0 if complete else None)
        obstacle_geometries=[]; counts={}; obstacle_coverage=[]
        present=False
        for name in obstacle_names:
            frame=frames.get(name)
            if frame is None: continue
            present=True
            indexes=frame.sindex.query(surrounding,predicate='intersects') if not frame.empty else []
            counts[name]=len(indexes)
            obstacle_geometries.extend(frame.geometry.iloc[indexes])
            fraction=coverage_fraction(name,surrounding,coverage)
            obstacle_coverage.append((coverage.get(name,('unknown',None))[0],fraction))
        occupied=unary_union(obstacle_geometries).intersection(surrounding).area if obstacle_geometries else 0
        record['mapped_obstacle_count']=sum(counts.values()) if present else None
        record['mapped_obstacle_counts']=counts
        record['mapped_obstacle_fraction']=min(1,float(occupied/surrounding.area)) if present else None
        record['openness_score']=1-record['mapped_obstacle_fraction'] if present else None
        verified=bool(obstacle_coverage) and all(state=='verified' and fraction is not None and fraction>=1-1e-8 for state,fraction in obstacle_coverage)
        record['context_coverage_state']='verified' if verified else 'unknown'
        record['openness_state']='derived_mapped_2d' if present else 'unknown'
        record['openness_method']='1 minus union of mapped obstacle footprints / 200m zone buffer area'
        surface_observations={}
        for name,(dataset,source) in raster_context.items():
            vals,weights,valid=weighted_samples(dataset,surrounding,zones.crs)
            raster_geom=transform_geometry(Transformer.from_crs(zones.crs,dataset.crs,always_xy=True).transform,surrounding)
            total=raster_geom.area
            observation=surface_observation(vals,weights,valid,total,source,name)
            fractions=observation['class_fractions'];valid_fraction=observation['observable_fraction']
            vegetation_classes=(4,) if name=='scl' else (10,20,30,40,90,95,100)
            vegetation_fraction=sum(fractions.get(str(k),0) for k in vegetation_classes)
            surface_observations[name]={**observation,'vegetation_fraction':vegetation_fraction if valid_fraction else None}
        record['context_surface_observations']=surface_observations
        primary=surface_observations.get('scl',surface_observations.get('landcover',surface_observations.get('worldcover',{})))
        record['context_vegetation_fraction']=primary.get('vegetation_fraction')
        record['context_cover_valid_fraction']=primary.get('observable_fraction',0)
        record['context_cover_date']=primary.get('date')
        record['context_vegetation_height_state']='unknown'
        restrictions=frames.get('restrictions',frames.get('restriction'))
        restriction_key='restrictions' if 'restrictions' in frames else 'restriction'
        if restrictions is not None:
            fraction=coverage_fraction(restriction_key,geometry,coverage)
            hits=restrictions.sindex.query(geometry,predicate='intersects') if not restrictions.empty else []
            overlap=unary_union(restrictions.geometry.iloc[hits]).intersection(geometry).area if len(hits) else 0
            record['restriction_intersection_fraction']=float(overlap/geometry.area)
            record['restriction_coverage_fraction']=fraction
            if overlap>0: record['restriction_state']='restricted_mapped'
            elif coverage.get(restriction_key,('unknown',None))[0]=='verified' and fraction is not None and fraction>=1-1e-8: record['restriction_state']='verified_clear'
        record['evidence']={'road':record['road_state'],'water':record['water_state'],'openness':record['openness_state'],'restrictions':record['restriction_state'],'obstacle_height':'unknown'}
        cached[cache_key]=record.copy()
        records.append(record)
    return pd.DataFrame(records,columns=None if records else ['zone_id','terrain_id'])
