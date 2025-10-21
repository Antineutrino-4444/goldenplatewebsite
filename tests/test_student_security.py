import io
import os
import sys

sys.path.insert(0, os.path.abspath('.'))

from src.main import app


def login(client, username='antineutrino', password='b-decay'):
    return client.post('/api/auth/login', json={'username': username, 'password': password})


def upload_sample_csv(client):
    csv_content = 'Student ID,Last,Preferred,Grade,Advisor,House,Clan\n'
    csv_content += '12345,Doe,John,9,Smith,Barn,Alpha\n'
    data = {
        'file': (io.BytesIO(csv_content.encode('utf-8')), 'students.csv')
    }
    return client.post('/api/csv/upload', data=data, content_type='multipart/form-data')

