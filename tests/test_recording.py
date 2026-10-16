import csv
import io
import uuid

import pytest

from src.routes.golden_plate_recorder_db.db import (
    Session as SessionModel, SessionRecord, SessionTicketEvent, Student, db_session,
)
from src.routes.golden_plate_recorder_db.storage import hydrate_session_from_db


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
    assert client.post('/api/record/dirty', json={}).status_code == 200
    assert client.post('/api/record/faculty', json={'input_value': 'Dr Jane Smith'}).status_code == 200

    status = client.get('/api/session/status')
    assert status.status_code == 200
    data = status.get_json()
    assert data['clean_count'] == 1
    assert data['red_count'] == 1
    assert data['dirty_count'] == 1
    assert data['faculty_clean_count'] == 1
    assert data['combined_dirty_count'] == 2



@pytest.mark.parametrize('category,count_field', [
    ('clean', 'clean_count'), ('dirty', 'dirty_count'),
    ('red', 'red_count'), ('faculty', 'faculty_clean_count'),
])
def test_blank_plates_are_repeatable_counts_without_identity(client, login, category, count_field):
    login()
    session_id = client.post('/api/session/create', json={'session_name': f'optional-{uuid.uuid4().hex}'}).get_json()['session_id']
    students_before = db_session.query(Student).count()
    for payload in [{}, {'input_value': ' \t '}, {'input_value': ''}]:
        response = client.post(f'/api/record/{category}', json=payload)
        assert response.status_code == 200
        assert response.get_json()['is_count_only'] is True

    status = client.get('/api/session/status').get_json()
    assert status[count_field] == 3
    assert status['total_recorded'] == 3
    db_sess = db_session.query(SessionModel).filter_by(id=session_id).one()
    assert db_sess.total_records == 3
    assert (db_sess.total_clean if category in ['clean', 'faculty'] else db_sess.total_dirty) == 3
    records = db_session.query(SessionRecord).filter_by(session_id=session_id).all()
    assert len(records) == len({record.dedupe_key for record in records}) == 3
    assert all(not (record.student_id or record.preferred_name or record.last_name) for record in records)
    assert db_session.query(Student).count() == students_before
    assert db_session.query(SessionTicketEvent).filter_by(session_id=session_id).count() == 0
    history = client.get('/api/session/scan-history').get_json()['scan_history']
    assert len(history) == 3
    assert all(row['is_count_only'] and '(count only)' in row['name'] for row in history)

    # Simulate a server restart: no anonymous UUID can become a student name/key.
    restored = hydrate_session_from_db(session_id)
    records_key = 'faculty_clean_records' if category == 'faculty' else f'{category}_records'
    assert len(restored[records_key]) == 3
    assert all(row['is_count_only'] and not row.get('student_key') for row in restored[records_key])
    export = list(csv.DictReader(io.StringIO(client.get('/api/export/csv/detailed').get_data(as_text=True))))
    assert len(export) == 3
    assert all(row['Category'] == category.upper() and '(count only)' in row['Preferred'] for row in export)


@pytest.mark.parametrize('identity', [
    {'input_value': '123'},
    {'input_value': 'John Doe'},
    {'input_value': '', 'student_id': '123', 'student_key': 'id:123'},
])
def test_named_dirty_plate_preserves_student_and_house(client, login, identity):
    login()
    assert upload_csv(client).status_code == 200
    session_id = client.post('/api/session/create', json={'session_name': f'optional-{uuid.uuid4().hex}'}).get_json()['session_id']
    assert client.post('/api/record/dirty', json={}).status_code == 200
    response = client.post('/api/record/dirty', json=identity)
    assert response.status_code == 200
    assert response.get_json()['preferred_name'] == 'John'
    assert response.get_json()['student_id'] == '123'
    assert client.get('/api/session/status').get_json()['dirty_count'] == 2
    record = db_session.query(SessionRecord).filter_by(session_id=session_id, dedupe_key='id:123').one()
    assert record.student_id and record.preferred_name == 'John'
    assert db_session.query(SessionTicketEvent).filter_by(session_id=session_id).count() == 0
    house = client.get(f'/api/session/{session_id}/house-stats').get_json()['house_stats'][0]
    assert house['house'] == 'Barn' and house['dirty_count'] == house['total_count'] == 1
    assert house['clean_rate'] == 0
    history = client.get('/api/session/scan-history').get_json()['scan_history']
    assert any(row['name'] == 'John Doe' and not row['is_count_only'] for row in history)
    restored = hydrate_session_from_db(session_id)
    assert len(restored['dirty_records']) == restored['dirty_count'] == 2
    assert any(row.get('preferred_name') == 'John' for row in restored['dirty_records'])
    assert client.post('/api/record/dirty', json=identity).status_code == 409
    assert client.post('/api/record/clean', json={'input_value': '123'}).status_code == 409
    export = client.get('/api/export/csv/detailed').get_data(as_text=True)
    assert 'John' in export and 'Doe' in export and '(count only)' in export


def test_named_manual_dirty_survives_rehydration(client, login):
    login()
    session_id = client.post('/api/session/create', json={'session_name': f'optional-{uuid.uuid4().hex}'}).get_json()['session_id']
    name = f'Manual {uuid.uuid4().hex}'
    assert client.post('/api/record/dirty', json={'input_value': name}).status_code == 200
    restored = hydrate_session_from_db(session_id)
    record = restored['dirty_records'][0]
    assert record['preferred_name'] == 'Manual'
    assert record['last_name'] == name.split()[1]


def test_anonymous_faculty_not_selected_for_draw(client, login):
    login()
    session_id = client.post('/api/session/create', json={'session_name': f'optional-{uuid.uuid4().hex}'}).get_json()['session_id']
    assert client.post('/api/record/faculty', json={}).status_code == 200
    assert client.get(f'/api/session/{session_id}/faculty/pick').status_code == 400
    assert client.post('/api/record/faculty', json={'input_value': 'Alex Morgan'}).status_code == 200
    assert client.post('/api/record/faculty', json={'input_value': 'Alex Morgan'}).status_code == 409
    result = client.get(f'/api/session/{session_id}/faculty/pick')
    assert result.status_code == 200
    assert result.get_json()['faculty']['display_name'] == 'Alex Morgan'


def test_count_only_records_do_not_change_existing_tickets(client, login):
    from src.routes.golden_plate_recorder_db.draw_db import get_student_ticket_balance

    login()
    upload_csv(client)
    session_id = client.post('/api/session/create', json={'session_name': f'optional-{uuid.uuid4().hex}'}).get_json()['session_id']
    assert client.post('/api/record/clean', json={'input_value': '123'}).status_code == 200
    student = db_session.query(Student).filter_by(student_identifier='123').first()
    assert get_student_ticket_balance(student.id) == 1
    for category in ['clean', 'dirty', 'red', 'faculty']:
        assert client.post(f'/api/record/{category}', json={}).status_code == 200
        assert get_student_ticket_balance(student.id) == 1
    assert db_session.query(SessionTicketEvent).filter_by(session_id=session_id).count() == 1
    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert len(summary['candidates']) == 1
    assert summary['candidates'][0]['student_identifier'] == '123'
    assert summary['candidates'][0]['tickets'] == 1


@pytest.mark.parametrize('category,payload', [
    ('clean', {'input_value': '123'}),
    ('dirty', {}),
    ('red', {'input_value': '456'}),
    ('faculty', {'input_value': 'Faculty Retry'}),
])
def test_failed_save_does_not_leave_phantom_duplicate_or_counts(client, login, monkeypatch, category, payload):
    from sqlalchemy.exc import SQLAlchemyError
    from src.routes.golden_plate_recorder_db.storage import get_session_entry

    login()
    upload_csv(client)
    identifier = client.post('/api/session/create', json={'session_name': f'retry-{uuid.uuid4().hex}'}).get_json()['session_id']
    with monkeypatch.context() as patch:
        patch.setattr(db_session, 'commit', lambda: (_ for _ in ()).throw(SQLAlchemyError('simulated save failure')))
        response = client.post(f'/api/record/{category}', json=payload)
    assert response.status_code == 503
    assert response.get_json()['error'] == 'record_save_failed'
    assert db_session.query(SessionRecord).filter_by(session_id=identifier).count() == 0
    info = get_session_entry(identifier)
    assert not info['scan_history']
    assert info['dirty_count'] == 0
    assert client.get('/api/session/status').get_json()['total_recorded'] == 0
    assert client.post(f'/api/record/{category}', json=payload).status_code == 200
    assert db_session.query(SessionRecord).filter_by(session_id=identifier).count() == 1
    assert client.get('/api/session/status').get_json()['total_recorded'] == 1
    if payload:
        duplicate = client.post(f'/api/record/{category}', json=payload)
        assert duplicate.status_code == 409
        assert duplicate.get_json()['existing_category'] == category
        assert 'No new plate was added' in duplicate.get_json()['message']


def test_lookup_refresh_failure_does_not_report_a_committed_plate_as_failed(client, login, monkeypatch):
    from src.routes.golden_plate_recorder_db import session_routes

    login()
    client.post('/api/session/create', json={'session_name': f'cache-failure-{uuid.uuid4().hex}'})
    with monkeypatch.context() as patch:
        patch.setattr(session_routes, 'update_student_lookup', lambda: (_ for _ in ()).throw(RuntimeError('cache failed')))
        response = client.post('/api/record/clean', json={'student_id': f'new-{uuid.uuid4().hex}', 'preferred_name': 'Manual', 'last_name': 'Student'})
    assert response.status_code == 200
    assert response.get_json()['is_manual_entry'] is True
    assert client.get('/api/session/status').get_json()['total_recorded'] == 1


def test_unmatched_student_id_stays_manual_in_later_sessions(client, login):
    login()
    student_id = f'unmatched-{uuid.uuid4().hex}'
    for _ in range(2):
        client.post('/api/session/create', json={'session_name': f'manual-{uuid.uuid4().hex}'})
        response = client.post('/api/record/dirty', json={'student_id': student_id, 'preferred_name': 'Manual', 'last_name': 'Student'})
        assert response.status_code == 200
        assert response.get_json()['is_manual_entry'] is True


def test_duplicate_checks_ignore_uncommitted_cache_entries(client, login):
    from src.routes.golden_plate_recorder_db.storage import get_session_entry

    login()
    upload_csv(client)
    identifier = client.post('/api/session/create', json={'session_name': f'cached-{uuid.uuid4().hex}'}).get_json()['session_id']
    cached = get_session_entry(identifier)
    cached['clean_records'].append({'student_id': '123', 'student_key': 'id:123', 'preferred_name': 'John', 'last_name': 'Doe'})
    assert client.post('/api/record/dirty', json={'input_value': '123'}).status_code == 200
    cached['clean_records'].clear()
    # Even an empty cache cannot hide the committed plate or its category.
    cached['dirty_records'].clear()
    response = client.post('/api/record/red', json={'input_value': '123'})
    assert response.status_code == 409
    assert response.get_json()['existing_category'] == 'dirty'
