from src.routes.golden_plate_recorder_db.db import DEFAULT_SCHOOL_ID, DEFAULT_SCHOOL_SLUG


def test_login_logout_status(client, login):
    resp = login()
    assert resp.status_code == 200

    status = client.get('/api/auth/status')
    assert status.status_code == 200
    data = status.get_json()
    assert data['authenticated'] is True

    client.post('/api/auth/logout')
    status = client.get('/api/auth/status')
    assert status.status_code == 200
    data = status.get_json()
    assert data['authenticated'] is False


def test_login_failure(client):
    resp = client.post('/api/auth/login', json={'username': 'antineutrino', 'password': 'wrong'})
    assert resp.status_code == 401


def test_guest_login_requires_slug(client):
    resp = client.post('/api/auth/guest')
    assert resp.status_code == 400


def test_guest_login_with_slug(client):
    resp = client.post('/api/auth/guest', json={'school_slug': DEFAULT_SCHOOL_SLUG})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['user']['school']['slug'] == DEFAULT_SCHOOL_SLUG
    assert payload['user']['school_id'] == DEFAULT_SCHOOL_ID

    status = client.get('/api/auth/status')
    data = status.get_json()
    assert status.status_code == 200
    assert data['authenticated'] is True
    assert data['user']['role'] == 'guest'
    assert data['user']['school_id'] == DEFAULT_SCHOOL_ID
    assert data['user']['school']['slug'] == DEFAULT_SCHOOL_SLUG


def test_guest_login_invalid_slug(client):
    resp = client.post('/api/auth/guest', json={'school_slug': 'missing-school'})
    assert resp.status_code == 404

