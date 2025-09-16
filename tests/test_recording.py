import io


def upload_csv(client):
    csv_content = 'Student ID,Last,Preferred,Grade,Advisor,House,Clan\n'
    csv_content += '123,Doe,John,9,Smith,Barn,Alpha\n'
    csv_content += '456,Roe,Jane,10,Jones,Hall,Beta\n'
    data = {'file': (io.BytesIO(csv_content.encode('utf-8')), 'students.csv')}
    return client.post('/api/csv/upload', data=data, content_type='multipart/form-data')


def test_recording_categories_and_stats(client, login):
    login()
    assert upload_csv(client).status_code == 200
    client.post('/api/session/create', json={'session_name': 'record_test'})

    assert client.post('/api/record/clean', json={'input_value': '123'}).status_code == 200
    assert client.post('/api/record/red', json={'input_value': '456'}).status_code == 200

    status = client.get('/api/session/status')
    assert status.status_code == 200
    data = status.get_json()
    assert data['clean_count'] == 1
    assert data['red_count'] == 1

