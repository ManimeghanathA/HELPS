import threading
import requests

from scripts.ui.server import Handler, ThreadingHTTPServer


def test_server_restricts_files_and_rejects_bad_requests():
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker = threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        assert requests.get(url,timeout=5).status_code == 200
        assert requests.get(url+'/.env',timeout=5).status_code == 404
        assert requests.get(url+'/artifacts/bad/.env',timeout=5).status_code == 404
        assert requests.post(url+'/api/run',json={},timeout=5).status_code == 400
        assert requests.post(url+'/api/run',json={},headers={'Origin':'https://example.com'},timeout=5).status_code == 403
        assert requests.get(url+'/api/runs',timeout=5).status_code == 200
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
