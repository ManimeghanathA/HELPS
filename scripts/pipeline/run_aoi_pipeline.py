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

from scripts.pipeline.acquisition import acquire, write_json
from scripts.pipeline.inputs import ROOT, load_aoi, cache_key, data_directory
from scripts.pipeline.processing import process_inputs

# CHANGED: these OSM layers get subtracted as exclusions (in addition to buildings).
# 'water' catches natural=water / waterway=* (rivers, canals, drains, ponds).
# 'industrial' catches landuse=industrial/construction/quarry/landfill/farmyard.
# Both are acquired into osm.gpkg by scripts/pipeline/acquisition.py but were
# previously never read back out.
EXCLUSION_LAYERS = ['water', 'industrial']


def _read_osm_layer(path, layer, log):
    """
    Read one OSM layer out of osm.gpkg, tolerating GPKGs written before
    this layer existed (older cached acquisitions). Returns an empty,
    4326 GeoDataFrame instead of raising, so old caches don't hard-fail --
    but note that this means the exclusion is silently skipped until the
    AOI/date is re-acquired.
    """
    try:
        frame = gpd.read_file(path, layer=layer)
    except (ValueError, Exception) as exc:  # pyogrio/fiona raise different types per backend
        log(f'WARNING: "{layer}" layer not found in osm.gpkg ({exc}); '
            f'treating as empty. Delete this AOI/date under data/inputs/ and rerun '
            f'to re-acquire it.')
        return gpd.GeoDataFrame(geometry=[], crs=4326)
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
    canonical_dir = ROOT / 'data/processed' / name / 'sentinel2' / date
    canonical_dir.mkdir(parents=True, exist_ok=True)
    canonical_gpkg = canonical_dir / f'{name.lower()}_final_open_land_zones.gpkg'
    try:
        shutil.copy2(run_gpkg, canonical_gpkg)
    except OSError:
        temp_gpkg = canonical_gpkg.with_suffix('.tmp')
        with open(run_gpkg, 'rb') as fsrc, open(temp_gpkg, 'wb') as fdst:
            shutil.copyfileobj(fsrc, fdst)
        temp_gpkg.replace(canonical_gpkg)
    log(f'Promoted {run_gpkg} -> {canonical_gpkg}')
    return canonical_gpkg


def run(aoi_path, date, name='AOI', log=print, run_tests=True):
    aoi = load_aoi(aoi_path)
    key = cache_key(aoi, date)
    name = re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_')[:60] or 'AOI'
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]
    output = ROOT/'data/runs'/run_id
    data_directory(output)
    status = {'id':run_id,'name':name,'date':date,'aoi_key':key,'status':'running'}
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
        paths, provenance = acquire(aoi, date, record)
        buildings = []
        for kind in ['osm','overture']:
            frame = gpd.read_file(paths[kind], **({'layer':'buildings'} if kind == 'osm' else {}))
            if frame.crs is None:
                raise ValueError(f'{kind} buildings have no CRS.')
            buildings.append(frame[['geometry']].to_crs(4326))
        merged = gpd.GeoDataFrame(pd.concat(buildings,ignore_index=True), geometry='geometry',crs=4326)
        # NEW: read the water/industrial layers and pass them through as exclusions.
        exclusions = {layer: _read_osm_layer(paths['osm'], layer, record) for layer in EXCLUSION_LAYERS}
        summary = process_inputs(paths['spectral'], paths['scl'], merged, exclusions, aoi, output, name, record)
        promote_to_canonical(output, name, date, record)
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
    args = parser.parse_args()
    result = run(args.aoi, args.date, args.name)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()