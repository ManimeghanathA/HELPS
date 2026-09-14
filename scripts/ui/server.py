"""Serve HELPSs on loopback: python -m scripts.ui.server."""
import argparse
import json
import mimetypes
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from scripts.pipeline.inputs import ROOT, data_directory
from scripts.pipeline.run_aoi_pipeline import run
from scripts.search_historical_sentinel_dates import scan_historical_dates

WEB = Path(__file__).parent
LOCK = threading.Lock()
STATE = {'status':'idle','log':[]}
ARTIFACTS = {'final_zones.png','final_zones.geojson','final_zones.gpkg','summary.json','run.log'}


def history():
    entries = []
    for path in sorted((ROOT/'data/runs').glob('*/run.json'), reverse=True):
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
            entries.append(item)
        except (OSError, ValueError):
            continue
    return entries


class Handler(BaseHTTPRequestHandler):
    def send(self, data, content_type='application/json', code=200):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/state':
            with LOCK:
                data = dict(STATE, log=list(STATE['log']))
            return self.send(data)
        if path == '/api/runs':
            return self.send(history())
        if path.startswith('/artifacts/'):
            parts = path.split('/')
            if len(parts) == 4 and parts[2].replace('_','').isalnum() and parts[3] in ARTIFACTS:
                file = ROOT/'data/runs'/parts[2]/parts[3]
                if file.is_file():
                    return self.send(file.read_bytes(), mimetypes.guess_type(file)[0] or 'application/octet-stream')
        if path == '/baseline.png':
            file = ROOT/'docs/results/bhadra_final_open_land_zones.png'
            if file.exists():
                return self.send(file.read_bytes(), 'image/png')
        if path in ['/', '/app.js', '/style.css']:
            file = WEB/('index.html' if path == '/' else path[1:])
            return self.send(file.read_bytes(), mimetypes.guess_type(file)[0] or 'text/plain')
        self.send({'error':'Not found'}, code=404)

    def do_POST(self):
        if self.path == '/api/historical-scan':
            try:
                return self.send(scan_historical_dates())
            except Exception as exc:
                return self.send({'error':str(exc)},code=500)
        if self.path != '/api/run':
            return self.send({'error':'Not found'},code=404)
        # Require a browser request from this same loopback origin.
        origin = self.headers.get('Origin')
        host = self.headers.get('Host','')
        if host not in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}:
            return self.send({'error':'Host rejected'},code=403)
        if origin and origin != 'http://'+host:
            return self.send({'error':'Origin rejected'},code=403)
        if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            return self.send({'error':'JSON required'},code=415)
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 20*1024*1024:
                raise ValueError('Upload must be smaller than 20 MB.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data,dict):
                raise ValueError('Request must be a JSON object.')
            if not isinstance(data.get('geojson'),dict):
                raise ValueError('Select an AOI GeoJSON.')
            from datetime import date
            date.fromisoformat(data['date'])
            if not isinstance(data.get('name','AOI'), str):
                raise ValueError('AOI name must be text.')
        except (ValueError,KeyError,TypeError) as exc:
            return self.send({'error':str(exc)},code=400)
        with LOCK:
            if STATE['status'] == 'running':
                return self.send({'error':'A run is already in progress.'},code=409)
            STATE.update(status='running', log=[], result=None, error=None,
                         name=data.get('name','AOI'), date=data['date'])
        upload = ROOT/'data/uploads'/f'{uuid.uuid4().hex}.geojson'
        data_directory(upload.parent)
        upload.write_text(json.dumps(data['geojson']),encoding='utf-8')
        def log(message):
            with LOCK:
                STATE['log'].append(str(message))
        def work():
            try:
                result = run(upload,data['date'],data.get('name','AOI'),log=log)
                with LOCK:
                    STATE.update(status='complete',result=result)
            except Exception as exc:
                with LOCK:
                    STATE.update(status='failed',error=str(exc))
            finally:
                upload.unlink(missing_ok=True)
        threading.Thread(target=work,daemon=True).start()
        self.send({'status':'running'},code=202)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'HELPSs: http://127.0.0.1:{args.port}',flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
