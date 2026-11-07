import io
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

from src.routes.golden_plate_recorder_db import db as database
from src.routes.golden_plate_recorder_db.db import (
    School, Session, SessionRecord, SessionTicketEvent, Student, db_session,
)
from src.routes.golden_plate_recorder_db.storage import hydrate_session_from_db
from src.routes.golden_plate_recorder_db.users import create_user_record


SETTINGS_URL = '/api/superadmin/recording-settings'


@pytest.fixture
def recording_school(client):
    client.get('/api/auth/status')
    suffix = uuid.uuid4().hex
    school = School(id=suffix, name='Recording Academy', slug=suffix)
    db_session.add(school)
    db_session.commit()
    account = create_user_record(f'recording-{suffix}', 'recording-password', 'Recording Admin',
                                 role='superadmin', school_id=school.id)
    assert client.post('/api/auth/login', json={
        'username': account.username, 'password': 'recording-password',
    }).status_code == 200
    return school


def set_name_input(client, enabled, **extra):
    return client.put(SETTINGS_URL, json={'dirty_plate_name_input_enabled': enabled, **extra})


def test_setting_defaults_persists_and_only_changes_own_school(client, recording_school):
    school_id = recording_school.id
    other = School(id=uuid.uuid4().hex, name='Other School', slug=uuid.uuid4().hex)
    db_session.add(other)
    db_session.commit()
    other_id = other.id
    assert client.get('/api/auth/status').get_json()['user']['school']['dirty_plate_name_input_enabled'] is True
    response = set_name_input(client, False, school_id=other_id)
    assert response.status_code == 200
    assert response.get_json()['dirty_plate_name_input_enabled'] is False
    db_session.remove()
    assert db_session.get(School, school_id).dirty_plate_name_input_enabled == 0
    assert db_session.get(School, other_id).dirty_plate_name_input_enabled == 1
    assert client.get('/api/auth/status').get_json()['user']['school']['dirty_plate_name_input_enabled'] is False
    assert set_name_input(client, True).status_code == 200
    assert client.get('/api/auth/status').get_json()['user']['school']['dirty_plate_name_input_enabled'] is True


@pytest.mark.parametrize('role', ['user', 'admin', 'inter_school'])
def test_only_superadmins_can_change_recording_settings(client, recording_school, role):
    account = create_user_record(f'recording-{role}-{uuid.uuid4().hex}', 'recording-password', 'Recorder',
                                 role=role, school_id=recording_school.id)
    response = client.post('/api/auth/login', json={'username': account.username, 'password': 'recording-password'})
    assert response.status_code == 200
    assert response.get_json()['user']['school']['dirty_plate_name_input_enabled'] is True
    assert set_name_input(client, False).status_code == 403
    assert db_session.get(School, recording_school.id).dirty_plate_name_input_enabled == 1


@pytest.mark.parametrize('guest', [False, True])
def test_recording_settings_require_account_login(client, recording_school, guest):
    slug = recording_school.slug
    client.post('/api/auth/logout')
    if guest:
        assert client.post('/api/auth/guest', json={'school_slug': slug}).status_code == 200
    assert set_name_input(client, False).status_code == 401


@pytest.mark.parametrize('payload', [
    {}, [], ['invalid'], {'dirty_plate_name_input_enabled': None},
    {'dirty_plate_name_input_enabled': 0}, {'dirty_plate_name_input_enabled': 1},
    {'dirty_plate_name_input_enabled': 'false'},
])
def test_recording_settings_require_boolean(client, recording_school, payload):
    assert client.put(SETTINGS_URL, json=payload).status_code == 400
    assert db_session.get(School, recording_school.id).dirty_plate_name_input_enabled == 1


def test_count_only_mode_ignores_identity_and_preserves_other_categories_and_history(client, recording_school):
    roster = 'Student ID,Last,Preferred,House\n987123,Doe,John,Barn\n987456,Roe,Jane,Hall\n'
    assert client.post('/api/csv/upload', data={
        'file': (io.BytesIO(roster.encode()), 'students.csv'),
    }).status_code == 200
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    # An existing named dirty plate stays named when the setting changes.
    assert client.post('/api/record/dirty', json={'input_value': '987123'}).status_code == 200
    students_before = db_session.query(Student).filter_by(school_id=recording_school.id).count()
    assert set_name_input(client, False).status_code == 200
    # Include stale tabs and caller-supplied selections: all become unnamed counts.
    for payload in [{}, {'input_value': '987123'}, {
        'input_value': 'New Student', 'student_id': '987456', 'student_key': 'id:987456',
        'preferred_name': 'New', 'last_name': 'Student', 'house': 'Hall',
    }]:
        response = client.post('/api/record/dirty', json=payload)
        assert response.status_code == 200
        assert response.get_json()['is_count_only'] is True
    assert db_session.query(Student).filter_by(school_id=recording_school.id).count() == students_before
    assert db_session.query(SessionTicketEvent).filter_by(session_id=session_id).count() == 0
    counts = db_session.query(SessionRecord).filter(
        SessionRecord.session_id == session_id, SessionRecord.dedupe_key.like('count:dirty:%'),
    ).all()
    assert len(counts) == 3
    assert all(not row.student_id and not row.preferred_name and not row.house for row in counts)
    # Anonymous counts do not claim a student or prevent a later named record.
    assert client.post('/api/record/red', json={'input_value': '987456'}).get_json()['student_id'] == '987456'
    assert set_name_input(client, True).status_code == 200
    assert client.post('/api/record/dirty', json={'input_value': '987123'}).status_code == 409
    assert client.post('/api/record/dirty', json={'input_value': '987456'}).status_code == 409
    assert client.post('/api/record/dirty', json={'input_value': 'New Student'}).get_json()['is_manual_entry'] is True
    assert set_name_input(client, False).status_code == 200
    assert client.post('/api/record/clean', json={'input_value': 'Another Student'}).get_json()['preferred_name'] == 'Another'
    assert client.post('/api/record/faculty', json={'input_value': 'Faculty Member'}).get_json()['preferred_name'] == 'Faculty'
    status = client.get('/api/session/status').get_json()
    assert status['dirty_count'] == 5 and status['red_count'] == 1
    assert status['clean_count'] == 1 and status['faculty_clean_count'] == 1
    restored = hydrate_session_from_db(session_id)
    assert len(restored['dirty_records']) == restored['dirty_count'] == 5
    assert sum(bool(row.get('is_count_only')) for row in restored['dirty_records']) == 3
    assert db_session.get(Session, session_id).total_records == 8


def test_existing_database_adds_default_without_resetting_saved_choice(monkeypatch):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(School.__table__.insert().values(id='old-school', name='Old School', slug='old-school'))
        connection.execute(text('ALTER TABLE schools DROP COLUMN dirty_plate_name_input_enabled'))
    monkeypatch.setattr(database, 'engine', engine)
    database._bootstrap_database()
    assert 'dirty_plate_name_input_enabled' in {col['name'] for col in inspect(engine).get_columns('schools')}
    with engine.begin() as connection:
        assert connection.execute(text("SELECT dirty_plate_name_input_enabled FROM schools WHERE id = 'old-school'")).scalar_one() == 1
        connection.execute(text("UPDATE schools SET dirty_plate_name_input_enabled = 0 WHERE id = 'old-school'"))
    database._bootstrap_database()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT dirty_plate_name_input_enabled FROM schools WHERE id = 'old-school'")).scalar_one() == 0
    engine.dispose()
