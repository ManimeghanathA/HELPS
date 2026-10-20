from app import app

def test_full_role_workflow_and_version_download_rejection():
    c=app.test_client()
    assert b'unified_application.js' in c.get('/').data
    for role in ('engineer','application'):
        response=c.get('/workspace/'+role)
        assert response.status_code==200
        for view in (b'data-tab="application"',b'data-tab="candidates"',b'data-tab="map"',b'data-tab="build"'):assert view in response.data
    assert c.get('/api/datasets/not-published/download').status_code==404
    assert c.post('/api/datasets/not-published/activate',json={}).status_code==403
