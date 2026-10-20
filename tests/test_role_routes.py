from app import app

def test_unified_entry_and_compatible_bookmarks():
    c=app.test_client()
    for route in ('/','/workspace/application','/workspace/engineer'):
        response=c.get(route)
        assert response.status_code==200
        for tab in (b'overview',b'map',b'candidates',b'application',b'build'):
            assert b'data-tab="'+tab+b'"' in response.data
        assert b'Application User' not in response.data
        assert b'Choose your role' not in response.data
    assert c.get('/legacy').status_code==200
    assert c.get('/workspace/unknown').status_code==404


def test_role_mutation_is_rejected():
    c=app.test_client()
    assert c.post('/api/knowledge/jobs',json={}).status_code==403
