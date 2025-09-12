from src.models.user import User


def test_create_and_get_user(client):
    response = client.post('/api/users', json={'username': 'u1', 'email': 'u1@example.com'})
    assert response.status_code == 201
    data = response.get_json()
    user_id = data['id']
    assert data['username'] == 'u1'

    response = client.get(f'/api/users/{user_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['username'] == 'u1'
    assert data['email'] == 'u1@example.com'
