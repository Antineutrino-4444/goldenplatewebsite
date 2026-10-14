import io
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

from src.routes.golden_plate_recorder_db import db as database, guest_privacy
from src.routes.golden_plate_recorder_db.db import (
    GuestStudentAlias, School, Session as SessionModel, SessionRecord, Student, db_session,
)
from src.routes.golden_plate_recorder_db.storage import hydrate_session_from_db, session_data
from src.routes.golden_plate_recorder_db.users import create_user_record


@pytest.fixture
def privacy_school(client):
    client.get('/api/auth/status')
    suffix = uuid.uuid4().hex
    school = School(id=f'privacy-{suffix}', name='Privacy Academy', slug=f'privacy-{suffix}')
    db_session.add(school)
    db_session.commit()
    admin = create_user_record(f'privacy-{suffix}', 'privacy-password', 'Private Administrator',
                               role='admin', school_id=school.id)
    sign_in(client, admin)
    # Identical real names must still produce distinct aliases.
    roster = ('Student ID,Last,Preferred,Grade,Advisor,House,Clan\n'
              'private-101,PrivateSurname,PrivateName,9,PrivateAdvisor,Barn,PrivateClan\n'
              'private-102,PrivateSurname,PrivateName,10,PrivateAdvisor,Hall,PrivateClan\n')
    assert client.post('/api/csv/upload', data={
        'file': (io.BytesIO(roster.encode()), 'PrivateRoster.csv'),
    }).status_code == 200
    sessions = []
    for _ in range(2):
        result = client.post('/api/session/create', json={'session_name': f'PrivateTitle {uuid.uuid4().hex}'})
        assert result.status_code == 200
        sessions.append(result.get_json()['session_id'])
        for identifier in ('private-101', 'private-102'):
            assert client.post('/api/record/clean', json={'input_value': identifier}).status_code == 200
    session_id = sessions[-1]
    assert client.post('/api/record/faculty', json={'input_value': 'Private Faculty'}).status_code == 200
    assert client.post('/api/record/dirty', json={}).status_code == 200
    assert client.post(f'/api/session/{session_id}/faculty/pick', json={}).status_code == 200
    assert client.post(f'/api/session/{session_id}/draw/start', json={
        'comment': 'PrivateComment includes a student name',
    }).status_code == 200
    return school, admin, sessions


def sign_in(client, account):
    result = client.post('/api/auth/login', json={'username': account.username, 'password': 'privacy-password'})
    assert result.status_code == 200


def guest(client, school):
    result = client.post('/api/auth/guest', json={'school_slug': school.slug})
    assert result.status_code == 200


def enable(client, enabled=True):
    result = client.put('/api/admin/guest-privacy', json={'enabled': enabled})
    assert result.status_code == 200
    assert result.get_json()['enabled'] is enabled


def test_private_guests_have_unique_consistent_aliases_everywhere(client, privacy_school):
    school, admin, sessions = privacy_school
    enable(client)
    guest(client, school)
    assert client.post(f'/api/session/switch/{sessions[-1]}').status_code == 200
    urls = [
        '/api/session/list', '/api/session/status', '/api/session/history',
        '/api/session/scan-history', f'/api/session/{sessions[-1]}/draw/summary',
        f'/api/session/{sessions[-1]}/house-stats?estimate_separation=1',
    ]
    forbidden = ['PrivateName', 'PrivateSurname', 'PrivateAdvisor', 'PrivateClan',
                 'PrivateTitle', 'Private Faculty', 'PrivateComment', 'PrivateRoster',
                 'private-101', 'private-102', admin.username]
    forbidden += [student.id for student in db_session.query(Student).filter_by(school_id=school.id)]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, response.get_json()
        assert response.headers['Cache-Control'] == 'no-store'
        assert not any(item in response.get_data(as_text=True) for item in forbidden), url
    summary = client.get(urls[4]).get_json()
    labels = {item['display_name'] for item in summary['candidates']}
    assert len(labels) == 2
    assert all(label.startswith('Student ') and label[8:].isdigit() for label in labels)
    assert summary['draw_info']['winner']['display_name'] in labels
    assert {event['student_name'] for event in summary['history'] if event['student_name']} <= labels
    for candidate in summary['candidates']:
        assert all(candidate[field] is None for field in ['grade', 'advisor', 'house', 'clan', 'student_identifier'])
    formatted = client.get('/api/session/scan-history').get_json()['scan_history']
    assert {item['name'] for item in formatted if item['category'] == 'CLEAN'} == labels
    assert next(item for item in formatted if item['category'] == 'FACULTY')['name'] == 'Faculty member'
    assert next(item for item in formatted if item['category'] == 'DIRTY')['name'] == 'Dirty Plate (count only)'
    legacy = client.get('/api/session/history').get_json()['scan_history']
    assert {item['preferred_name'] for item in legacy if item['category'] == 'clean'} == labels
    assert client.post(f'/api/session/switch/{sessions[0]}').status_code == 200
    assert {item['name'] for item in client.get('/api/session/scan-history').get_json()['scan_history']} == labels
    # A new request and a cache hydration do not change saved labels.
    hydrate_session_from_db(sessions[0])
    assert {item['display_name'] for item in client.get(f'/api/session/{sessions[0]}/draw/summary').get_json()['candidates']} == labels
    assert db_session.query(GuestStudentAlias).filter_by(school_id=school.id).count() == 2


def test_toggle_applies_to_existing_guests_and_preserves_staff_and_records(client, privacy_school):
    school, admin, sessions = privacy_school
    enable(client)
    guest(client, school)
    client.post(f'/api/session/switch/{sessions[-1]}')
    labels = client.get('/api/session/scan-history').get_json()['scan_history']
    with client.application.test_client() as staff:
        sign_in(staff, admin)
        enable(staff, False)
        staff.post(f'/api/session/switch/{sessions[-1]}')
        assert 'PrivateName' in staff.get('/api/session/scan-history').get_data(as_text=True)
        enable(staff)
        assert 'PrivateName' in staff.get('/api/session/scan-history').get_data(as_text=True)
    assert client.get('/api/session/scan-history').get_json()['scan_history'] == labels
    assert all(record.preferred_name == 'PrivateName' for record in db_session.query(SessionRecord).filter_by(
        school_id=school.id, category='clean',
    ))
    assert any(row['preferred_name'] == 'PrivateName' for row in session_data[sessions[-1]]['clean_records'])


def test_disabled_setting_keeps_original_guest_view(client, privacy_school):
    school, _, sessions = privacy_school
    enable(client, False)
    assert client.get('/api/admin/guest-privacy').get_json()['enabled'] is False
    guest(client, school)
    client.post(f'/api/session/switch/{sessions[-1]}')
    assert 'PrivateName' in client.get('/api/session/scan-history').get_data(as_text=True)


def test_new_schools_anonymize_guest_views_by_default(client, privacy_school):
    school, _, sessions = privacy_school
    assert client.get('/api/admin/guest-privacy').get_json()['enabled'] is True
    guest(client, school)
    client.post(f'/api/session/switch/{sessions[-1]}')
    response = client.get('/api/session/scan-history')
    assert response.status_code == 200
    assert 'PrivateName' not in response.get_data(as_text=True)
    assert 'Student ' in response.get_data(as_text=True)


def test_roster_name_changes_do_not_reassign_guest_labels(client, privacy_school):
    school, admin, sessions = privacy_school
    enable(client)
    guest(client, school)
    url = f'/api/session/{sessions[-1]}/draw/summary'
    before = client.get(url).get_json()['candidates']
    sign_in(client, admin)
    updated = ('Student ID,Last,Preferred,Grade,Advisor,House,Clan\n'
               'private-101,NewSurname,RenamedStudent,9,NewAdvisor,Barn,NewClan\n'
               'private-102,OtherSurname,AnotherStudent,10,NewAdvisor,Hall,NewClan\n')
    assert client.post('/api/csv/upload', data={
        'file': (io.BytesIO(updated.encode()), 'UpdatedRoster.csv'),
    }).status_code == 200
    guest(client, school)
    after = client.get(url).get_json()['candidates']
    assert {row['student_id']: row['display_name'] for row in before} == {
        row['student_id']: row['display_name'] for row in after}
    assert 'RenamedStudent' not in str(after)


@pytest.mark.parametrize('role', ['admin', 'superadmin', 'user', 'inter_school', 'guest', None])
def test_setting_permissions_and_school_scope(client, privacy_school, role):
    school, _, _ = privacy_school
    school_id = school.id
    school_slug = school.slug
    other_id = uuid.uuid4().hex
    other = School(id=other_id, name='Other School', slug=uuid.uuid4().hex)
    db_session.add(other)
    db_session.commit()
    client.post('/api/auth/logout')
    if role == 'guest':
        assert client.post('/api/auth/guest', json={'school_slug': school_slug}).status_code == 200
    elif role:
        account = create_user_record(uuid.uuid4().hex, 'privacy-password', 'Test Role', role=role, school_id=school_id)
        sign_in(client, account)
    expected = 200 if role in {'admin', 'superadmin'} else 401 if role in {'guest', None} else 403
    assert client.get('/api/admin/guest-privacy').status_code == expected
    assert client.put('/api/admin/guest-privacy', json={'enabled': False, 'school_id': other_id}).status_code == expected
    db_session.expire_all()
    assert db_session.get(School, other_id).guest_privacy_enabled == 1
    assert bool(db_session.get(School, school_id).guest_privacy_enabled) is (expected != 200)


@pytest.mark.parametrize('data', [None, [], {}, {'enabled': 'true'}, {'enabled': 1}])
def test_setting_rejects_non_boolean_values(client, privacy_school, data):
    assert client.put('/api/admin/guest-privacy', json=data).status_code == 400


def test_guests_cannot_use_rosters_exports_or_other_school_draws(client, privacy_school):
    school, admin, sessions = privacy_school
    other = School(id=uuid.uuid4().hex, name='Other School', slug=uuid.uuid4().hex)
    db_session.add(other)
    db_session.flush()
    foreign_id = uuid.uuid4().hex
    foreign = SessionModel(id=foreign_id, school_id=other.id, created_by=admin.id,
                           session_name='Foreign session', is_public=1)
    db_session.add(foreign)
    db_session.get(SessionModel, sessions[0]).is_public = 0
    db_session.commit()
    guest(client, school)
    assert client.get(f'/api/session/{foreign_id}/draw/summary').status_code == 404
    assert client.get(f'/api/session/{sessions[0]}/draw/summary').status_code == 403
    for url in ['/api/csv/student-names', '/api/csv/preview', '/api/teachers/list',
                '/api/export/csv', '/api/export/csv/detailed', '/api/admin/sessions/export']:
        assert client.get(url).status_code in {401, 403}


def test_privacy_failure_never_sends_original_data(client, privacy_school, monkeypatch):
    school, _, sessions = privacy_school
    enable(client)
    guest(client, school)
    client.post(f'/api/session/switch/{sessions[-1]}')
    def fail(*args):
        raise RuntimeError('Alias storage unavailable')
    monkeypatch.setattr(guest_privacy.GuestView, 'alias', fail)
    result = client.get('/api/session/scan-history')
    assert result.status_code == 503
    assert 'PrivateName' not in result.get_data(as_text=True)


def test_existing_database_upgrades_privacy_setting_and_alias_table(monkeypatch):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(School.__table__.insert().values(
            id='historical-privacy-school', name='Historical School', slug='historical-privacy-school',
        ))
        connection.execute(text('ALTER TABLE schools DROP COLUMN guest_privacy_enabled'))
        connection.execute(text('DROP TABLE guest_student_aliases'))
    monkeypatch.setattr(database, 'engine', engine)
    database._bootstrap_database()
    assert 'guest_privacy_enabled' in {column['name'] for column in inspect(engine).get_columns('schools')}
    assert 'guest_student_aliases' in inspect(engine).get_table_names()
    with engine.begin() as connection:
        assert connection.execute(text("SELECT guest_privacy_enabled FROM schools WHERE id = 'historical-privacy-school'")).scalar_one() == 1
        connection.execute(text("UPDATE schools SET guest_privacy_enabled = 0 WHERE id = 'historical-privacy-school'"))
    database._bootstrap_database()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT guest_privacy_enabled FROM schools WHERE id = 'historical-privacy-school'")).scalar_one() == 0
    engine.dispose()
