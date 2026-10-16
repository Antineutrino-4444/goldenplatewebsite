import uuid
from types import SimpleNamespace

import pytest

from src.routes.golden_plate_recorder_db.db import INTERSCHOOL_SCHOOL_ID, School, db_session
from src.routes.golden_plate_recorder_db.map_db import MapSchoolLocation, MapSchoolMapPreference, map_db_session
from src.routes.golden_plate_recorder_db.users import create_user_record

LOCATION = {'latitude': 43.99, 'longitude': -79.47, 'location_name': 'Example Academy',
            'address': '10 School Road, Aurora, Canada', 'source': 'photon', 'place_id': 'W123'}


@pytest.fixture
def school_accounts(client):
    client.get('/api/auth/status')
    suffix = uuid.uuid4().hex[:10]
    school = School(id=f'map-{suffix}', name=f'Academy {suffix}', slug=f'map-{suffix}', contact_email='private@example.com')
    other = School(id=f'other-{suffix}', name='Other School', slug=f'other-{suffix}')
    db_session.add_all([school, other])
    db_session.commit()
    users = {role: create_user_record(f'map-{role}-{suffix}', 'map-test-password', role.title(),
                                     role=role, school_id=INTERSCHOOL_SCHOOL_ID if role == 'inter_school' else school.id)
             for role in ('user', 'admin', 'superadmin', 'inter_school')}
    school_info = SimpleNamespace(id=school.id, name=school.name)
    other_info = SimpleNamespace(id=other.id, name=other.name)
    account_info = {role: SimpleNamespace(id=account.id, username=account.username) for role, account in users.items()}
    yield school_info, other_info, account_info
    map_db_session.query(MapSchoolLocation).filter(MapSchoolLocation.school_id.in_([school_info.id, other_info.id])).delete()
    map_db_session.query(MapSchoolMapPreference).filter(MapSchoolMapPreference.school_id.in_([school_info.id, other_info.id])).delete()
    map_db_session.commit()


def sign_in(client, account):
    return client.post('/api/auth/login', json={'username': account.username, 'password': 'map-test-password'})


@pytest.mark.parametrize('role', ['superadmin'])
def test_superadmin_selects_own_school_location_and_updates_one_marker(client, school_accounts, role):
    school, other, accounts = school_accounts
    sign_in(client, accounts[role])
    assert client.get('/api/map/school-location').get_json()['can_edit'] is True
    response = client.put('/api/map/school-location', json={**LOCATION, 'school_id': other.id})
    assert response.status_code == 200
    assert response.get_json()['location']['school_id'] == school.id
    assert map_db_session.get(MapSchoolLocation, other.id) is None
    response = client.put('/api/map/school-location', json={**LOCATION, 'latitude': 0, 'longitude': 0})
    assert response.status_code == 200
    assert map_db_session.query(MapSchoolLocation).filter_by(school_id=school.id).count() == 1
    client.post('/api/auth/logout')
    markers = [item for item in client.get('/api/map/schools').get_json()['schools'] if item['school_id'] == school.id]
    assert len(markers) == 1
    assert markers[0]['latitude'] == markers[0]['longitude'] == 0
    assert not ({'contact_email', 'updated_by_user_id', 'email', 'password'} & markers[0].keys())


@pytest.mark.parametrize('role', ['user', 'admin'])
def test_members_can_preview_but_not_change_shared_school_location(client, school_accounts, role):
    school, _, accounts = school_accounts
    sign_in(client, accounts[role])
    assert client.get('/api/map/school-location').get_json()['can_edit'] is False
    assert client.put('/api/map/school-location', json=LOCATION).status_code == 403
    assert client.put('/api/map/school-location', json={'unmapped': True}).status_code == 403
    assert client.get('/api/map/school-location').get_json()['decision_required'] is False
    assert map_db_session.get(MapSchoolLocation, school.id) is None


def test_anonymous_users_cannot_set_school_locations(client):
    client.post('/api/auth/logout')
    assert client.get('/api/map/school-location').status_code == 401
    assert client.put('/api/map/school-location', json=LOCATION).status_code == 401


@pytest.mark.parametrize('patch', [
    {'latitude': None}, {'longitude': 181}, {'latitude': 'NaN'}, {'latitude': True},
    {'latitude': -91}, {'source': 'google'}, {'address': 'x' * 501},
])
def test_invalid_school_location_is_not_saved(client, school_accounts, patch):
    school, _, accounts = school_accounts
    sign_in(client, accounts['superadmin'])
    assert client.put('/api/map/school-location', json={**LOCATION, **patch}).status_code == 400
    assert map_db_session.get(MapSchoolLocation, school.id) is None


def test_disabled_schools_are_not_listed(client, school_accounts):
    school, _, accounts = school_accounts
    sign_in(client, accounts['superadmin'])
    client.put('/api/map/school-location', json=LOCATION)
    db_session.query(School).filter_by(id=school.id).update({'status': 'disabled'})
    db_session.commit()
    assert school.id not in {item['school_id'] for item in client.get('/api/map/schools').get_json()['schools']}


def test_manually_placed_location_can_be_saved_again(client, school_accounts):
    _, _, accounts = school_accounts
    sign_in(client, accounts['superadmin'])
    assert client.put('/api/map/school-location', json={
        'latitude': 10, 'longitude': 20, 'source': 'manual',
    }).status_code == 200
    location = client.get('/api/map/school-location').get_json()['location']
    assert location['place_id'] is None
    assert client.put('/api/map/school-location', json=location).status_code == 200


def test_pending_school_is_in_others_and_still_requires_a_decision(client, school_accounts):
    school, _, accounts = school_accounts
    sign_in(client, accounts['superadmin'])
    state = client.get('/api/map/school-location').get_json()
    assert state['location_state'] == 'pending'
    assert state['decision_required'] is True
    assert state['location'] is None
    listed = next(item for item in client.get('/api/map/schools').get_json()['schools'] if item['school_id'] == school.id)
    assert listed['unmapped'] is True
    assert listed['latitude'] is None and listed['longitude'] is None
    client.post('/api/auth/logout')
    sign_in(client, accounts['superadmin'])
    assert client.get('/api/map/school-location').get_json()['decision_required'] is True


def test_explicit_unmapped_choice_stops_reminders_and_stays_in_others(client, school_accounts):
    school, other, accounts = school_accounts
    sign_in(client, accounts['superadmin'])
    response = client.put('/api/map/school-location', json={'unmapped': True, 'school_id': other.id})
    assert response.status_code == 200
    assert response.get_json()['decision_required'] is False
    assert map_db_session.get(MapSchoolMapPreference, other.id) is None
    client.post('/api/auth/logout')
    sign_in(client, accounts['superadmin'])
    state = client.get('/api/map/school-location').get_json()
    assert state['location_state'] == 'unmapped'
    assert state['decision_required'] is False
    client.post('/api/auth/logout')
    listed = next(item for item in client.get('/api/map/schools').get_json()['schools'] if item['school_id'] == school.id)
    assert listed['unmapped'] is True
    assert listed['latitude'] is None and listed['longitude'] is None
    assert 'contact_email' not in listed


def test_switching_to_unmapped_removes_old_coordinates_and_can_be_reversed(client, school_accounts):
    school, _, accounts = school_accounts
    sign_in(client, accounts['superadmin'])
    client.put('/api/map/school-location', json=LOCATION)
    assert client.get('/api/map/school-location').get_json()['decision_required'] is False
    assert client.put('/api/map/school-location', json={'unmapped': True}).status_code == 200
    assert map_db_session.get(MapSchoolLocation, school.id) is None
    assert client.put('/api/map/school-location', json=LOCATION).status_code == 200
    state = client.get('/api/map/school-location').get_json()
    assert state['location_state'] == 'mapped'
    assert state['decision_required'] is False
    listed = next(item for item in client.get('/api/map/schools').get_json()['schools'] if item['school_id'] == school.id)
    assert listed['unmapped'] is False and listed['latitude'] == LOCATION['latitude']


@pytest.mark.parametrize('choice', ['true', 1, None, [], {}])
def test_invalid_unmapped_flag_cannot_suppress_the_reminder(client, school_accounts, choice):
    _, _, accounts = school_accounts
    sign_in(client, accounts['superadmin'])
    assert client.put('/api/map/school-location', json={'unmapped': choice}).status_code == 400
    assert client.get('/api/map/school-location').get_json()['decision_required'] is True


def test_interschool_admin_can_select_and_update_each_school_without_changing_the_other(client, school_accounts):
    school, other, accounts = school_accounts
    sign_in(client, accounts['inter_school'])
    for target, latitude in [(school, 10), (other, 20), (school, 30)]:
        url = f'/api/map/school-location?school_id={target.id}'
        state = client.get(url)
        assert state.status_code == 200
        assert state.get_json()['school_id'] == target.id
        assert state.get_json()['can_edit'] is True
        assert state.get_json()['decision_required'] is False
        result = client.put(url, json={**LOCATION, 'latitude': latitude, 'school_id': INTERSCHOOL_SCHOOL_ID})
        assert result.status_code == 200
        assert result.get_json()['location']['school_id'] == target.id
        assert map_db_session.get(MapSchoolLocation, target.id).updated_by_user_id == accounts['inter_school'].id
    assert map_db_session.get(MapSchoolLocation, school.id).latitude == 30
    assert map_db_session.get(MapSchoolLocation, other.id).latitude == 20
    assert map_db_session.query(MapSchoolLocation).filter_by(school_id=school.id).count() == 1
    assert map_db_session.get(MapSchoolLocation, INTERSCHOOL_SCHOOL_ID) is None


@pytest.mark.parametrize('role', ['user', 'admin', 'superadmin'])
def test_school_accounts_cannot_target_another_school_in_query(client, school_accounts, role):
    school, other, accounts = school_accounts
    sign_in(client, accounts[role])
    url = f'/api/map/school-location?school_id={other.id}'
    assert client.get(url).status_code == 403
    assert client.put(url, json=LOCATION).status_code == 403
    assert client.put(url, json={'unmapped': True}).status_code == 403
    assert map_db_session.get(MapSchoolLocation, other.id) is None
    assert map_db_session.get(MapSchoolMapPreference, other.id) is None
    assert map_db_session.get(MapSchoolLocation, school.id) is None


@pytest.mark.parametrize('target', [None, '', 'does-not-exist', INTERSCHOOL_SCHOOL_ID, 'disabled'])
def test_interschool_admin_must_choose_an_available_school(client, school_accounts, target):
    school, _, accounts = school_accounts
    if target == 'disabled':
        db_session.query(School).filter_by(id=school.id).update({'status': 'disabled'})
        db_session.commit()
        target = school.id
    sign_in(client, accounts['inter_school'])
    url = '/api/map/school-location' + (f'?school_id={target}' if target is not None else '')
    expected = 400 if target in (None, '') else 403
    assert client.get(url).status_code == expected
    assert client.put(url, json=LOCATION).status_code == expected


def test_interschool_unmapped_choice_updates_public_map_and_school_reminder(client, school_accounts):
    school, other, accounts = school_accounts
    sign_in(client, accounts['inter_school'])
    url = f'/api/map/school-location?school_id={school.id}'
    assert client.put(url, json=LOCATION).status_code == 200
    result = client.put(url, json={'unmapped': True})
    assert result.status_code == 200
    assert map_db_session.get(MapSchoolLocation, school.id) is None
    assert map_db_session.get(MapSchoolMapPreference, school.id).updated_by_user_id == accounts['inter_school'].id
    assert map_db_session.get(MapSchoolMapPreference, other.id) is None
    client.post('/api/auth/logout')
    listed = next(item for item in client.get('/api/map/schools').get_json()['schools'] if item['school_id'] == school.id)
    assert listed['location_state'] == 'unmapped'
    assert listed['latitude'] is None
    sign_in(client, accounts['superadmin'])
    assert client.get('/api/map/school-location').get_json()['decision_required'] is False
    client.post('/api/auth/logout')
    sign_in(client, accounts['inter_school'])
    assert client.put(url, json=LOCATION).status_code == 200
    assert map_db_session.get(MapSchoolMapPreference, school.id) is None
