"""Separate HELPS UI for an explicit experiment; leaves the baseline server intact."""
import sys,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
DRAFT=ROOT/'HELPS - draft'
sys.path.insert(0,str(DRAFT/'.review-deps'));sys.path.insert(0,str(DRAFT))
output=Path((ROOT/'docs/reviews/2026-10-13/latest-experiment-path.txt').read_text().strip())
metadata=json.loads((output/'run.json').read_text())
if metadata['status']!='experimental_complete' or not metadata['summary']['audits']['passed']:
    raise ValueError('Experimental preview requires a finished, audited experiment.')
preview_root=output/'preview_data'
folder=preview_root/'processed/Bhadra/sentinel2/2026-06-01';folder.mkdir(parents=True,exist_ok=True)
shutil.copy2(output/'final_zones.gpkg',folder/'bhadra_final_open_land_zones.gpkg')
import app as web
from landing_zone_engine import LandingZoneEngine
web.landing_engine=LandingZoneEngine(preview_root)
web.landing_engine.active_run_info={**metadata,'run_id':output.name}

@web.app.after_request
def experimental_banner(response):
    if response.mimetype=='text/html':
        banner='<div style="position:fixed;bottom:16px;left:16px;right:16px;z-index:2000;background:#492e09;color:#fff1cc;padding:12px;border:1px solid #d6a351;border-radius:8px;font:14px sans-serif">Experimental screening — 191 candidates · WorldCover 2021 · industrial/facility coverage incomplete · clearance unverified. <a style="color:#fff" href="http://127.0.0.1:8766">Open baseline</a></div>'
        response.set_data(response.get_data(as_text=True).replace('</body>',banner+'</body>'))
    return response

web.app.run(host='127.0.0.1',port=8770,debug=False)
