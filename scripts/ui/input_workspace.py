"""Engineer-only input readiness and registered evidence access."""
from datetime import date
from urllib.parse import urlencode

from flask import Blueprint, jsonify, request, send_file

from scripts.knowledge.contracts import SourceAsset
from scripts.knowledge.sources import read_vector
from scripts.pipeline.region_inputs import RegionInputs
from scripts.pipeline.source_store import safe_id


def register_input_workspace(app,root,catalog,guard):
    bp=Blueprint('input_workspace',__name__)

    def service(region):
        source=catalog(safe_id(region)).get('aoi')
        if not source:raise ValueError('Region boundary missing')
        aoi=SourceAsset.from_dict({**source,'path':str(root/source['path'])})
        return RegionInputs(root,region,read_vector(aoi))

    @bp.errorhandler(ValueError)
    def invalid(exc):return jsonify(error=str(exc)),400

    @bp.post('/api/knowledge/input-readiness')
    def readiness():
        denied=guard()
        if denied:return denied
        d=request.get_json(silent=True)
        if not isinstance(d,dict):raise ValueError('Region and observation date required')
        day=d.get('date','')
        try:
            if date.fromisoformat(day).isoformat()!=day:raise ValueError()
        except (ValueError,TypeError):raise ValueError('Observation date must use YYYY-MM-DD') from None
        region=d.get('region_id','');s=service(region)
        rows=s.readiness(day,refresh=d.get('refresh_obstacles') is True)
        for row in rows:
            row['access']=[]
            if row['snapshot_id']:
                for key,file in row['files'].items():
                    query={'region_id':region,'kind':row['kind'],'snapshot_id':row['snapshot_id'],'phase':row['phase'],'key':key}
                    if row['kind']=='sentinel':query['date']=day
                    row['access'].append({'key':key,'location':str(root/file['path']),'download_url':'/api/knowledge/input-file?'+urlencode(query)})
        return jsonify(region_id=region,date=day,inputs=rows,
                       knowledge_directory=str(root/'data/knowledge'),
                       note='Readiness inspects local registered evidence only. Builds revalidate every source. Context snapshots retain independent dates.')

    @bp.get('/api/knowledge/input-file')
    def download():
        denied=guard()
        if denied:return denied
        q=request.args
        if 'path' in q:raise ValueError('Use registered source identity, not a file path')
        s=service(q.get('region_id',''))
        path=s.store.file(q.get('kind'),q.get('snapshot_id'),q.get('phase'),q.get('key'),q.get('date'))
        return send_file(path,as_attachment=True)

    app.register_blueprint(bp)
