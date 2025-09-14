def test_create_and_list_session(client, login):
    login()
    # ensure clean slate
    listing = client.get('/api/session/list')
    for s in listing.get_json().get('sessions', []):
        client.delete(f"/api/session/delete/{s['session_id']}")

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


def test_default_session_name_uniqueness(client, login):
    login()
    listing = client.get('/api/session/list')
    for s in listing.get_json().get('sessions', []):
        client.delete(f"/api/session/delete/{s['session_id']}")
    first = client.post('/api/session/create', json={})
    assert first.status_code == 200
    first_name = first.get_json()['session_name']
    first_id = first.get_json()['session_id']

    second = client.post('/api/session/create', json={})
    assert second.status_code == 200
    second_name = second.get_json()['session_name']
    second_id = second.get_json()['session_id']

    assert second_name == f"{first_name}_1"

    # cleanup
    client.delete(f'/api/session/delete/{first_id}')
    client.delete(f'/api/session/delete/{second_id}')


def test_custom_session_name_duplicate_fails(client, login):
    login()
    listing = client.get('/api/session/list')
    for s in listing.get_json().get('sessions', []):
        client.delete(f"/api/session/delete/{s['session_id']}")

    resp1 = client.post('/api/session/create', json={'session_name': 'CustomName'})
    assert resp1.status_code == 200
    session_id = resp1.get_json()['session_id']

    resp2 = client.post('/api/session/create', json={'session_name': 'CustomName'})
    assert resp2.status_code == 400

    # cleanup
    client.delete(f'/api/session/delete/{session_id}')


def test_user_delete_requires_approval(client, login):
    # create invite code
    login()
    # ensure user does not already exist
    client.post('/api/superadmin/delete-account', json={'username': 'regular'})
    # clear existing sessions
    listing = client.get('/api/session/list')
    for s in listing.get_json().get('sessions', []):
        client.delete(f"/api/session/delete/{s['session_id']}")
    invite = client.post('/api/admin/invite')
    code = invite.get_json()['invite_code']
    client.post('/api/auth/logout')

    # signup regular user
    signup = client.post('/api/auth/signup', json={
        'username': 'regular',
        'password': 'pass123',
        'name': 'Regular',
        'invite_code': code
    })
    assert signup.status_code == 201

    # login as regular user and create sessions
    login(username='regular', password='pass123')
    create = client.post('/api/session/create', json={'session_name': 'user_session'})
    assert create.status_code == 200
    sess_id = create.get_json()['session_id']

    create2 = client.post('/api/session/create', json={'session_name': 'temp_session'})
    assert create2.status_code == 200
    temp_id = create2.get_json()['session_id']

    # direct delete should be forbidden
    direct = client.delete(f'/api/session/delete/{sess_id}')
    assert direct.status_code == 403

    # submit delete request for the first session
    req = client.post('/api/session/request-delete', json={'session_id': sess_id})
    assert req.status_code == 200
    request_id = req.get_json()['request']['id']
    client.post('/api/auth/logout')

    # approve as admin and clean up
    login()
    approve = client.post(f'/api/admin/delete-requests/{request_id}/approve')
    assert approve.status_code == 200
    client.delete(f'/api/session/delete/{temp_id}')

    # cleanup user
    client.post('/api/superadmin/delete-account', json={'username': 'regular'})

