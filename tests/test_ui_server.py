import threading
import requests

from scripts.ui.server import Handler, ThreadingHTTPServer


def test_server_restricts_files_and_rejects_bad_requests():
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker = threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{server.server_port}'
    s = requests.Session()
    s.headers.update({'Connection': 'close'})
    try:
        assert s.get(url,timeout=5).status_code == 200
        assert s.get(url+'/.env',timeout=5).status_code == 404
        assert s.get(url+'/artifacts/bad/.env',timeout=5).status_code == 404
        assert s.post(url+'/api/run',json={},timeout=5).status_code == 400
        assert s.post(url+'/api/run',json={},headers={'Origin':'https://example.com','Connection':'close'},timeout=5).status_code == 403
        assert s.get(url+'/api/runs',timeout=5).status_code == 200
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
