import uuid

import pytest

from src.routes.golden_plate_recorder_db import school_map_routes
from src.routes.golden_plate_recorder_db.db import DEFAULT_SCHOOL_ID, School, Session, User, db_session
from src.routes.golden_plate_recorder_db.map_db import MapSchoolLocation, MapSchoolMapPreference, map_db_session


@pytest.fixture(autouse=True)
def legacy_disabled(monkeypatch):
    monkeypatch.delenv('MAP_LEGACY_FEATURES_ENABLED', raising=False)


@pytest.mark.parametrize('path', ['/map/background', '/map/background/info', '/map/pins',
                                 '/map/submissions', '/map/submissions/pending', '/map/leaderboard',
                                 '/map/featured', '/map/send-verification-code'])
def test_archived_ecological_features_are_disabled(client, path):
    response = client.get('/api' + path) if path != '/map/send-verification-code' else client.post('/api' + path)
    assert response.status_code == 410
    assert response.get_json()['code'] == 'MAP_LEGACY_DISABLED'


def test_public_school_codes_find_unmapped_schools_without_external_search(client, monkeypatch):
    client.get('/api/auth/status')
    map_db_session.query(MapSchoolLocation).filter_by(school_id=DEFAULT_SCHOOL_ID).delete()
    map_db_session.commit()
    def no_provider(*args, **kwargs):
        raise AssertionError('Known school codes must not be sent to the external provider')
    monkeypatch.setattr(school_map_routes, 'search_places', no_provider)
    for code in ('SAC', 'sac', ' SAC '):
        response = client.get('/api/map/places/search', query_string={'q': code})
        assert response.status_code == 200
        assert response.get_json()['provider'] == 'Golden Plate schools'
        school = response.get_json()['results'][0]
        assert school['school_id'] == DEFAULT_SCHOOL_ID
        assert school['code'] == 'SAC'
        assert school['latitude'] is None
        assert school['unmapped'] is True
        assert 'contact_email' not in school


def test_public_code_search_returns_only_explicitly_saved_coordinates(client, login):
    login()
    assert client.put('/api/map/school-location', json={'latitude': 44.01, 'longitude': -79.47}).status_code == 200
    client.post('/api/auth/logout')
    result = client.get('/api/map/places/search?q=SAC').get_json()['results'][0]
    assert result['latitude'] == 44.01 and result['longitude'] == -79.47
    assert result['unmapped'] is False
    map_db_session.query(MapSchoolLocation).filter_by(school_id=DEFAULT_SCHOOL_ID).delete()
    map_db_session.commit()


def test_inter_school_accounts_can_browse_the_public_school_map(client, login):
    login('inter-school-admin')
    assert client.get('/api/map/schools').status_code == 200
    assert client.get('/api/map/places/search?q=SAC').status_code == 200
    # Interschool admins can edit locations, but must explicitly choose a school.
    assert client.put('/api/map/school-location', json={'unmapped': True}).status_code == 400


def test_saved_school_location_search_resolves_codes_to_school_names(client, monkeypatch):
    client.get('/api/auth/status')
    requested = []
    from src.routes.golden_plate_recorder_db import school_map_routes
    monkeypatch.setattr(school_map_routes, 'search_places', lambda query: requested.append(query) or [])
    response = client.get('/api/map/places/search?q=SAC&scope=places')
    assert response.status_code == 200
    assert requested == [db_session.get(School, DEFAULT_SCHOOL_ID).name]


@pytest.mark.parametrize('state', ['mapped', 'pending', 'unmapped'])
def test_public_activity_counts_are_school_scoped_and_respect_session_visibility(client, login, state):
    login()
    creator = db_session.query(User).filter_by(username='greenguys').one().id
    school_id, empty_id = f'activity-{uuid.uuid4().hex}', f'empty-{uuid.uuid4().hex}'
    code = f'ACT-{uuid.uuid4().hex[:8]}'
    db_session.add_all([
        School(id=school_id, name='Activity Test School', slug=code),
        School(id=empty_id, name='School Without Sessions', slug=empty_id),
    ])
    db_session.commit()
    db_session.add_all([
        Session(school_id=school_id, created_by=creator, session_name='active', status='active', is_public=1),
        Session(school_id=school_id, created_by=creator, session_name='archived', status='archived', is_public=1),
        Session(school_id=school_id, created_by=creator, session_name='discarded', status='discarded', is_public=1),
        Session(school_id=school_id, created_by=creator, session_name='private', status='active', is_public=0),
        Session(school_id=school_id, created_by=creator, session_name='private archived', status='archived', is_public=0),
    ])
    db_session.commit()
    if state == 'mapped':
        map_db_session.add(MapSchoolLocation(school_id=school_id, latitude=44, longitude=-79, location_name='School'))
    elif state == 'unmapped':
        map_db_session.add(MapSchoolMapPreference(school_id=school_id, unmapped=1))
    map_db_session.commit()
    try:
        client.post('/api/auth/logout')
        schools = {school['school_id']: school for school in client.get('/api/map/schools').get_json()['schools']}
        assert schools[school_id]['session_count'] == 2
        assert schools[school_id]['location_state'] == state
        assert schools[empty_id]['session_count'] == 0
        found = client.get('/api/map/places/search', query_string={'q': code}).get_json()['results'][0]
        assert found['session_count'] == 2
        assert found['school_id'] == school_id
        assert 'sessions' not in found  # Only the aggregate is public.
        # Counts are fetched afresh rather than cached with location data.
        db_session.query(Session).filter_by(school_id=school_id, session_name='active').update({'is_public': 0})
        db_session.commit()
        refreshed = client.get('/api/map/places/search', query_string={'q': code}).get_json()['results'][0]
        assert refreshed['session_count'] == 1
    finally:
        map_db_session.query(MapSchoolLocation).filter_by(school_id=school_id).delete()
        map_db_session.query(MapSchoolMapPreference).filter_by(school_id=school_id).delete()
        map_db_session.commit()
        db_session.query(Session).filter_by(school_id=school_id).delete()
        db_session.query(School).filter(School.id.in_([school_id, empty_id])).delete(synchronize_session=False)
        db_session.commit()
