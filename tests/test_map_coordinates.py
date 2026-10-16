import pytest
from sqlalchemy import create_engine, inspect, text

from src.routes.golden_plate_recorder_db import map_db
from src.routes.golden_plate_recorder_db.map_db import MapPin, map_db_session


@pytest.mark.parametrize('latitude,longitude', [(43.99, -79.47), (0, 0), (-90, 180)])
def test_geographic_pin_round_trip(client, login, latitude, longitude):
    login()
    response = client.post('/api/map/pins', json={
        'name': 'World location', 'latitude': latitude, 'longitude': longitude,
    })
    assert response.status_code == 201
    pin = response.get_json()['pin']
    try:
        assert pin['latitude'] == latitude
        assert pin['longitude'] == longitude
        stored = next(item for item in client.get('/api/map/pins').get_json()['pins']
                      if item['id'] == pin['id'])
        assert stored['latitude'] == latitude
        assert stored['longitude'] == longitude
    finally:
        map_db_session.query(MapPin).filter_by(id=pin['id']).delete()
        map_db_session.commit()


@pytest.mark.parametrize('coordinates', [
    {'latitude': 10}, {'longitude': 10},
    {'latitude': None, 'longitude': None},
    {'latitude': True, 'longitude': 10},
    {'latitude': 10, 'longitude': False},
    {'latitude': 'north', 'longitude': 10},
    {'latitude': 91, 'longitude': 0},
    {'latitude': -91, 'longitude': 0},
    {'latitude': 0, 'longitude': 181},
    {'latitude': 0, 'longitude': -181},
    {'latitude': 'NaN', 'longitude': 0},
    {'latitude': 0, 'longitude': 'Infinity'},
])
def test_invalid_geographic_pin_is_rejected(client, coordinates):
    # Legacy x/y must not let an invalid geographic position fall through.
    response = client.post('/api/map/pins', json={
        'name': 'Invalid location', 'x': 50, 'y': 50, **coordinates,
    })
    assert response.status_code == 400
    assert response.get_json()['code'] in {
        'MAP_PIN_COORDS_INVALID', 'MAP_PIN_COORDS_OUT_OF_RANGE',
    }


def test_geographic_pin_keeps_existing_verification_requirement(client):
    client.post('/api/auth/logout')
    response = client.post('/api/map/pins', json={
        'name': 'Unverified', 'latitude': 40, 'longitude': -70,
    })
    assert response.status_code == 403
    assert response.get_json()['code'] == 'MAP_PIN_EMAIL_REQUIRED'


def test_original_map_pin_keeps_image_position(client, login):
    login()
    response = client.post('/api/map/pins', json={'name': 'Original', 'x': 12.5, 'y': 75})
    assert response.status_code == 201
    pin = response.get_json()['pin']
    try:
        assert (pin['x'], pin['y']) == (12.5, 75)
        assert pin['latitude'] is None
        assert pin['longitude'] is None
    finally:
        map_db_session.query(MapPin).filter_by(id=pin['id']).delete()
        map_db_session.commit()


def test_map_upgrade_preserves_original_positions(monkeypatch):
    temporary_engine = create_engine('sqlite://')
    try:
        with temporary_engine.begin() as connection:
            connection.execute(text('CREATE TABLE map_pins '
                                    '(id TEXT PRIMARY KEY, name TEXT, x FLOAT, y FLOAT)'))
            connection.execute(text("INSERT INTO map_pins VALUES ('old', 'Original', 25, 75)"))
        monkeypatch.setattr(map_db, 'map_engine', temporary_engine)
        map_db._bootstrap_map_database()
        map_db._bootstrap_map_database()
        assert {'latitude', 'longitude'} <= {
            column['name'] for column in inspect(temporary_engine).get_columns('map_pins')
        }
        with temporary_engine.connect() as connection:
            row = connection.execute(text('SELECT x, y, latitude, longitude FROM map_pins')).one()
        assert tuple(row) == (25, 75, None, None)
    finally:
        temporary_engine.dispose()


@pytest.fixture(autouse=True)
def _enable_archived_map_for_regression_tests(monkeypatch):
    monkeypatch.setenv("MAP_LEGACY_FEATURES_ENABLED", "true")
