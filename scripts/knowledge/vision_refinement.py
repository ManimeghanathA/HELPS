"""Strict geometry refinement from a pinned, indexed vision classification."""
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import Polygon
from .characterization import weighted_samples
from .repository import decode_geometry,_atomic_json
from .slope_zones import polygon_parts,local_exclusion
from .sources import file_sha256
from scripts.processing.candidate_geometry_filter import passes_geometry_gate
from scripts.processing.operational_zone_extraction import extract_operational_zones
from scripts.processing.maximum_clearance import measure_maximum_clearance


def strict_parts(geometry):
    if geometry is None or geometry.is_empty or not geometry.is_valid:return []
    result=[]
    for part in polygon_parts(geometry):
        if not passes_geometry_gate(part):continue
        for candidate in extract_operational_zones(part):
            if not candidate.is_valid or not passes_geometry_gate(candidate):continue
            if measure_maximum_clearance(candidate)['diameter_m']>=30:result.append(candidate)
    return sorted(result,key=lambda g:(g.bounds,hashlib.sha256(g.wkb).hexdigest()))


def contract_open_region(geometry,inward_m=5):
    if inward_m<0:raise ValueError('Inward contraction cannot be negative')
    if geometry is None or geometry.is_empty or not geometry.is_valid:return []
    return strict_parts(geometry.buffer(-inward_m))


def slope_qualification(geometry,slope,max_degrees=12):
    values,weights,valid=weighted_samples(slope,geometry,slope.crs)
    support=float(weights[valid].sum()/geometry.area) if geometry.area else 0
    maximum=float(values[valid].max()) if np.any(valid) else None
    passed=bool(support>=1-1e-8 and maximum is not None and maximum<=max_degrees)
    return {'passed':passed,'valid_fraction':min(1.0,support),'max_slope_deg':maximum,
            'reason':'pass' if passed else 'missing_slope_support' if support<1-1e-8 else 'slope_above_limit'}


class AcceptedIndex:
    """Dynamic accepted footprint index; prevents duplicate additions."""
    def __init__(self):
        self.db=sqlite3.connect(':memory:');self.db.execute('CREATE VIRTUAL TABLE accepted USING rtree(id,minx,maxx,miny,maxy)');self.geometries={}
    def add(self,geometry):
        key=len(self.geometries);self.geometries[key]=geometry;x0,y0,x1,y1=geometry.bounds
        self.db.execute('INSERT INTO accepted VALUES(?,?,?,?,?)',(key,x0,x1,y0,y1))
    def nearby(self,geometry):
        x0,y0,x1,y1=geometry.bounds
        return [self.geometries[r[0]] for r in self.db.execute('SELECT id FROM accepted WHERE minx<=? AND maxx>=? AND miny<=? AND maxy>=?',(x1,x0,y1,y0))]
    def subtract(self,geometry):
        nearby=self.nearby(geometry)
        return geometry.difference(shapely.union_all(nearby)) if nearby else geometry


class VisionStore:
    def __init__(self,path,expected_sha256):
        self.path=Path(path).resolve();self.sha256=file_sha256(self.path)
        if self.sha256!=expected_sha256:raise ValueError('Vision source checksum changed')
        self.db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.db.execute('PRAGMA query_only=ON')
        for table in ('open_regions','other_regions','bhadra_boundary'):
            record=self.db.execute('SELECT srs_id FROM gpkg_geometry_columns WHERE table_name=?',(table,)).fetchone()
            if not record or record[0]!=32643:raise ValueError('Vision layers must declare metric EPSG:32643')
        self.boundary=shapely.union_all([decode_geometry(r[0]) for r in self.db.execute('SELECT geom FROM bhadra_boundary')])
    def obstacles(self,geometry):
        x0,y0,x1,y1=geometry.bounds
        rows=self.db.execute('SELECT f.class_id,f.geom FROM rtree_other_regions_geom r JOIN other_regions f ON f.fid=r.id WHERE r.minx<=? AND r.maxx>=? AND r.miny<=? AND r.maxy>=?',(x1,x0,y1,y0))
        parts=[]
        for cls,blob in rows:
            if cls not in (1,2,5,6,7,8):raise ValueError('Unexpected class in vision obstacle layer')
            obstacle=decode_geometry(blob)
            if not obstacle.is_valid:raise ValueError('Invalid vision obstacle geometry; repair/review source first')
            if obstacle.intersects(geometry):parts.append(obstacle.intersection(geometry))
        return shapely.union_all(parts) if parts else Polygon()
    def open_regions(self):
        for fid,key,batch,cls,blob in self.db.execute('SELECT fid,feature_key,batch_id,class_id,geom FROM open_regions ORDER BY fid'):
            if cls not in (3,4):raise ValueError('Unexpected class in vision open layer')
            yield {'fid':fid,'feature_key':key,'batch_id':batch,'class_id':cls,'geometry':decode_geometry(blob)}


def prepare_seed(current,vision,slope,static_exclusions,output,max_slope_deg=12,log=print):
    """Subtract obstacles, then add contracted qualifying sites, preserving lineage."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if current.crs.to_epsg()!=32643 or slope.crs.to_epsg()!=32643:raise ValueError('Refinement inputs must use EPSG:32643')
    accepted=AcceptedIndex();records=[];counts=Counter();audit_path=output/'geometry-decisions.jsonl'
    def remove_static(geometry):
        mask=local_exclusion(geometry,static_exclusions)
        return geometry.difference(mask) if mask is not None else geometry
    def add(geometry,origin,source_key,parent=None,source_class=None,batch=None,slope_evidence=None):
        key=hashlib.sha256((origin+str(source_key)).encode()+geometry.wkb).hexdigest()[:16]
        identity=(str(parent)+'_CV_' if parent else 'Bhadra_CVNEW_')+key
        row={'source_zone_id':identity,'parent_terrain_id':parent,'refinement_origin':origin,'vision_feature_key':str(source_key),
             'vision_class_id':source_class,'vision_batch_id':batch,'vision_observation_date':None,'vision_date_status':'unknown',
             'geometry':geometry,'new_site_slope_limit_deg':max_slope_deg if origin=='vision_addition' else None}
        if slope_evidence:row.update(new_site_max_slope_deg=slope_evidence['max_slope_deg'],new_site_dem_valid_fraction=slope_evidence['valid_fraction'])
        records.append(row);accepted.add(geometry)
    with audit_path.open('w',encoding='utf-8') as audit:
        for i,parent in enumerate(current.itertuples()):
            geometry=parent.geometry.intersection(vision.boundary)
            if not geometry.is_empty:geometry=remove_static(geometry.difference(vision.obstacles(geometry)))
            geometry=accepted.subtract(geometry) if not geometry.is_empty else geometry
            pieces=strict_parts(geometry);counts['old_parents_seen']+=1
            counts['old_parents_removed']+=int(not pieces);counts['retained_refined_fragments']+=len(pieces)
            for part in pieces:add(part,'retained_refinement',parent.terrain_id,parent.terrain_id)
            audit.write(json.dumps({'parent_terrain_id':parent.terrain_id,'origin':'retained_refinement','accepted_fragments':len(pieces)})+'\n')
            if i%100==0:log(f'Vision obstacle subtraction: {i}/{len(current)} parents; {len(records)} qualifying fragments')
        for i,source in enumerate(vision.open_regions()):
            counts['open_regions_seen']+=1;geometry=source['geometry'];reason='contracted_geometry_rejected';kept=0
            if geometry.is_valid:
                contracted=geometry.buffer(-5).intersection(vision.boundary)
                for part in polygon_parts(contracted):
                    if not passes_geometry_gate(part):continue
                    evidence=slope_qualification(part,slope,max_slope_deg)
                    if not evidence['passed']:reason=evidence['reason'];continue
                    remaining=accepted.subtract(remove_static(part.difference(vision.obstacles(part))))
                    for qualified in strict_parts(remaining):
                        evidence=slope_qualification(qualified,slope,max_slope_deg)
                        if not evidence['passed']:reason=evidence['reason'];continue
                        if qualified.difference(contracted).area>1e-4:raise ValueError('New site escaped its 5 m contracted source')
                        add(qualified,'vision_addition',source['feature_key'] or source['fid'],source_class=source['class_id'],batch=source['batch_id'],slope_evidence=evidence);kept+=1
            else:reason='invalid_source_geometry'
            counts['new_added_fragments']+=kept
            if not kept:counts['open_rejected_'+reason]+=1
            audit.write(json.dumps({'vision_feature_key':source['feature_key'],'origin':'vision_addition','accepted_fragments':kept,'reason':'pass' if kept else reason})+'\n')
            if i%2000==0:log(f'Vision additions: {i} segmentations examined; {counts["new_added_fragments"]} new sites')
    if not records:raise ValueError('No candidates satisfy strict refinement gates')
    frame=gpd.GeoDataFrame(records,geometry='geometry',crs=32643)
    if frame.source_zone_id.duplicated().any():raise ValueError('Duplicate derived source IDs')
    for i,row in frame.iterrows():
        if not row.geometry.is_valid or row.geometry.intersection(vision.obstacles(row.geometry)).area>1e-4:raise ValueError('Refinement obstacle audit failed')
        if i%500==0:log(f'Final strict exclusion audit: {i}/{len(frame)}')
    path=output/'candidate_seed.gpkg';frame.to_file(path,layer='candidate_seed',driver='GPKG')
    gpd.GeoDataFrame({'vision_sha256':[vision.sha256],'imagery_date_status':['unknown']},geometry=[vision.boundary],crs=32643).to_file(path,layer='vision_extent',driver='GPKG')
    summary={'passed':True,'counts':dict(counts),'total_area_m2':float(frame.area.sum()),'vision_sha256':vision.sha256,'inward_contraction_m':5,'new_site_max_slope_deg':max_slope_deg,'all_other_classes_excluded':[1,2,5,6,7,8],
             'geometry_rules':{'min_area_m2':900,'min_width_m':30,'min_length_m':30,'neck_radius_m':15,'min_clear_diameter_m':30},'vision_acquisition_date':None,'date_status':'unknown; Sentinel context retains its original observation date'}
    _atomic_json(output/'refinement-audit.json',summary)
    return frame,path,summary
