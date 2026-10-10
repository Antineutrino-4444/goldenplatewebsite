import copy
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect, text

from src.routes.golden_plate_recorder_db import db as database
from src.routes.golden_plate_recorder_db.db import School, Session, SessionRecord, db_session
from src.routes.golden_plate_recorder_db.live_counter_routes import _utc_bounds
from src.routes.golden_plate_recorder_db.users import create_user_record


SETTINGS = {
    'year': 2026, 'timezone': 'America/New_York', 'default_range': 'year',
    'custom_ranges': [
        {'id': 'custom-1', 'name': 'Fall term', 'start_date': '2026-10-10', 'end_date': '2026-10-10'},
        {'id': 'custom-2', 'start_date': '2026-03-08', 'end_date': '2026-03-08'},
        {'id': 'custom-3', 'name': '', 'start_date': '2025-12-31', 'end_date': '2026-01-01'},
    ],
}


@pytest.fixture
def counter_school(client):
    client.get('/api/auth/status')
    suffix = uuid.uuid4().hex
    school = School(id=f'counter-{suffix}', name='Counter Academy', slug=f'counter-{suffix}',
                    live_counter_settings=json.dumps(SETTINGS))
    db_session.add(school)
    db_session.commit()
    school_id, code = school.id, school.slug
    account = create_user_record(f'counter-super-{suffix}', 'counter-test-password', 'Counter Superadmin',
                                 role='superadmin', school_id=school_id)
    owner = account.id
    assert client.post('/api/auth/login', json={
        'username': account.username, 'password': 'counter-test-password',
    }).status_code == 200
    return {'id': school_id, 'code': code, 'owner': owner}


def add_session(school, *, public=True, status='active', main_id=None):
    row = Session(id=uuid.uuid4().hex, school_id=school['id'], created_by=school['owner'],
                  session_name=uuid.uuid4().hex, created_at=datetime(2024, 1, 1),
                  is_public=int(public), status=status, main_session_id=main_id)
    db_session.add(row)
    db_session.commit()
    return row.id


def add_record(school, session_id, category, when, *, named=False):
    row = SessionRecord(school_id=school['id'], session_id=session_id, category=category,
                        recorded_by=school['owner'], recorded_at=datetime.fromisoformat(when),
                        dedupe_key=f'count:{category}:{uuid.uuid4().hex}',
                        preferred_name='Private Student Name' if named else None)
    db_session.add(row)
    db_session.commit()
    return row.id


def ranges(client):
    response = client.get('/api/live-counter')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    return {row['id']: row for row in response.get_json()['ranges']}


def test_live_counter_includes_counts_faculty_and_inclusive_days_by_record_time(client, counter_school):
    sid = add_session(counter_school)
    add_record(counter_school, sid, 'clean', '2026-10-10T04:00:00+00:00', named=True)
    add_record(counter_school, sid, 'faculty', '2026-10-11T03:59:59.999999+00:00')
    add_record(counter_school, sid, 'dirty', '2026-10-10T15:00:00+00:00')
    add_record(counter_school, sid, 'red', '2026-10-10T15:00:00+00:00')
    add_record(counter_school, sid, 'clean', '2026-10-10T03:59:59.999999+00:00')
    add_record(counter_school, sid, 'clean', '2026-10-11T04:00:00+00:00')
    result = ranges(client)
    day = result['custom-1']
    assert (day['clean_count'], day['total_records'], day['clean_percentage']) == (2, 4, 50)
    assert day['student_clean_count'] == day['faculty_clean_count'] == 1
    assert result['year']['total_records'] == 6
    payload = client.get('/api/live-counter').get_json()
    assert payload['scope'] == 'both'
    assert payload['can_manage_ranges'] and payload['can_set_default']
    assert 'Private Student Name' not in json.dumps(payload)
    assert len(payload['ranges']) == 4


def test_year_boundaries_use_local_calendar_not_server_year(client, counter_school):
    sid = add_session(counter_school)
    for when in ['2026-01-01T04:59:59.999999+00:00', '2026-01-01T05:00:00+00:00',
                 '2027-01-01T04:59:59.999999+00:00', '2027-01-01T05:00:00+00:00']:
        add_record(counter_school, sid, 'clean', when)
    assert ranges(client)['year']['clean_count'] == 2


@pytest.mark.parametrize('day,hours', [('2026-03-08', 23), ('2026-11-01', 25), ('2026-10-10', 24)])
def test_calendar_day_boundaries_handle_daylight_saving(day, hours):
    lower, upper = _utc_bounds(day, day, 'America/New_York')
    assert upper - lower == timedelta(hours=hours)
    assert lower.tzinfo == upper.tzinfo == timezone.utc


def test_merged_and_archived_sessions_count_once_but_discarded_sessions_are_excluded(client, counter_school):
    main_id = add_session(counter_school)
    extra_id = add_session(counter_school, main_id=main_id)
    for sid in [main_id, extra_id, add_session(counter_school, status='archived'),
                add_session(counter_school, status='discarded')]:
        add_record(counter_school, sid, 'clean', '2026-10-10T12:00:00+00:00')
    assert ranges(client)['custom-1']['clean_count'] == 3


def test_guest_requires_school_code_sees_only_public_school_totals_and_cannot_edit(client, counter_school):
    public = add_session(counter_school)
    private = add_session(counter_school, public=False)
    for sid in [public, private]:
        add_record(counter_school, sid, 'clean', '2026-10-10T12:00:00+00:00')
    client.post('/api/auth/logout')
    assert client.get('/api/live-counter').status_code == 401
    assert client.put('/api/live-counter/settings', json=SETTINGS).status_code == 401
    assert client.post('/api/auth/guest', json={}).status_code == 400
    assert client.post('/api/auth/guest', json={'school_slug': 'nonexistent-counter-school'}).status_code == 404
    assert client.post('/api/auth/guest', json={'school_slug': counter_school['code'].upper()}).status_code == 200
    payload = client.get('/api/live-counter').get_json()
    assert payload['public_sessions_only'] is True
    assert not payload['can_manage_ranges'] and not payload['can_set_default']
    assert ranges(client)['custom-1']['clean_count'] == 1
    assert client.put('/api/live-counter/settings', json=SETTINGS).status_code == 403
    assert ranges(client)['custom-1']['clean_count'] == 1


@pytest.mark.parametrize('role', ['user', 'admin', 'inter_school'])
def test_role_permissions_and_superadmin_only_default(client, counter_school, role):
    account = create_user_record(f'counter-{role}-{uuid.uuid4().hex}', 'counter-test-password', 'Other Role',
                                 role=role, school_id=counter_school['id'])
    assert client.post('/api/auth/login', json={
        'username': account.username, 'password': 'counter-test-password',
    }).status_code == 200
    if role == 'inter_school':
        assert client.get('/api/live-counter').status_code == 403
    else:
        response = client.get('/api/live-counter').get_json()
        assert response['can_manage_ranges'] is (role == 'admin')
        assert response['can_set_default'] is False
    altered = copy.deepcopy(SETTINGS)
    altered['custom_ranges'][0]['name'] = 'New name'
    response = client.put('/api/live-counter/settings', json=altered)
    assert response.status_code == (200 if role == 'admin' else 403)
    altered['default_range'] = 'custom-1'
    assert client.put('/api/live-counter/settings', json=altered).status_code == 403


def test_superadmin_sets_persistent_default_admin_can_rename_but_not_remove_it(client, counter_school):
    changed = {**SETTINGS, 'default_range': 'custom-1'}
    assert client.put('/api/live-counter/settings', json=changed).status_code == 200
    db_session.remove()
    data = client.get('/api/live-counter').get_json()
    assert data['settings']['default_range'] == 'custom-1'
    assert data['settings']['custom_ranges'][1]['name'] == ''
    account = create_user_record(f'counter-admin-{uuid.uuid4().hex}', 'counter-test-password', 'Range Admin',
                                 role='admin', school_id=counter_school['id'])
    client.post('/api/auth/login', json={'username': account.username, 'password': 'counter-test-password'})
    updated = copy.deepcopy(SETTINGS)
    updated.pop('default_range')
    updated['custom_ranges'][0]['name'] = 'Optional renamed period'
    assert client.put('/api/live-counter/settings', json=updated).status_code == 200
    assert client.get('/api/live-counter').get_json()['settings']['default_range'] == 'custom-1'
    updated['custom_ranges'] = updated['custom_ranges'][1:]
    assert client.put('/api/live-counter/settings', json=updated).status_code == 400


@pytest.mark.parametrize('field,value', [
    ('year', True), ('year', 2026.5), ('year', '2026'), ('year', 1899), ('year', 9999),
    ('timezone', 'Not/AZone'), ('timezone', None), ('custom_ranges', None),
    ('default_range', 'custom-4'), ('custom_ranges', [*SETTINGS['custom_ranges'], SETTINGS['custom_ranges'][0]]),
])
def test_invalid_settings_rejected_without_changes(client, counter_school, field, value):
    assert client.put('/api/live-counter/settings', json={**SETTINGS, field: value}).status_code == 400
    stored = json.loads(db_session.get(School, counter_school['id']).live_counter_settings)
    assert stored == SETTINGS


@pytest.mark.parametrize('patch', [
    {'start_date': '2026-02-30'}, {'end_date': '2026-1-01'}, {'start_date': '2026-10-11'},
    {'end_date': ''}, {'id': 'custom-4'}, {'id': ['custom-1']}, {'name': 'x' * 81}, {'name': False},
])
def test_custom_range_validation(client, counter_school, patch):
    invalid = copy.deepcopy(SETTINGS)
    invalid['custom_ranges'][0].update(patch)
    assert client.put('/api/live-counter/settings', json=invalid).status_code == 400
    assert json.loads(db_session.get(School, counter_school['id']).live_counter_settings) == SETTINGS


def test_cross_school_isolation_and_scope_cannot_be_changed_by_viewer(client, counter_school):
    other = School(id=uuid.uuid4().hex, slug=uuid.uuid4().hex, name='Other Counter School')
    db_session.add(other)
    db_session.commit()
    other_id = other.id
    sid = add_session(counter_school)
    add_record(counter_school, sid, 'clean', '2026-10-10T12:00:00+00:00')
    response = client.get(f'/api/live-counter?school_id={other_id}&scope=faculty&start_date=2020-01-01').get_json()
    assert response['school']['code'] == counter_school['code']
    assert response['scope'] == 'both' and response['ranges'][0]['clean_count'] == 1
    assert client.put('/api/live-counter/settings', json={**SETTINGS, 'school_id': other_id}).status_code == 200
    assert db_session.get(School, other_id).live_counter_settings is None


def test_zero_totals_and_new_records_appear_on_next_live_update(client, counter_school):
    assert ranges(client)['year']['clean_count'] == ranges(client)['year']['clean_percentage'] == 0
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    assert client.post('/api/record/clean', json={}).status_code == 200
    assert client.post('/api/record/faculty', json={}).status_code == 200
    assert client.post('/api/record/dirty', json={}).status_code == 200
    db_session.query(SessionRecord).filter_by(session_id=session_id).update({
        SessionRecord.recorded_at: datetime(2026, 10, 10, 12),
    })
    db_session.commit()
    result = ranges(client)['custom-1']
    assert result['clean_count'] == 2 and result['total_records'] == 3 and result['clean_percentage'] == 66.7
    identifier = db_session.query(SessionRecord).filter_by(session_id=session_id, category='dirty').one().id
    db_session.query(SessionRecord).filter_by(id=identifier).delete()
    db_session.commit()
    result = ranges(client)['custom-1']
    assert result['total_records'] == 2 and result['clean_percentage'] == 100


def test_milestone_is_persistent_school_specific_and_superadmin_only(client, counter_school):
    assert client.get('/api/live-counter').get_json()['settings']['milestone'] is None
    assert client.put('/api/live-counter/settings', json={**SETTINGS, 'milestone': 1000}).status_code == 200
    db_session.remove()
    assert client.get('/api/live-counter').get_json()['settings']['milestone'] == 1000
    other = School(id=uuid.uuid4().hex, slug=uuid.uuid4().hex, name='Other Milestone School')
    db_session.add(other)
    db_session.commit()
    assert other.live_counter_settings is None
    account = create_user_record(f'milestone-admin-{uuid.uuid4().hex}', 'counter-test-password', 'Range Admin',
                                 role='admin', school_id=counter_school['id'])
    client.post('/api/auth/login', json={'username': account.username, 'password': 'counter-test-password'})
    assert client.put('/api/live-counter/settings', json=SETTINGS).status_code == 200
    for milestone in (500, None):
        response = client.put('/api/live-counter/settings', json={**SETTINGS, 'milestone': milestone})
        assert response.status_code == 403
    assert client.get('/api/live-counter').get_json()['settings']['milestone'] == 1000
    client.post('/api/auth/logout')
    client.post('/api/auth/guest', json={'school_slug': counter_school['code']})
    assert client.get('/api/live-counter').get_json()['settings']['milestone'] == 1000
    assert client.put('/api/live-counter/settings', json={**SETTINGS, 'milestone': 2}).status_code == 403


@pytest.mark.parametrize('milestone', [0, -1, 1.5, '1000', True, 1_000_000_001])
def test_invalid_milestones_rejected_atomically(client, counter_school, milestone):
    assert client.put('/api/live-counter/settings', json={**SETTINGS, 'milestone': milestone}).status_code == 400
    assert json.loads(db_session.get(School, counter_school['id']).live_counter_settings) == SETTINGS


def test_superadmin_can_disable_milestone(client, counter_school):
    assert client.put('/api/live-counter/settings', json={**SETTINGS, 'milestone': 1_000_000_000}).status_code == 200
    assert client.put('/api/live-counter/settings', json={**SETTINGS, 'milestone': None}).status_code == 200
    assert client.get('/api/live-counter').get_json()['settings']['milestone'] is None


@pytest.mark.parametrize('field', ['celebration_title', 'celebration_message', 'celebration_footer'])
def test_banner_text_is_persistent_superadmin_only_and_preserved_by_admin_edits(client, counter_school, field):
    assert client.get('/api/live-counter').get_json()['settings'][field] == ''
    assert client.put('/api/live-counter/settings', json={**SETTINGS, field: '  Our {milestone} plate celebration!  '}).status_code == 200
    db_session.remove()
    assert client.get('/api/live-counter').get_json()['settings'][field] == 'Our {milestone} plate celebration!'
    account = create_user_record(f'banner-admin-{uuid.uuid4().hex}', 'counter-test-password', 'Banner Admin',
                                 role='admin', school_id=counter_school['id'])
    client.post('/api/auth/login', json={'username': account.username, 'password': 'counter-test-password'})
    assert client.put('/api/live-counter/settings', json=SETTINGS).status_code == 200
    for value in ('New banner text', ''):
        assert client.put('/api/live-counter/settings', json={**SETTINGS, field: value}).status_code == 403
    assert client.get('/api/live-counter').get_json()['settings'][field] == 'Our {milestone} plate celebration!'
    client.post('/api/auth/logout')
    client.post('/api/auth/guest', json={'school_slug': counter_school['code']})
    assert client.get('/api/live-counter').get_json()['settings'][field] == 'Our {milestone} plate celebration!'
    assert client.put('/api/live-counter/settings', json={**SETTINGS, field: 'Guest edit'}).status_code == 403


@pytest.mark.parametrize('field,value', [
    ('celebration_title', 'x' * 81), ('celebration_message', 'x' * 301), ('celebration_footer', 'x' * 121),
    ('celebration_title', None), ('celebration_message', False), ('celebration_footer', ['text']),
])
def test_invalid_banner_text_rejected_atomically(client, counter_school, field, value):
    assert client.put('/api/live-counter/settings', json={**SETTINGS, field: value}).status_code == 400
    assert json.loads(db_session.get(School, counter_school['id']).live_counter_settings) == SETTINGS


def test_banner_text_can_restore_defaults_without_affecting_other_schools(client, counter_school):
    fields = {'celebration_title': 'Go team!', 'celebration_message': '<b>{milestone} plates!</b>',
              'celebration_footer': 'Thank you!'}
    assert client.put('/api/live-counter/settings', json={**SETTINGS, **fields}).status_code == 200
    assert client.get('/api/live-counter').get_json()['settings']['celebration_message'] == fields['celebration_message']
    other = School(id=uuid.uuid4().hex, slug=uuid.uuid4().hex, name='Other Banner School')
    db_session.add(other)
    db_session.commit()
    assert other.live_counter_settings is None
    assert client.put('/api/live-counter/settings', json={**SETTINGS, **dict.fromkeys(fields, '   ')}).status_code == 200
    settings = client.get('/api/live-counter').get_json()['settings']
    assert all(settings[field] == '' for field in fields)


def test_legacy_discard_control_persistently_excludes_and_restores_live_totals(client, counter_school):
    kept = add_session(counter_school)
    omitted = add_session(counter_school)
    add_record(counter_school, kept, 'dirty', '2026-10-10T12:00:00+00:00')
    for category in ('clean', 'faculty', 'dirty', 'red'):
        add_record(counter_school, omitted, category, '2026-10-10T12:00:00+00:00')
    original = ranges(client)['custom-1']
    assert (original['clean_count'], original['total_records'], original['clean_percentage']) == (2, 5, 40)
    endpoint = f'/api/session/{omitted}/draw/discard'
    assert client.post(endpoint, json={'discarded': True}).status_code == 200
    db_session.remove()
    row = db_session.get(Session, omitted)
    assert row.status == 'discarded' and row.discarded_by == counter_school['owner'] and row.discarded_at
    timestamp = row.discarded_at
    assert client.post(endpoint, json={'discarded': True}).status_code == 200
    assert db_session.get(Session, omitted).discarded_at == timestamp
    result = ranges(client)['custom-1']
    assert (result['clean_count'], result['total_records'], result['clean_percentage']) == (0, 1, 0)
    assert db_session.query(SessionRecord).filter_by(session_id=omitted).count() == 4
    assert client.get(f'/api/session/{omitted}/draw/summary').get_json()['is_discarded'] is True
    listed = client.get('/api/session/list').get_json()['sessions']
    assert next(item for item in listed if item['session_id'] == omitted)['is_discarded'] is True
    assert client.post(f'/api/session/{omitted}/draw/start', json={}).status_code == 400
    assert client.post(endpoint, json={'discarded': False}).status_code == 200
    db_session.remove()
    row = db_session.get(Session, omitted)
    assert row.status == 'active' and row.discarded_at is None and row.discarded_by is None
    assert ranges(client)['custom-1'] == original
    assert client.get(f'/api/session/{omitted}/draw/summary').get_json()['is_discarded'] is False


@pytest.mark.parametrize('role', ['admin', 'user', 'inter_school', 'guest'])
def test_only_superadmins_can_discard_for_live_totals(client, counter_school, role):
    sid = add_session(counter_school)
    if role == 'guest':
        client.post('/api/auth/logout')
        client.post('/api/auth/guest', json={'school_slug': counter_school['code']})
    else:
        account = create_user_record(f'discard-{role}-{uuid.uuid4().hex}', 'counter-test-password', 'Discard User',
                                     role=role, school_id=counter_school['id'])
        client.post('/api/auth/login', json={'username': account.username, 'password': 'counter-test-password'})
    assert client.post(f'/api/session/{sid}/draw/discard', json={'discarded': True}).status_code == (401 if role == 'guest' else 403)
    assert db_session.get(Session, sid).status == 'active'


@pytest.mark.parametrize('value', [None, {}, {'discarded': 1}, {'discarded': 'false'}, {'discarded': None}, []])
def test_discard_requires_explicit_boolean_and_preserves_state(client, counter_school, value):
    sid = add_session(counter_school)
    assert client.post(f'/api/session/{sid}/draw/discard', json=value).status_code == 400
    assert db_session.get(Session, sid).status == 'active'


def test_discard_is_school_scoped_and_updates_guest_totals(client, counter_school):
    sid = add_session(counter_school)
    add_record(counter_school, sid, 'faculty', '2026-10-10T12:00:00+00:00')
    other = School(id=uuid.uuid4().hex, slug=uuid.uuid4().hex, name='Other Discard School')
    db_session.add(other)
    db_session.commit()
    other_sid = add_session({**counter_school, 'id': other.id})
    assert client.post(f'/api/session/{other_sid}/draw/discard', json={'discarded': True}).status_code == 404
    assert db_session.get(Session, other_sid).status == 'active'
    assert client.post(f'/api/session/{sid}/draw/discard', json={'discarded': True}).status_code == 200
    client.post('/api/auth/logout')
    assert client.post(f'/api/session/{sid}/draw/discard', json={'discarded': False}).status_code == 401
    client.post('/api/auth/guest', json={'school_slug': counter_school['code']})
    assert ranges(client)['custom-1']['clean_count'] == 0


def test_existing_schema_upgrade_adds_settings_and_index_idempotently(monkeypatch):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE schools DROP COLUMN live_counter_settings'))
        connection.execute(text('DROP INDEX idx_records_school_recorded_at'))
    monkeypatch.setattr(database, 'engine', engine)
    try:
        database._bootstrap_database()
        database._bootstrap_database()
        inspector = inspect(engine)
        assert 'live_counter_settings' in {column['name'] for column in inspector.get_columns('schools')}
        assert 'idx_records_school_recorded_at' in {index['name'] for index in inspector.get_indexes('session_records')}
    finally:
        engine.dispose()


def test_metric_defaults_and_both_goals_survive_restart_and_admin_range_edits(client, counter_school):
    legacy = client.get('/api/live-counter').get_json()['settings']
    assert legacy['default_metric'] == 'count' and legacy['percentage_milestone'] is None
    update = {**SETTINGS, 'default_metric': 'percentage', 'milestone': 1000, 'percentage_milestone': 75.5}
    assert client.put('/api/live-counter/settings', json=update).status_code == 200
    db_session.remove()
    settings = client.get('/api/live-counter').get_json()['settings']
    assert (settings['default_metric'], settings['milestone'], settings['percentage_milestone']) == ('percentage', 1000, 75.5)
    account = create_user_record(f'metric-admin-{uuid.uuid4().hex}', 'counter-test-password', 'Range Admin',
                                 role='admin', school_id=counter_school['id'])
    client.post('/api/auth/login', json={'username': account.username, 'password': 'counter-test-password'})
    assert client.put('/api/live-counter/settings', json={**SETTINGS, 'year': 2025}).status_code == 200
    for field, value in [('default_metric', 'count'), ('percentage_milestone', 80), ('percentage_milestone', None)]:
        assert client.put('/api/live-counter/settings', json={**SETTINGS, field: value}).status_code == 403
    settings = client.get('/api/live-counter').get_json()['settings']
    assert (settings['default_metric'], settings['milestone'], settings['percentage_milestone']) == ('percentage', 1000, 75.5)
    client.post('/api/auth/logout')
    client.post('/api/auth/guest', json={'school_slug': counter_school['code']})
    settings = client.get('/api/live-counter').get_json()['settings']
    assert settings['default_metric'] == 'percentage' and settings['percentage_milestone'] == 75.5
    assert client.put('/api/live-counter/settings', json=update).status_code == 403


@pytest.mark.parametrize('field,value', [
    ('default_metric', 'other'), ('default_metric', None), ('default_metric', ['count']),
    ('percentage_milestone', 0), ('percentage_milestone', -1), ('percentage_milestone', 100.1),
    ('percentage_milestone', 70.55), ('percentage_milestone', '80'), ('percentage_milestone', True),
    ('percentage_milestone', float('nan')), ('percentage_milestone', float('inf')),
])
def test_invalid_percentage_settings_are_rejected_atomically(client, counter_school, field, value):
    assert client.put('/api/live-counter/settings', json={**SETTINGS, field: value}).status_code == 400
    assert json.loads(db_session.get(School, counter_school['id']).live_counter_settings) == SETTINGS


def test_percentage_goal_boundaries_disable_and_school_isolation(client, counter_school):
    for goal in (0.1, 70.1, 100, None):
        assert client.put('/api/live-counter/settings', json={**SETTINGS, 'percentage_milestone': goal}).status_code == 200
        assert client.get('/api/live-counter').get_json()['settings']['percentage_milestone'] == goal
    other = School(id=uuid.uuid4().hex, slug=uuid.uuid4().hex, name='Other Percentage School')
    db_session.add(other)
    db_session.commit()
    assert other.live_counter_settings is None
