import threading
import requests

import scripts.ui.server as ui_server
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


def test_server_returns_historical_scan_results(monkeypatch):
    monkeypatch.setattr(ui_server, 'scan_historical_dates',
                        lambda: {'best_date_per_month': [{'month': '2025-10', 'date': '2025-10-12', 'cloud_cover': 2.34}]})
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker = threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        response = requests.post(url+'/api/historical-scan',timeout=5)
        assert response.status_code == 200
        assert response.json()['best_date_per_month'][0]['date'] == '2025-10-12'
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
