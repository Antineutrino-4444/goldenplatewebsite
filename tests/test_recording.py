import io


def upload_csv(client):
    csv_content = 'Last,First,Student ID\nDoe,John,123\nRoe,Jane,456\n'
    data = {'file': (io.BytesIO(csv_content.encode('utf-8')), 'students.csv')}
    return client.post('/api/csv/upload', data=data, content_type='multipart/form-data')


def test_recording_categories_and_stats(client, login):
    login()
    # clear existing sessions
    listing = client.get('/api/session/list')
    for s in listing.get_json().get('sessions', []):
        client.delete(f"/api/session/delete/{s['session_id']}")
    assert upload_csv(client).status_code == 200
    client.post('/api/session/create', json={'session_name': 'record_test'})

    assert client.post('/api/record/clean', json={'input_value': '123'}).status_code == 200
    assert client.post('/api/record/red', json={'input_value': '456'}).status_code == 200

    status = client.get('/api/session/status')
    assert status.status_code == 200
    data = status.get_json()
    assert data['clean_count'] == 1
    assert data['red_count'] == 1

