"""Bounded Overpass fallback with adaptive query subdivision and raw checkpoints."""
import hashlib
import json
import re
import time
from pathlib import Path

import requests
from scripts.knowledge.repository import _atomic_json


def fetch(aoi,tags,log,endpoints,session=None,cache_dir=None):
    session=session or requests.Session();deadline=time.monotonic()+240
    attempts=0;subqueries=0;query_dates=[]
    def query(bounds,depth=0):
        nonlocal attempts,subqueries
        west,south,east,north=bounds
        filters=[]
        for key,value in tags.items():
            if value is True:selector=f'[{json.dumps(key)}]'
            elif isinstance(value,list):selector=f'[{json.dumps(key)}~{json.dumps("^("+"|".join(re.escape(v) for v in value)+")$")}]'
            else:selector=f'[{json.dumps(key)}={json.dumps(value)}]'
            filters.append(f'nwr{selector}({south},{west},{north},{east});')
        text='[out:json][timeout:25];('+''.join(filters)+');out body;>;out skel qt;'
        key=hashlib.sha256(text.encode()).hexdigest()
        path=Path(cache_dir)/(key+'.json') if cache_dir else None
        if path and path.is_file():
            try:
                record=json.loads(path.read_text(encoding='utf-8'));payload=record['payload']
                if record['query_hash']==key and record['payload_hash']==hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest() and isinstance(payload.get('elements'),list) and not payload.get('remark'):
                    query_dates.append(record['acquired_at']);return payload
            except (OSError,ValueError,KeyError,TypeError):pass
        for endpoint in endpoints:
            remaining=deadline-time.monotonic()
            if remaining<=0 or attempts>=32:raise RuntimeError('OSM acquisition failed: bounded retry budget reached; partial raw responses are preserved')
            attempts+=1;log(f'OSM bounded request (part depth {depth}): {endpoint}')
            try:
                response=session.post(endpoint,data={'data':text},timeout=(min(10,remaining),min(40,remaining)),
                    headers={'User-Agent':'HELPS research prototype (https://github.com/ManimeghanathA/HELPS)','Accept':'application/json'})
                response.raise_for_status();payload=response.json()
                if not isinstance(payload,dict) or not isinstance(payload.get('elements'),list) or payload.get('remark'):raise ValueError('Incomplete OSM response')
                from datetime import datetime,timezone
                acquired=datetime.now(timezone.utc).isoformat();query_dates.append(acquired)
                if path:_atomic_json(path,{'query_hash':key,'payload_hash':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),'payload':payload,'acquired_at':acquired})
                return payload
            except (requests.RequestException,ValueError) as exc:
                log(f'OSM provider unavailable ({type(exc).__name__}); trying alternate provider or smaller query')
        if depth>=2 or max(east-west,north-south)<.02:
            raise RuntimeError('OSM acquisition failed: providers could not complete a small query. No empty obstacle layer was substituted.')
        log('OSM request failed on all configured providers; dividing the region into four smaller requests')
        x=(west+east)/2;y=(south+north)/2;elements={}
        for child in ((west,south,x,y),(x,south,east,y),(west,y,x,north),(x,y,east,north)):
            subqueries+=1
            payload=query(child,depth+1)
            for element in payload['elements']:
                identity=(element['type'],element['id']);previous=elements.get(identity,{})
                merged={**previous,**element}
                if previous.get('tags') or element.get('tags'):merged['tags']={**previous.get('tags',{}),**element.get('tags',{})}
                elements[identity]=merged
        return {'elements':list(elements.values())}
    result=query(tuple(float(v) for v in aoi.to_crs(4326).total_bounds))
    result['helps_acquisition']={'requests':attempts,'subqueries':subqueries,'query_acquisition_times':sorted(set(query_dates))}
    return result
