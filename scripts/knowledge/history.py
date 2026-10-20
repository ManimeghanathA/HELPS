"""Reclassify dated history under one explicit spectral/cloud policy without editing originals."""
import hashlib
import json
from pathlib import Path
from .sources import file_sha256
from .repository import _atomic_json
from .temporal import validate_history_raster


def harmonize_history(history,cache_dir,profile='conservative',log=print):
    from .build import algorithm_fingerprint
    from scripts.processing.open_land_detector import generate_possible_open_mask
    if profile not in ('calibrated','conservative','neha-236c34c'):raise ValueError('Unknown historical classification policy')
    cache_dir=Path(cache_dir);cache_dir.mkdir(parents=True,exist_ok=True);result=[]
    implementation=algorithm_fingerprint()
    for original in history:
        row=dict(original)
        if row.get('status')!='available':result.append(row);continue
        try:
            path=Path(row['path'])
            if validate_history_raster(path)['sha256']!=row['sha256']:raise ValueError('Historical classification source hash changed')
            candidates=[(Path(row['spectral_path']),Path(row['scl_path']))] if row.get('spectral_path') and row.get('scl_path') else [(path.parent/'bhadra_spectral.tif',path.parent/'bhadra_scl.tif'),(path.parent/'spectral.tif',path.parent/'scl.tif')]
            pair=next(((spectral,scl) for spectral,scl in candidates if spectral.is_file() and scl.is_file()),None)
            if pair is None:raise ValueError('Original spectral/SCL evidence unavailable for consistent historical classification')
            spectral,scl=pair;hashes={'spectral_sha256':file_sha256(spectral),'scl_sha256':file_sha256(scl)}
            if not all(row.get(key) for key in hashes):raise ValueError('Pinned historical imagery hashes unavailable; original-source integrity is unverified')
            for key,value in hashes.items():
                if row.get(key) and row[key]!=value:raise ValueError('Historical imagery source hash changed')
            identity={'date':row['date'],'original_classification_sha256':row['sha256'],'classification_policy':profile,'cloud_buffer_pixels':3,'algorithm_fingerprint':implementation,'original_provenance_state':row.get('provenance_state','unknown'),**hashes}
            key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
            folder=cache_dir/key;folder.mkdir(parents=True,exist_ok=True);state=folder/'classification.tif';manifest=folder/'manifest.json'
            cached=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
            if not state.exists() or cached.get('identity')!=identity or cached.get('sha256')!=file_sha256(state):
                log('Reclassifying historical '+row['date']+' using '+profile+' and 30 m cloud margin')
                generate_possible_open_mask(spectral,scl,state,cloud_buffer_pixels=3,screening_profile=profile)
                _atomic_json(manifest,{'identity':identity,'sha256':file_sha256(state)})
            row.update(path=str(state.resolve()),source_id='harmonized-'+key[:24],original_source_id=row['source_id'],**identity,**validate_history_raster(state),provenance_state='reclassified_from_original_dated_sources',spectral_path=str(spectral.resolve()),scl_path=str(scl.resolve()),policy_scope='same spectral and cloud screening across dates; mapped obstacle and 2021 land-cover exclusions are not temporal observations')
        except (ValueError,OSError,KeyError) as exc:
            row.update(status='failed',error=str(exc),classification_policy=profile)
        result.append(row)
    return result
