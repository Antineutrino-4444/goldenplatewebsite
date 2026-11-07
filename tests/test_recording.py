import csv
import io
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier

import pytest
from sqlalchemy import event

from src.routes.golden_plate_recorder_db.db import (
    DraftPool, INTERSCHOOL_SCHOOL_ID, School, Session as SessionModel, SessionRecord,
    SessionTicketEvent, Student, db_session, engine,
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


@pytest.mark.parametrize('category,expected_balance', [('clean', 8), ('red', 0)])
def test_recording_reuses_legacy_ticket_row_with_stale_school(client, login, monkeypatch, category, expected_balance):
    from sqlalchemy.exc import SQLAlchemyError

    login()
    assert upload_csv(client).status_code == 200
    session_id = client.post('/api/session/create', json={
        'session_name': f'legacy-ticket-{uuid.uuid4().hex}',
    }).json['session_id']
    session_school = db_session.get(SessionModel, session_id).school_id
    student = db_session.query(Student).filter_by(
        student_identifier='123', school_id=session_school, is_active=1,
    ).one()
    student_id, school_id = student.id, student.school_id
    pool = DraftPool(school_id=INTERSCHOOL_SCHOOL_ID, student_id=student_id, ticket_number=7)
    other_student = db_session.query(Student).filter_by(student_identifier='456', school_id=school_id).one()
    # Public roster IDs may repeat across schools; internal IDs must remain separate.
    other_school = School(id=uuid.uuid4().hex, slug=uuid.uuid4().hex, name='Separate school')
    db_session.add(other_school)
    db_session.flush()
    other_school_student = Student(school_id=other_school.id, student_identifier='123',
                                   preferred_name='Other', last_name='School')
    db_session.add(other_school_student)
    db_session.flush()
    untouched = [
        DraftPool(school_id=school_id, student_id=other_student.id, ticket_number=12),
        DraftPool(school_id=other_school.id, student_id=other_school_student.id, ticket_number=30),
    ]
    db_session.add_all([pool, *untouched])
    db_session.commit()
    pool_id = pool.id
    untouched_balances = {row.id: (row.school_id, row.student_id, row.ticket_number) for row in untouched}

    # Older production databases enforce UNIQUE(student_id), even though the
    # ORM now declares UNIQUE(school_id, student_id).
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE UNIQUE INDEX test_legacy_pool_student ON draft_pool (student_id)')
    try:
        assert db_session.query(SessionRecord).filter_by(session_id=session_id).count() == 0
        # A failure after repairing the school must roll back the repair, plate,
        # ticket event and balance together, so a subsequent retry remains safe.
        with monkeypatch.context() as patch:
            def fail_commit():
                raise SQLAlchemyError('simulated commit failure')
            patch.setattr(db_session, 'commit', fail_commit)
            assert client.post(f'/api/record/{category}', json={'input_value': '123'}).status_code == 503
        db_session.expire_all()
        failed_pool = db_session.get(DraftPool, pool_id)
        assert (failed_pool.school_id, failed_pool.ticket_number) == (INTERSCHOOL_SCHOOL_ID, 7)
        assert db_session.query(SessionRecord).filter_by(session_id=session_id).count() == 0
        assert db_session.query(SessionTicketEvent).filter_by(session_id=session_id).count() == 0
        assert client.get('/api/session/status').json['total_recorded'] == 0

        response = client.post(f'/api/record/{category}', json={'input_value': '123'})
        assert response.status_code == 200, response.json
        db_session.expire_all()
        saved_pool = db_session.query(DraftPool).filter_by(student_id=student_id).one()
        assert saved_pool.id == pool_id
        assert saved_pool.school_id == school_id
        assert saved_pool.ticket_number == expected_balance
        record = db_session.query(SessionRecord).filter_by(session_id=session_id).one()
        assert record.student_id == student_id and record.category == category
        ticket_event = db_session.query(SessionTicketEvent).filter_by(session_record_id=record.id).one()
        assert ticket_event.ticket_balance_after == expected_balance
        assert ticket_event.tickets_delta == (1 if category == 'clean' else -7)
        assert client.get('/api/session/status').json['total_recorded'] == 1
        assert client.post(f'/api/record/{category}', json={'input_value': '123'}).status_code == 409
        db_session.expire_all()
        assert db_session.get(DraftPool, pool_id).ticket_number == expected_balance
        for row_id, expected in untouched_balances.items():
            row = db_session.get(DraftPool, row_id)
            assert (row.school_id, row.student_id, row.ticket_number) == expected
            assert db_session.query(SessionTicketEvent).filter_by(student_id=row.student_id).count() == 0
    finally:
        db_session.rollback()
        with engine.begin() as connection:
            connection.exec_driver_sql('DROP INDEX test_legacy_pool_student')


def test_ticket_update_rejects_a_session_from_another_school(client, login):
    from src.routes.golden_plate_recorder_db.draw_db import update_draft_pool

    login()
    session_id = client.post('/api/session/create', json={
        'session_name': f'wrong-school-ticket-{uuid.uuid4().hex}',
    }).json['session_id']
    student = Student(school_id=INTERSCHOOL_SCHOOL_ID, student_identifier=uuid.uuid4().hex,
                      preferred_name='Separate', last_name='School')
    db_session.add(student)
    db_session.flush()
    pool = DraftPool(school_id=student.school_id, student_id=student.id, ticket_number=9)
    db_session.add(pool)
    db_session.commit()
    with pytest.raises(ValueError, match='same school'):
        update_draft_pool(student.id, 10, session_id=session_id)
    db_session.commit()
    db_session.expire_all()
    assert pool.school_id == INTERSCHOOL_SCHOOL_ID
    assert pool.ticket_number == 9
    assert pool.session_id is None


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


def test_simultaneous_clean_submissions_save_one_plate_and_ticket(client, login, monkeypatch):
    from src.main import app
    from src.routes.golden_plate_recorder_db import session_routes
    from src.routes.golden_plate_recorder_db.draw_db import get_student_ticket_balance

    login()
    upload_csv(client)
    session_id = client.post('/api/session/create', json={'session_name': 'concurrent-clean'}).get_json()['session_id']
    with client.session_transaction() as browser_session:
        browser_state = dict(browser_session)

    both_passed_duplicate_check = Barrier(2, timeout=10)
    prepare_roster = session_routes.prepare_recording_roster

    def sync_before_insert(meal):
        prepare_roster(meal)
        both_passed_duplicate_check.wait()

    def submit():
        browser = app.test_client()
        with browser.session_transaction() as browser_session:
            browser_session.update(browser_state)
        return browser.post('/api/record/clean', json={'input_value': 'John Doe (123)'})

    monkeypatch.setattr(session_routes, 'prepare_recording_roster', sync_before_insert)
    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [pool.submit(submit) for _ in range(2)]
        responses = sorted((pending.result() for pending in requests), key=lambda response: response.status_code)

    assert [response.status_code for response in responses] == [200, 409]
    duplicate = responses[1].get_json()
    assert duplicate['error'] == 'duplicate'
    assert duplicate['existing_category'] == 'clean'
    assert 'No new plate was added' in duplicate['message']
    record = db_session.query(SessionRecord).filter_by(session_id=session_id).one()
    assert db_session.query(SessionTicketEvent).filter_by(session_id=session_id, session_record_id=record.id).count() == 1
    assert get_student_ticket_balance(record.student_id) == 1
    assert client.get('/api/session/status').get_json()['clean_count'] == 1


@pytest.mark.parametrize('release_lock', [True, False])
def test_fast_sqlite_lock_failure_retries_once(client, login, monkeypatch, release_lock):
    from src.routes.golden_plate_recorder_db import session_routes

    login()
    upload_csv(client)
    session_id = client.post('/api/session/create', json={'session_name': f'locked-{release_lock}'}).get_json()['session_id']
    retries = []

    def skip_sqlite_wait(connection, *_):
        connection.execute('PRAGMA busy_timeout=0')

    with closing(sqlite3.connect(engine.url.database)) as writer:
        def retry_delay(seconds):
            retries.append(seconds)
            if release_lock:
                writer.rollback()

        monkeypatch.setattr(session_routes, 'sleep', retry_delay)
        monkeypatch.setattr(session_routes, 'monotonic', lambda: 0)
        event.listen(engine, 'checkout', skip_sqlite_wait)
        try:
            writer.execute('BEGIN IMMEDIATE')
            response = client.post('/api/record/clean', json={'input_value': '123'})
        finally:
            event.remove(engine, 'checkout', skip_sqlite_wait)
            engine.dispose()

    assert len(retries) == 1
    assert db_session.query(SessionRecord).filter_by(session_id=session_id).count() == int(release_lock)
    assert db_session.query(SessionTicketEvent).filter_by(session_id=session_id).count() == int(release_lock)
    if release_lock:
        assert response.status_code == 200
    else:
        assert response.status_code == 503
        assert response.get_json()['error'] == 'record_save_failed'
        assert 'database is busy' in response.get_json()['message']


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
