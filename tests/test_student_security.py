import io
import os
import sys

sys.path.insert(0, os.path.abspath('.'))

from src.main import app
from conftest import TEST_SUPERADMIN_PASSWORD, TEST_SUPERADMIN_USERNAME, ensure_test_account_passwords


def login(client, username=TEST_SUPERADMIN_USERNAME, password=TEST_SUPERADMIN_PASSWORD):
    client.get('/api/auth/status')
    ensure_test_account_passwords()
    return client.post('/api/auth/login', json={'username': username, 'password': password})


def upload_sample_csv(client):
    csv_content = 'Student ID,Last,Preferred,Grade,Advisor,House,Clan\n'
    csv_content += '12345,Doe,John,9,Smith,Barn,Alpha\n'
    data = {
        'file': (io.BytesIO(csv_content.encode('utf-8')), 'students.csv')
    }
    return client.post('/api/csv/upload', data=data, content_type='multipart/form-data')
