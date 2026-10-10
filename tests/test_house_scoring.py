import io
import uuid

import pytest
from sqlalchemy import create_engine, text

from src.routes.golden_plate_recorder_db import db as database
from src.routes.golden_plate_recorder_db.db import School, Session, SessionRecord, Student, db_session
from src.routes.golden_plate_recorder_db.house_scoring import house_score_settings
from src.routes.golden_plate_recorder_db.users import create_user_record


DEFAULTS = {'clean_points': 2, 'dirty_penalty': 2, 'very_dirty_penalty': 10}
SETTINGS_URL = '/api/superadmin/house-score-settings'


@pytest.fixture
def score_school(client):
    client.get('/api/auth/status')
    suffix = uuid.uuid4().hex
    school = School(id=f'score-{suffix}', name='Score Academy', slug=f'score-{suffix}')
    db_session.add(school)
    db_session.commit()
    admin = create_user_record(f'score-admin-{suffix}', 'score-test-password', 'Score Admin',
                               role='superadmin', school_id=school.id)
    assert client.post('/api/auth/login', json={
        'username': admin.username, 'password': 'score-test-password',
    }).status_code == 200
    return school


def create_session(client):
    response = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex})
    assert response.status_code == 200
    return response.get_json()['session_id']


def record_roster(client, entries):
    roster = 'Student ID,Last,Preferred,House\n'
    for identifier, house, _ in entries:
        roster += f'{identifier},Student,Name{identifier},{house}\n'
    assert client.post('/api/csv/upload', data={
        'file': (io.BytesIO(roster.encode()), 'score-roster.csv'),
    }).status_code == 200
    for identifier, _, category in entries:
        assert client.post(f'/api/record/{category}', json={'input_value': identifier}).status_code == 200


def test_scores_count_only_missing_houses_and_negative_ranking(client, score_school):
    session_id = create_session(client)
    record_roster(client, [
        ('8101', 'A', 'clean'), ('8102', 'A', 'clean'), ('8103', 'A', 'clean'),
        ('8104', 'A', 'red'), ('8105', 'B', 'clean'), ('8106', 'C', 'dirty'),
        ('8107', 'D', 'red'), ('8108', '', 'dirty'),
    ])
    # Every count category ignores even a caller-supplied house.
    for category in ['clean', 'dirty', 'red', 'faculty']:
        assert client.post(f'/api/record/{category}', json={'house': 'B'}).status_code == 200
    anonymous = db_session.query(SessionRecord).filter_by(session_id=session_id).filter(
        SessionRecord.dedupe_key.like('count:%'),
    ).all()
    assert len(anonymous) == 4 and all(not row.house for row in anonymous)
    # Defensive coverage for malformed historical anonymous records.
    anonymous[0].house = 'B'
    faculty = SessionRecord(school_id=score_school.id, session_id=session_id, category='faculty',
                            preferred_name='Teacher', house='B', dedupe_key='faculty:test',
                            recorded_by='test')
    db_session.add(faculty)
    db_session.commit()
    data = client.get(f'/api/session/{session_id}/house-stats').get_json()
    assert data['score_settings'] == DEFAULTS
    assert data['total_records_with_house'] == 7
    assert [(row['house'], row['score']) for row in data['house_stats']] == [
        ('B', 2), ('C', -2), ('A', -4), ('D', -10),
    ]
    a = next(row for row in data['house_stats'] if row['house'] == 'A')
    assert a['total_count'] == 4 and a['clean_rate'] == 75
    assert a['clean_count'] == 3 and a['red_count'] == 1 and a['dirty_count'] == 0


def test_setting_changes_recalculate_existing_archived_and_active_sessions(client, score_school):
    first_id = create_session(client)
    record_roster(client, [('8201', 'A', 'clean'), ('8202', 'A', 'dirty'), ('8203', 'A', 'red')])
    db_session.query(Session).filter_by(id=first_id).update({'status': 'archived'})
    db_session.commit()
    second_id = create_session(client)
    assert client.post('/api/record/clean', json={'input_value': '8201'}).status_code == 200
    assert client.get(f'/api/session/{first_id}/house-stats').get_json()['house_stats'][0]['score'] == -10
    settings = {'clean_points': 20, 'dirty_penalty': 0, 'very_dirty_penalty': 0}
    assert client.put(SETTINGS_URL, json=settings).get_json()['score_settings'] == settings
    # Fresh DB loads verify persistence, then both sessions use the new weights.
    db_session.remove()
    assert client.get(SETTINGS_URL).get_json()['score_settings'] == settings
    for session_id in [first_id, second_id]:
        assert client.get(f'/api/session/{session_id}/house-stats').get_json()['house_stats'][0]['score'] == 20
    zero = dict.fromkeys(DEFAULTS, 0)
    assert client.put(SETTINGS_URL, json=zero).status_code == 200
    assert client.get(f'/api/session/{first_id}/house-stats').get_json()['house_stats'][0]['score'] == 0


@pytest.mark.parametrize('invalid', [-1, 21, 2.5, True, '2', None, [], {}])
def test_invalid_values_are_rejected_atomically(client, score_school, invalid):
    for field in DEFAULTS:
        assert client.put(SETTINGS_URL, json={**DEFAULTS, field: invalid}).status_code == 400
        assert house_score_settings(score_school.id) == DEFAULTS


@pytest.mark.parametrize('payload', [{}, [], ['invalid'], {'clean_points': 5}])
def test_incomplete_or_non_object_settings_are_rejected(client, score_school, payload):
    assert client.put(SETTINGS_URL, json=payload).status_code == 400
    assert house_score_settings(score_school.id) == DEFAULTS


@pytest.mark.parametrize('role', ['user', 'admin', 'inter_school'])
def test_only_superadmins_can_read_or_change_settings(client, score_school, role):
    account = create_user_record(f'score-{role}-{uuid.uuid4().hex}', 'score-test-password', 'Other Role',
                                 role=role, school_id=score_school.id)
    assert client.post('/api/auth/login', json={
        'username': account.username, 'password': 'score-test-password',
    }).status_code == 200
    assert client.get(SETTINGS_URL).status_code == 403
    assert client.put(SETTINGS_URL, json=DEFAULTS).status_code == 403
    assert house_score_settings(score_school.id) == DEFAULTS


def test_settings_are_scoped_to_authenticated_school_and_guests_can_view_scores(client, score_school):
    other = School(id=uuid.uuid4().hex, name='Other School', slug=uuid.uuid4().hex)
    db_session.add(other)
    db_session.commit()
    other_id = other.id
    session_id = create_session(client)
    record_roster(client, [('8301', 'A', 'clean')])
    changed = {'clean_points': 0, 'dirty_penalty': 20, 'very_dirty_penalty': 20}
    assert client.put(SETTINGS_URL, json={**changed, 'school_id': other_id}).status_code == 200
    assert house_score_settings(score_school.id) == changed
    assert house_score_settings(other_id) == DEFAULTS
    other_session = Session(school_id=other_id, session_name=uuid.uuid4().hex, created_by='test')
    db_session.add(other_session)
    db_session.commit()
    assert client.get(f'/api/session/{other_session.id}/house-stats').status_code == 404
    client.post('/api/auth/logout')
    assert client.get(SETTINGS_URL).status_code == 401
    assert client.put(SETTINGS_URL, json=DEFAULTS).status_code == 401
    assert client.post('/api/auth/guest', json={'school_slug': score_school.slug}).status_code == 200
    assert client.get(SETTINGS_URL).status_code == 401
    assert client.put(SETTINGS_URL, json=DEFAULTS).status_code == 401
    response = client.get(f'/api/session/{session_id}/house-stats')
    assert response.status_code == 200
    assert response.get_json()['house_stats'][0]['score'] == 0


def test_historical_record_house_survives_missing_roster_and_linked_house_fallback(client, score_school):
    session_id = create_session(client)
    record_roster(client, [('8401', 'Stored House', 'clean')])
    # Historical records can still rank if a future roster loses house data.
    student = db_session.query(Student).filter_by(school_id=score_school.id, student_identifier='8401').one()
    student.house = ''
    db_session.commit()
    assert client.get(f'/api/session/{session_id}/house-stats').get_json()['house_stats'][0]['score'] == 2
    # If the record has no house, use the linked student's house.
    student = db_session.query(Student).filter_by(school_id=score_school.id, student_identifier='8401').one()
    student.house = 'Linked House'
    record = db_session.query(SessionRecord).filter_by(session_id=session_id).one()
    record.house = ''
    db_session.commit()
    data = client.get(f'/api/session/{session_id}/house-stats').get_json()
    assert [(row['house'], row['score']) for row in data['house_stats']] == [('Linked House', 2)]
    student = db_session.query(Student).filter_by(school_id=score_school.id, student_identifier='8401').one()
    student.house = ''
    db_session.commit()
    data = client.get(f'/api/session/{session_id}/house-stats').get_json()
    assert data['has_house_data'] is False and data['house_stats'] == []


def test_existing_database_upgrade_adds_defaults_and_preserves_saved_weights(monkeypatch):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    columns = ['house_clean_points', 'house_dirty_penalty', 'house_very_dirty_penalty']
    with engine.begin() as connection:
        connection.execute(School.__table__.insert().values(id='old-school', name='Old School', slug='old-school'))
        for column in columns:
            connection.execute(text(f'ALTER TABLE schools DROP COLUMN {column}'))
    monkeypatch.setattr(database, 'engine', engine)
    try:
        database._bootstrap_database()
        with engine.begin() as connection:
            assert connection.execute(text(
                'SELECT house_clean_points, house_dirty_penalty, house_very_dirty_penalty '
                "FROM schools WHERE id = 'old-school'"
            )).one() == (2, 2, 10)
            connection.execute(text("UPDATE schools SET house_clean_points = 7 WHERE id = 'old-school'"))
        database._bootstrap_database()
        with engine.connect() as connection:
            assert connection.execute(text("SELECT house_clean_points FROM schools WHERE id = 'old-school'")).scalar_one() == 7
    finally:
        engine.dispose()
