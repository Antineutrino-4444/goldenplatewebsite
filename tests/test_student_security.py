import io
import os
import sys

sys.path.insert(0, os.path.abspath('.'))

from src.main import app


def login(client, username='admin', password='admin123'):
    return client.post('/api/auth/login', json={'username': username, 'password': password})


def upload_sample_csv(client):
    csv_content = 'Last,First,Student ID\nDoe,John,12345\n'
    data = {
        'file': (io.BytesIO(csv_content.encode('utf-8')), 'students.csv')
    }
    return client.post('/api/csv/upload', data=data, content_type='multipart/form-data')


def test_records_store_only_names_and_csv_cleared_on_logout():
    with app.test_client() as client:
        # Login and upload CSV
        resp = login(client)
        assert resp.status_code == 200
        assert upload_sample_csv(client).status_code == 200

        # Create a session
        client.post('/api/session/create', json={'session_name': 'Test'})

        # Record student by ID
        record_resp = client.post('/api/record/clean', json={'input_value': '12345'})
        assert record_resp.status_code == 200

        # Ensure record history contains name only
        history_resp = client.get('/api/session/history')
        data = history_resp.get_json()
        assert history_resp.status_code == 200
        assert 'scan_history' in data
        assert data['scan_history'][0]['first_name'] == 'John'
        assert 'Student ID' not in data['scan_history'][0]

        # Logout to clear CSV data
        client.post('/api/auth/logout')

        # Login again and ensure CSV preview shows no data
        login(client)
        preview_resp = client.get('/api/csv/preview')
        preview_data = preview_resp.get_json()
        assert preview_resp.status_code == 200
        assert preview_data['status'] == 'no_data'

