"""Register known Bhadra inputs without moving or redownloading scientific data.

Usage: python -m scripts.pipeline.register_existing_inputs
"""
import json
from pathlib import Path

from .inputs import ROOT,load_aoi
from .region_inputs import RegionInputs
from scripts.knowledge.sources import file_sha256


def register_bhadra(root=ROOT,log=print):
    root=Path(root).resolve();boundary=root/'data/raw/Bhadra/bhadra_entire_region.geojson'
    service=RegionInputs(root,'bhadra',load_aoi(boundary))
    registry=root/'data/knowledge/registry.json'
    before=registry.read_bytes() if registry.is_file() else None
    protected=[p for p in (root/'data/knowledge').glob('*/knowledge.gpkg')]
    hashes={str(p):file_sha256(p) for p in protected}
    adopted=service.adopt_bhadra(log)
    # This operation is offline: only the already retained, hash-identified local
    # DEM is permitted. Never call the acquisition fallback during migration.
    from .elevation import KNOWN_FABDEM_SHA256,FABDEM_METADATA
    dem=root/'data/raw/DEM/FABDEM_N13E075.tif'
    if dem.is_file() and file_sha256(dem)==KNOWN_FABDEM_SHA256:
        service.store.adopt('dem',None,{'dem':dem},{**FABDEM_METADATA,'units':'m','legacy_source':str(dem)},service.validate('dem'))
        adopted.append('dem')
    for p,digest in hashes.items():
        if file_sha256(p)!=digest:raise ValueError('Protected knowledge changed during input registration')
    if (registry.read_bytes() if registry.is_file() else None)!=before:raise ValueError('Knowledge selection changed during registration')
    return {'adopted':adopted,'knowledge_hashes_unchanged':hashes,'registry_unchanged':True,
            'inputs':service.readiness('2026-06-01'),'operation':'offline registration; no source moved, no provider requested'}


def main():
    result=register_bhadra()
    output=ROOT/'docs/reviews/2026-10-18/region-input-adoption.json'
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'adopted':result['adopted'],'registry_unchanged':True,'report':str(output)},indent=2))


if __name__=='__main__':main()
