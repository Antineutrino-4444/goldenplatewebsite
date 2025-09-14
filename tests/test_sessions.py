def test_create_and_list_session(client, login):
    login()
    create = client.post('/api/session/create', json={'session_name': 'pytest_session'})
    assert create.status_code == 200
    session_id = create.get_json()['session_id']

    listing = client.get('/api/session/list')
    assert listing.status_code == 200
    data = listing.get_json()
    assert any(s['session_id'] == session_id for s in data['sessions'])


def test_guest_cannot_create_session(client):
    client.post('/api/auth/guest')
    resp = client.post('/api/session/create', json={'session_name': 'guest_session'})
    assert resp.status_code == 401


def test_default_session_name_suffix(client, login):
    login()
    first = client.post('/api/session/create', json={})
    assert first.status_code == 200
    base_name = first.get_json()['session_name']
    second = client.post('/api/session/create', json={})
    assert second.status_code == 200
    assert second.get_json()['session_name'] == f"{base_name}_1"


def test_custom_name_duplicate_rejected(client, login):
    login()
    first = client.post('/api/session/create', json={'session_name': 'dup'})
    assert first.status_code == 200
    second = client.post('/api/session/create', json={'session_name': 'dup'})
    assert second.status_code == 400

