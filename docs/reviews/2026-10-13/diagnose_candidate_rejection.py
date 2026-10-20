"""Measure experimental rejection stages against the preserved baseline; no threshold changes."""
import json
from pathlib import Path
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
experiment=Path((OUT/'latest-experiment-path.txt').read_text().strip())
base=gpd.read_file(OUT/'bhadra-baseline-236c34c.gpkg',layer='final_open_land_zones')
new=gpd.read_file(experiment/'final_zones.gpkg',layer='final_open_land_zones').to_crs(base.crs)
with rasterio.open(experiment/'archive/possible_open.tif') as src:
    state=src.read(1)
    labels=rasterize([(geom,index+1) for index,geom in enumerate(base.geometry)],
                     out_shape=state.shape,transform=src.transform,dtype='uint16')
with rasterio.open(experiment/'archive/screened_open.tif') as src:screened=src.read(1)
with rasterio.open(ROOT/'HELPS - draft/data/inputs/45295356fafbdae35c06ddec/2026-06-01/landcover/worldcover_2021_aligned.tif') as src:cover=src.read(1)
count=len(base)+1
total=np.bincount(labels.ravel(),minlength=count)
spectral=np.bincount(labels[state==1],minlength=count)
landcover=np.bincount(labels[screened==1],minlength=count)
unknown=np.bincount(labels[state==255],minlength=count)
trees=np.bincount(labels[cover==10],minlength=count)
built=np.bincount(labels[cover==50],minlength=count)
union=new.geometry.union_all()
rows=[]
for index,row in base.iterrows():
    i=index+1
    rows.append({'source_zone_id':row.zone_id,'baseline_area_m2':float(row.geometry.area),
                 'sampled_pixel_centres':int(total[i]),
                 'spectral_retained_centres':int(spectral[i]),
                 'landcover_retained_centres':int(landcover[i]),
                 'unknown_centres':int(unknown[i]),
                 'reference_2021_tree_centres':int(trees[i]),
                 'reference_2021_built_up_centres':int(built[i]),
                 'new_overlap_area_m2':float(row.geometry.intersection(union).area)})
summary={'baseline_candidates':len(base),'experimental_candidates':len(new),
         'baseline_pixel_centres':int(total[1:].sum()),
         'spectral_retained_centres':int(spectral[1:].sum()),
         'landcover_retained_centres':int(landcover[1:].sum()),
         'baseline_candidates_with_zero_spectral_pixels':int((spectral[1:]==0).sum()),
         'additional_candidates_zero_after_landcover':int(((spectral[1:]>0)&(landcover[1:]==0)).sum()),
         'baseline_candidates_with_any_new_overlap':sum(r['new_overlap_area_m2']>1e-4 for r in rows),
         'accuracy_measured':False,
         'interpretation':'Rejection accounting only; promising ground and physical obstacles require independent evidence.'}
(OUT/'candidate-rejection-diagnosis.json').write_text(json.dumps({'summary':summary,'candidates':rows},indent=2))
print(json.dumps(summary,indent=2))
