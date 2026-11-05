import csv
import io
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import SQLAlchemyError

from src.routes.golden_plate_recorder_db import session_routes


def test_api_error_codes_preserve_error_messages_and_leave_success_alone(client):
    response = client.get('/api/session/scan-history')
    assert response.status_code == 401
    assert response.json['error'] == 'Authentication or guest access required'
    assert response.json['error_code'] == 'GET_SCAN_HISTORY_401'
    assert 'error_reference' not in response.json

    missing = client.get('/api/unknown-endpoint')
    assert missing.status_code == 404
    assert missing.json['error_code'] == 'API_404'
    assert 'error_code' not in client.get('/api/auth/status').json


def test_server_error_reference_can_be_found_only_by_interschool_users(client, login, monkeypatch, caplog):
    url = '/api/interschool/error-log'
    assert client.get(url).status_code == 401
    assert login().status_code == 200
    assert client.get(url).status_code == 403

    def fail_to_save(category):
        raise SQLAlchemyError('private exception contents')

    with monkeypatch.context() as patch:
        patch.setattr(session_routes, '_record_student', fail_to_save)
        failure = client.post('/api/record/clean?private-query=123456', json={'input_value': 'private payload'})
    assert failure.status_code == 503
    assert failure.json['error_code'] == 'RECORD_SAVE_FAILED'
    reference = failure.json['error_reference']
    assert re.fullmatch('[A-F0-9]{12}', reference)
    assert 'private' not in failure.get_data(as_text=True)
    assert reference in caplog.text

    assert client.post('/api/auth/logout').status_code == 200
    assert login('inter-school-admin').status_code == 200
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'private' not in response.get_data(as_text=True)
    entry, = response.json['errors']
    assert entry['reference'] == reference
    assert entry['code'] == 'RECORD_SAVE_FAILED'
    assert entry['status'] == 503
    assert entry['route'] == '/api/record/clean'
    assert 'SQLAlchemyError' in entry['detail']


def test_live_server_log_records_actions_across_accounts_and_exports_matching_history(client, login):
    url = '/api/interschool/server-log'
    assert client.get(url).status_code == 401
    assert client.get('/api/app/environment').status_code == 200
    assert login().status_code == 200
    assert client.get(url + '?format=csv').status_code == 403
    assert client.post('/api/session/create', json={'session_name': 'private-audit-test'}).status_code == 200
    assert client.post('/api/record/clean', json={}).status_code == 200
    assert client.post('/api/auth/logout').status_code == 200
    assert client.post('/api/auth/guest', json={'school_slug': 'SAC'}).status_code == 200
    assert client.get('/api/auth/status').status_code == 200
    assert client.post('/api/auth/guest/logout').status_code == 200
    assert login('inter-school-admin').status_code == 200

    response = client.get(url + '?poll=1')
    assert response.headers['Cache-Control'] == 'no-store'
    entries = response.json['entries']
    assert entries == sorted(entries, key=lambda entry: entry['id'])
    assert any(entry['actor'] == 'Anonymous' and entry['route'] == '/api/app/environment' for entry in entries)
    plate, = [entry for entry in entries if entry['route'] == '/api/record/clean']
    assert plate['actor'] == 'greenguys'
    assert plate['school'] == 'SAC'
    assert plate['status'] == 200
    assert any(entry['actor'] == plate['actor'] and entry['route'] == '/api/auth/logout' for entry in entries)
    guest_rows = [entry for entry in entries if entry['actor'] == 'Guest']
    assert {entry['route'] for entry in guest_rows} == {'/api/auth/guest', '/api/auth/status', '/api/auth/guest/logout'}
    assert len({entry['actor_id'] for entry in guest_rows}) == 1 and guest_rows[0]['actor_id']
    assert 'private-audit-test' not in response.get_data(as_text=True)

    cursor = response.json['cursor']
    assert client.get(f'{url}?after={cursor}&poll=1').json['entries'] == []
    assert client.get('/api/app/environment').status_code == 200
    update = client.get(f'{url}?after={cursor}&poll=1').json['entries']
    assert [entry['route'] for entry in update] == ['/api/app/environment']
    failures = client.get(url + '?failures=1&poll=1').json['entries']
    assert failures and all(entry['status'] >= 400 for entry in failures)

    export = client.get(url + '?format=csv&search=/api/record/clean')
    assert export.headers['Content-Disposition'].startswith('attachment;')
    rows = list(csv.DictReader(io.StringIO(export.get_data(as_text=True))))
    assert [row['actor'] for row in rows] == ['greenguys']
    assert any(entry['route'] == url for entry in client.get(url + '?poll=1').json['entries'])


def test_live_log_imports_recent_errors_from_the_previous_log(client, login, tmp_path):
    now = datetime.now(timezone.utc)
    with closing(sqlite3.connect(tmp_path / 'api-errors.sqlite3')) as db, db:
        db.execute('''CREATE TABLE api_errors (id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL,
            reference TEXT NOT NULL, code TEXT NOT NULL, method TEXT NOT NULL, route TEXT NOT NULL,
            status INTEGER NOT NULL, detail TEXT NOT NULL)''')
        db.executemany('INSERT INTO api_errors VALUES (?, ?, ?, ?, ?, ?, ?, ?)', [
            (1, now.isoformat(), 'LEGACY1', 'RECORD_SAVE_FAILED', 'POST', '/api/record/<category>', 503, 'SQLAlchemyError'),
            (2, (now - timedelta(days=31)).isoformat(), 'EXPIRED', 'RECORD_SAVE_FAILED', 'POST', '/api/record/<category>', 503, ''),
        ])
    assert login('inter-school-admin').status_code == 200
    url = '/api/interschool/server-log?failures=1&poll=1'
    assert [entry['reference'] for entry in client.get(url).json['entries']] == ['LEGACY1']
    assert [entry['reference'] for entry in client.get(url).json['entries']] == ['LEGACY1']
