"""CLI and UI entry point for validated single-date processing."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd

from scripts.pipeline.acquisition import write_json, digest
from scripts.pipeline.region_inputs import resolve_region_inputs
from scripts.pipeline.inputs import ROOT, load_aoi, cache_key, data_directory
from scripts.pipeline.processing import process_inputs

# CHANGED: these OSM layers get subtracted as exclusions (in addition to buildings).
# 'water' catches natural=water / waterway=* (rivers, canals, drains, ponds).
# 'industrial' catches landuse=industrial/construction/quarry/landfill/farmyard.
# Both are acquired into osm.gpkg by scripts/pipeline/acquisition.py but were
# previously never read back out.
EXCLUSION_LAYERS = ['water', 'industrial', 'facilities']


def _read_osm_layer(path, layer, log):
    """Required exclusions must be readable; an absent layer is not evidence of absence."""
    try:
        frame = gpd.read_file(path, layer=layer)
    except Exception as exc:
        raise ValueError(f'Required OSM exclusion layer {layer!r} cannot be read; reacquire inputs.') from exc
    if frame.crs is None:
        raise ValueError(f'{layer} layer has no CRS.')
    return frame[['geometry']].to_crs(4326)


def promote_to_canonical(run_output: Path, name: str, date: str, log=print) -> Path:
    """
    Copy freshly generated run GPKG to the canonical processed dataset location
    read by LandingZoneEngine._load_datasets().
    """
    run_gpkg = run_output / 'final_zones.gpkg'
    if not run_gpkg.exists():
        raise FileNotFoundError(f'Run GPKG not found at {run_gpkg}')
    summary = json.loads((run_output/'summary.json').read_text())
    if (summary.get('experimental') is True or summary.get('sources_complete') is not True
            or summary.get('audits',{}).get('passed') is not True):
        raise ValueError('Only complete-source, audited results can be promoted.')
    canonical_dir = ROOT / 'data/processed' / name / 'sentinel2' / date
    canonical_dir.mkdir(parents=True, exist_ok=True)
    canonical_gpkg = canonical_dir / f'{name.lower()}_final_open_land_zones.gpkg'
    temp_gpkg = canonical_gpkg.with_name(canonical_gpkg.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with open(run_gpkg, 'rb') as fsrc, open(temp_gpkg, 'wb') as fdst:
            shutil.copyfileobj(fsrc, fdst)
        temp_gpkg.replace(canonical_gpkg)
    finally:
        temp_gpkg.unlink(missing_ok=True)
    log(f'Promoted {run_gpkg} -> {canonical_gpkg}')
    return canonical_gpkg


def run(aoi_path, date, name='AOI', log=print, run_tests=True, screening_profile='neha-236c34c'):
    aoi = load_aoi(aoi_path)
    key = cache_key(aoi, date)
    name = re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_')[:60] or 'AOI'
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]
    output = ROOT/'data/runs'/run_id
    data_directory(output)
    status = {'id':run_id,'name':name,'date':date,'aoi_key':key,'status':'running','review_required':True,'review_decision':'pending',
              'screening_profile': screening_profile}
    write_json(output/'run.json', status)
    aoi.to_file(output/'aoi.geojson', driver='GeoJSON')
    def record(message):
        with (output/'run.log').open('a', encoding='utf-8') as stream:
            stream.write(str(message)+'\n')
        log(message)
    try:
        if run_tests:
            record('Running unit and integration tests')
            result = subprocess.run([sys.executable,'-m','pytest','tests','-q'], cwd=ROOT,
                                    capture_output=True, text=True, timeout=300)
            record(result.stdout)
            if result.returncode:
                raise RuntimeError('Preflight tests failed. '+result.stderr)
        paths, provenance = resolve_region_inputs(ROOT,name.lower(),aoi,date,log=record)
        landcover_path=paths['landcover']
        buildings = []
        for kind in ['osm','overture']:
            frame = gpd.read_file(paths[kind], **({'layer':'buildings'} if kind == 'osm' else {}))
            if frame.crs is None:
                raise ValueError(f'{kind} buildings have no CRS.')
            buildings.append(frame[['geometry']].to_crs(4326))
        merged = gpd.GeoDataFrame(pd.concat(buildings,ignore_index=True), geometry='geometry',crs=4326)
        # NEW: read the water/industrial layers and pass them through as exclusions.
        layers=('water','industrial') if screening_profile=='neha-236c34c' else EXCLUSION_LAYERS
        exclusions = {layer: _read_osm_layer(paths['osm'], layer, record) for layer in layers}
        # Geographic applicability must survive a change of AOI display name.
        reviews, review_sources = [], []
        for review_path in sorted((ROOT/'data/raw').glob('*/reviewed_exclusions.geojson')):
            frame = gpd.read_file(review_path)
            if frame.crs is None:
                raise ValueError(f'Reviewed exclusions have no CRS: {review_path}')
            frame = frame.to_crs(4326)
            frame = frame[frame.intersects(aoi.to_crs(4326).geometry.union_all())]
            if len(frame):
                reviews.append(frame[['geometry']])
                review_sources.append({'path':str(review_path.relative_to(ROOT)), 'sha256':digest(review_path)})
        if reviews:
            exclusions['reviewed'] = gpd.GeoDataFrame(pd.concat(reviews,ignore_index=True),crs=4326)
            provenance['reviewed_exclusions'] = review_sources
        summary = process_inputs(paths['spectral'], paths['scl'], merged, exclusions, aoi, output, name, record,
                                 screening_profile=screening_profile, landcover_path=landcover_path)
        record('Candidate output is pending review; existing processed polygons and knowledge selection are unchanged')
        status.update(status='complete', summary=summary, provenance=provenance)
        record(f'Complete: {output}')
    except Exception as exc:
        status.update(status='failed', error=str(exc))
        record(f'Failed: {exc}')
        raise
    finally:
        write_json(output/'run.json', status)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aoi', required=True)
    parser.add_argument('--date', required=True)
    parser.add_argument('--name', default='AOI')
    parser.add_argument('--screening-profile', choices=['neha-236c34c','conservative', 'calibrated'], default='neha-236c34c')
    args = parser.parse_args()
    result = run(args.aoi, args.date, args.name, screening_profile=args.screening_profile)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
