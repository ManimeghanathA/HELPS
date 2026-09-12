"""CLI and UI entry point for validated single-date processing."""
import argparse
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd

from scripts.pipeline.acquisition import acquire, write_json
from scripts.pipeline.inputs import ROOT, load_aoi, cache_key, data_directory
from scripts.pipeline.processing import process_inputs


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
        summary = process_inputs(paths['spectral'], paths['scl'], merged, aoi, output, name, record)
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
