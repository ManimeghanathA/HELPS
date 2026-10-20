"""Reproducible full-AOI experiment; preserves canonical data and declares missing sources."""
import json,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
DRAFT=ROOT/'HELPS - draft'
sys.path.insert(0,str(DRAFT/'.review-deps'));sys.path.insert(0,str(DRAFT))
import geopandas as gpd
import pandas as pd
import fiona
from scripts.pipeline.inputs import load_aoi,legacy_inputs
from scripts.pipeline.processing import process_inputs
from scripts.pipeline.acquisition import digest,write_json
from scripts.pipeline.landcover import acquire_worldcover

output=DRAFT/'data/experiments'/('bhadra_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:6])
output.mkdir(parents=True)
(ROOT/'docs/reviews/2026-10-13/latest-experiment-path.txt').write_text(str(output))
def log(message):
    with (output/'run.log').open('a',encoding='utf-8') as f:f.write(str(message)+'\n')
    print(message,flush=True)
status={'status':'experimental_running','name':'Bhadra','date':'2026-06-01',
        'accuracy_measured':False,'landing_safety_certified':False}
write_json(output/'run.json',status)
try:
    aoi=load_aoi(DRAFT/'data/raw/Bhadra/bhadra_entire_region.geojson')
    paths=legacy_inputs(aoi,'2026-06-01')
    building_frames=[gpd.read_file(paths['osm'],layer='buildings')[['geometry']].to_crs(4326),
                     gpd.read_file(paths['overture'])[['geometry']].to_crs(4326)]
    buildings=gpd.GeoDataFrame(pd.concat(building_frames,ignore_index=True),crs=4326)
    exclusions={'water':gpd.read_file(paths['osm'],layer='water_polygons')[['geometry']].to_crs(4326)}
    fresh=DRAFT/'data/inputs/45295356fafbdae35c06ddec/2026-06-01/fresh_exclusions.gpkg'
    exclusion_sources=[]
    if fresh.exists():
        layers=fiona.listlayers(fresh)
        for layer in ['industrial','facilities']:
            if layer in layers:
                exclusions[layer]=gpd.read_file(fresh,layer=layer)[['geometry']].to_crs(4326)
                exclusion_sources.append({'path':str(fresh),'sha256':digest(fresh),'layer':layer})
    reviews=[]
    for path in (DRAFT/'data/raw').glob('*/reviewed_exclusions.geojson'):
        frame=gpd.read_file(path).to_crs(4326)
        frame=frame[frame.intersects(aoi.geometry.union_all())]
        if len(frame):
            reviews.append(frame[['geometry']])
            snapshot=output/'source_snapshots'/path.parent.name/'reviewed_exclusions.geojson'
            snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_bytes(path.read_bytes())
            exclusion_sources.append({'path':str(path),'sha256':digest(path),
                                      'snapshot':str(snapshot),'selected_features':len(frame)})
    if reviews:exclusions['reviewed']=gpd.GeoDataFrame(pd.concat(reviews,ignore_index=True),crs=4326)
    cover,cover_info=acquire_worldcover(paths['spectral'],DRAFT/'data/inputs/45295356fafbdae35c06ddec/2026-06-01/landcover',log)
    provenance={key:{'path':str(path),'sha256':digest(path)} for key,path in paths.items()}
    provenance['landcover']=cover_info
    provenance['exclusion_sources']=exclusion_sources
    provenance['water_note']='Legacy mapped water polygons; line and date completeness unverified.'
    log(f'EXPERIMENT ONLY; missing groups: {sorted({"industrial","facilities"}-set(exclusions))}')
    summary=process_inputs(paths['spectral'],paths['scl'],buildings,exclusions,aoi,output,
                          'BhadraExp',log,screening_profile='conservative',landcover_path=cover,experimental=True)
    status.update(status='experimental_complete',summary=summary,provenance=provenance)
    log(f'Experimental output: {output}')
except Exception as exc:
    status.update(status='failed',error=str(exc));log(f'FAILED: {exc}');raise
finally:
    write_json(output/'run.json',status)
