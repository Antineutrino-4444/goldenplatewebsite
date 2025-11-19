def test_non_admin_cannot_generate_invite(client, login):
    client.post('/api/auth/signup', json={
        'username': 'regular',
        'password': 'userpass',
        'name': 'Regular User'
    })
    login(username='regular', password='userpass')
    resp = client.post('/api/admin/invite')
    assert resp.status_code == 403


def test_invite_signup_flow(client, login):
    # Admin generates invite code
    login()
    invite = client.post('/api/admin/invite')
    assert invite.status_code == 201
    code = invite.get_json()['invite_code']
    client.post('/api/auth/logout')

    # Signup with invite code
    signup = client.post('/api/auth/signup', json={
        'username': 'pytestuser',
        'password': 'pass123',
        'name': 'Pytest User',
        'invite_code': code
    })
    assert signup.status_code == 201

    # Reusing code should fail
    reuse = client.post('/api/auth/signup', json={
        'username': 'pytestuser2',
        'password': 'pass123',
        'name': 'Another',
        'invite_code': code
    })
    assert reuse.status_code == 403

    # New user can log in
    login(username='pytestuser', password='pass123')
    client.post('/api/auth/logout')

    # Cleanup the created user
    login(username='antineutrino', password='b-decay')
    delete = client.post('/api/superadmin/delete-account', json={'username': 'pytestuser'})
    assert delete.status_code == 200


def test_admin_users_include_school_metadata(client, login):
    login()
    resp = client.get('/api/admin/users')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload and 'users' in payload and payload['users'], 'Expected users list in response'
    super_admin = next((user for user in payload['users'] if user['username'] == 'antineutrino'), payload['users'][0])
    assert 'school' in super_admin
    assert super_admin['school'] is None or 'name' in super_admin['school']
    assert 'status' in super_admin


def test_admin_overview_includes_school_metadata(client, login):
    login()
    resp = client.get('/api/admin/overview')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload and 'users' in payload and payload['users'], 'Expected users list in overview response'
    first_user = payload['users'][0]
    assert 'school' in first_user
    assert first_user['school'] is None or 'name' in first_user['school']
    assert 'status' in first_user

