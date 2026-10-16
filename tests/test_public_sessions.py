import uuid

import pytest

from src.routes.golden_plate_recorder_db import public_session_routes
from src.routes.golden_plate_recorder_db.db import School, Session, User, db_session
from src.routes.golden_plate_recorder_db.users import create_user_record


@pytest.fixture
def public_sessions(client):
    client.get('/api/auth/status')
    suffix = uuid.uuid4().hex
    school = School(id=f'public-{suffix}', name='Public Academy', slug=f'public-{suffix}')
    disabled = School(id=f'disabled-{suffix}', name='Disabled Academy', slug=f'disabled-{suffix}', status='disabled')
    db_session.add_all([school, disabled])
    db_session.commit()
    owner = create_user_record(f'public-{suffix}', 'public-test-password', 'Private Staff', school_id=school.id)
    sessions = []
    for label, status, public, school_id in [
        ('active', 'active', 1, school.id), ('archived', 'archived', 1, school.id),
        ('discarded', 'discarded', 1, school.id), ('private', 'active', 0, school.id),
        ('disabled', 'active', 1, disabled.id),
    ]:
        row = Session(id=f'{label}-{suffix}', school_id=school_id, created_by=owner.id,
                      session_name=f'Private student name {label}', status=status, is_public=public,
                      clean_number=7, faculty_number=2, dirty_number=2, red_number=1)
        db_session.add(row)
        sessions.append(row.id)
    db_session.commit()
    yield school.id, sessions
    db_session.query(Session).filter(Session.id.in_(sessions)).delete(synchronize_session=False)
    db_session.commit()


def test_random_draws_only_eligible_sessions_and_does_not_cache(client, public_sessions, monkeypatch):
    _, ids = public_sessions
    eligible = public_session_routes._available_sessions().order_by(Session.id).all()
    selected = set()
    for index in range(len(eligible)):
        def choose(count):
            assert count == len(eligible)
            return index
        monkeypatch.setattr(public_session_routes.random, 'randrange', choose)
        response = client.get('/api/public/sessions/random')
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        selected.add(response.get_json()['session']['session_id'])
    assert set(ids[:2]) <= selected
    assert not set(ids[2:]) & selected


def test_guest_metrics_match_real_dashboard_and_never_contain_people(client, public_sessions):
    school_id, ids = public_sessions
    client.post('/api/auth/guest', json={'school_id': school_id})
    assert client.post(f'/api/session/switch/{ids[0]}').status_code == 200
    actual = client.get('/api/session/status').get_json()
    response = client.get(f'/api/public/sessions/{ids[0]}')
    payload = response.get_json()['session']
    for field in ('clean_count', 'dirty_count', 'red_count', 'combined_dirty_count',
                  'faculty_clean_count', 'total_recorded', 'clean_percentage', 'dirty_percentage'):
        assert payload[field] == actual[field]
    assert payload['total_recorded'] == 12
    assert payload['clean_percentage'] == 75
    assert payload['session_name'] == 'School session'
    assert 'Private' not in response.get_data(as_text=True)
    assert set(payload) == {'session_id', 'session_name', 'school_name', 'status', 'updated_at',
                            'clean_count', 'dirty_count', 'red_count', 'combined_dirty_count',
                            'faculty_clean_count', 'total_recorded', 'clean_percentage', 'dirty_percentage'}


@pytest.mark.parametrize('index', [2, 3, 4])
def test_unavailable_session_links_fail_closed(client, public_sessions, index):
    response = client.get(f'/api/public/sessions/{public_sessions[1][index]}')
    assert response.status_code == 404
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'session' not in response.get_json()


def test_session_link_tracks_access_changes_and_preserves_login(client, public_sessions):
    school_id, ids = public_sessions
    account = db_session.query(User).filter_by(school_id=school_id).first()
    assert client.post('/api/auth/login', json={'username': account.username, 'password': 'public-test-password'}).status_code == 200
    assert client.post(f'/api/session/switch/{ids[1]}').status_code == 200
    before = None
    with client.session_transaction() as cookie:
        before = dict(cookie)
    assert client.get(f'/api/public/sessions/{ids[0]}').status_code == 200
    with client.session_transaction() as cookie:
        assert dict(cookie) == before
    row = db_session.get(Session, ids[0])
    row.status = 'discarded'
    db_session.commit()
    assert client.get(f'/api/public/sessions/{ids[0]}').status_code == 404


def test_title_follows_school_guest_privacy_and_zero_totals_are_valid(client, public_sessions):
    school_id, ids = public_sessions
    school = db_session.get(School, school_id)
    school.guest_privacy_enabled = 0
    row = db_session.get(Session, ids[0])
    row.clean_number = row.dirty_number = row.red_number = row.faculty_number = None
    db_session.commit()
    payload = client.get(f'/api/public/sessions/{ids[0]}').get_json()['session']
    assert payload['session_name'].startswith('Private student name')
    assert payload['total_recorded'] == payload['clean_percentage'] == payload['dirty_percentage'] == 0
    school = db_session.get(School, school_id)
    school.guest_privacy_enabled = 1
    db_session.commit()
    assert client.get(f'/api/public/sessions/{ids[0]}').get_json()['session']['session_name'] == 'School session'


def test_empty_random_session_is_honest(client):
    client.get('/api/auth/status')
    # Isolate this empty-state test from sessions saved by other test modules.
    query = public_session_routes._available_sessions()
    ids = [row.id for row, _ in query.all()]
    db_session.query(Session).filter(Session.id.in_(ids)).update({Session.is_public: 0}, synchronize_session=False)
    db_session.commit()
    try:
        response = client.get('/api/public/sessions/random')
        assert response.status_code == 200
        assert response.get_json() == {'session': None}
        assert client.get('/api/public/sessions/unknown').status_code == 404
    finally:
        db_session.query(Session).filter(Session.id.in_(ids)).update({Session.is_public: 1}, synchronize_session=False)
        db_session.commit()


def test_counter_is_real_all_school_total_including_private_and_disabled_schools(client, public_sessions):
    _, ids = public_sessions
    others = db_session.query(Session).filter(Session.status != 'discarded', ~Session.id.in_(ids)).all()
    baseline_clean = sum((row.clean_number or 0) + (row.faculty_number or 0) for row in others)
    baseline_sessions = len(others)
    response = client.get('/api/public/counter')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    payload = response.get_json()
    # Active, archived, private, and disabled-school sessions all count.
    # Only the discarded session is excluded. Faculty clean plates count too.
    assert payload['clean_count'] == baseline_clean + 36
    assert payload['session_count'] == baseline_sessions + 4
    assert set(payload) == {'clean_count', 'session_count', 'updated_at', 'refresh_interval_seconds'}
    assert payload['refresh_interval_seconds'] == 5
    private = db_session.get(Session, ids[3])
    private.clean_number += 4
    db_session.commit()
    assert client.get('/api/public/counter').get_json()['clean_count'] == baseline_clean + 40
    private = db_session.get(Session, ids[3])
    private.status = 'discarded'
    db_session.commit()
    changed = client.get('/api/public/counter').get_json()
    assert changed['clean_count'] == baseline_clean + 27
    assert changed['session_count'] == baseline_sessions + 3

