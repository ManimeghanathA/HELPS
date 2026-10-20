"""Measured inventory QA, cached separately from immutable published packages."""
import hashlib
import json
from pathlib import Path
from threading import RLock

_cache={}
_lock=RLock()


def scl_inventory_quality(root,aoi_source,scl_path):
    from scripts.knowledge.contracts import SourceAsset
    from scripts.knowledge.sources import read_vector
    root=Path(root);path=Path(scl_path)
    if not path.is_file() or not aoi_source:return {'qa_state':'unknown'}
    source={**aoi_source,'path':str((root/aoi_source['path']).resolve())}
    aoi_path=Path(source['path'])
    if not aoi_path.is_file():return {'qa_state':'unknown'}
    stats=(path.stat(),aoi_path.stat())
    signature=(str(path.resolve()),stats[0].st_mtime_ns,stats[0].st_size,str(aoi_path.resolve()),stats[1].st_mtime_ns,stats[1].st_size,source.get('layer'))
    with _lock:
        if signature in _cache:return dict(_cache[signature])
        try:
            aoi=read_vector(SourceAsset.from_dict(source))
            geometry_hash=hashlib.sha256(aoi.to_crs(4326).geometry.union_all().wkb).hexdigest()
            key=hashlib.sha256(json.dumps([signature,geometry_hash]).encode()).hexdigest()
            folder=root/'data/knowledge/inventory-qa';cache=folder/(key+'.json')
            if cache.is_file():quality=json.loads(cache.read_text(encoding='utf-8'))
            else:
                from scripts.pipeline.monthly import measure_scl_quality
                quality=measure_scl_quality(path,aoi)
                quality['aoi_geometry_sha256']=geometry_hash
                folder.mkdir(parents=True,exist_ok=True)
                from scripts.knowledge.repository import _atomic_json
                _atomic_json(cache,quality)
        except (OSError,ValueError):quality={'qa_state':'unknown','qa_note':'Local SCL could not be measured for this region'}
        _cache[signature]=quality
        return dict(quality)
