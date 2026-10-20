"""One active-run selection rule for map geometry, ranking and provenance."""
import json
from pathlib import Path


def latest_completed_run(runs_dir):
    runs_dir = Path(runs_dir)
    if not runs_dir.exists():
        return None
    for folder in sorted(runs_dir.iterdir(), key=lambda p:p.name, reverse=True):
        if not folder.is_dir() or folder.name == 'archive':
            continue
        try:
            metadata = json.loads((folder/'run.json').read_text(encoding='utf-8'))
            if (metadata.get('status') == 'complete'
                    and (not metadata.get('review_required') or metadata.get('review_decision')=='accepted')
                    and metadata.get('summary',{}).get('sources_complete',True) is True
                    and metadata.get('summary',{}).get('experimental',False) is not True
                    and metadata.get('summary',{}).get('audits',{}).get('passed') is True
                    and (folder/'final_zones.gpkg').is_file()
                    and (folder/'final_zones.geojson').is_file()):
                return folder, metadata
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return None
