"""Launch the current local draft UI using the review environment."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
draft = root / "HELPS - draft"
sys.path.insert(0, str(draft / ".review-deps"))
sys.path.insert(0, str(draft))
from app import app

@app.after_request
def baseline_banner(response):
    if response.mimetype == 'text/html':
        banner='<div style="position:fixed;bottom:16px;left:16px;right:16px;z-index:2000;background:#153b39;color:#e0f4ec;padding:12px;border:1px solid #5b9b88;border-radius:8px;font:14px sans-serif">WORKING CANDIDATE MAP — broader candidate set retained. Terrain and obstacles still require verification.</div>'
        html=response.get_data(as_text=True).replace('HELPS - Helicopter Emergency Landing Planning System','HELPS — Working candidate map')
        response.set_data(html.replace('</body>',banner+'</body>'))
    return response

app.run(host="127.0.0.1", port=8766, debug=False)
