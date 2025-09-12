
def test_login_logout_session(client, sample_recorder_user):
    response = client.post('/api/auth/login', json=sample_recorder_user)
    assert response.status_code == 200
    data = response.get_json()
    assert data['user']['username'] == sample_recorder_user['username']

    with client.session_transaction() as sess:
        assert sess.get('user_id') == sample_recorder_user['username']

    response = client.post('/api/auth/logout')
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert 'user_id' not in sess
