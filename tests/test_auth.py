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


def test_guest_login(client):
    resp = client.post('/api/auth/guest')
    assert resp.status_code == 200

    status = client.get('/api/auth/status')
    data = status.get_json()
    assert status.status_code == 200
    assert data['authenticated'] is True
    assert data['user']['role'] == 'guest'

