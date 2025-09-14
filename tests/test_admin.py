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

