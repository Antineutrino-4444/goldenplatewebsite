from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from src.routes.golden_plate_recorder_db import place_search
from src.routes.golden_plate_recorder_db.map_db import (
    MapPlaceSearchCache, MapPlaceSearchQuota, map_db_session,
)


def feature(**properties):
    return {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [-79.47, 43.99]},
            'properties': {'name': 'Example Academy', 'city': 'Aurora', 'country': 'Canada',
                           'street': 'School Road', 'housenumber': '10',
                           'osm_type': 'W', 'osm_id': 123, **properties}}


@pytest.fixture(autouse=True)
def search_transport(monkeypatch):
    for model in (MapPlaceSearchCache, MapPlaceSearchQuota):
        map_db_session.query(model).delete()
    map_db_session.commit()
    get = Mock(return_value=SimpleNamespace(status_code=200, json=lambda: {'features': [feature()]}))
    monkeypatch.setattr(place_search, 'http_requests', SimpleNamespace(get=get, RequestException=requests.RequestException))
    monkeypatch.delenv('MAP_PLACE_SEARCH_URL', raising=False)
    yield get
    map_db_session.rollback()
    for model in (MapPlaceSearchCache, MapPlaceSearchQuota):
        map_db_session.query(model).delete()
    map_db_session.commit()


def test_public_search_returns_school_name_address_and_coordinates(client, search_transport):
    response = client.get('/api/map/places/search', query_string={'q': 'Example Academy Aurora'})
    assert response.status_code == 200
    assert response.get_json()['results'] == [{
        'name': 'Example Academy', 'address': '10 School Road, Aurora, Canada',
        'latitude': 43.99, 'longitude': -79.47, 'source': 'photon', 'place_id': 'W123',
    }]
    args, kwargs = search_transport.call_args
    assert args == (place_search.DEFAULT_SEARCH_URL,)
    assert kwargs['params'] == {'q': 'Example Academy Aurora', 'limit': 5, 'lang': 'en'}
    assert 'GoldenPlate' in kwargs['headers']['User-Agent']
    assert kwargs['timeout'] == (3, 8)


def test_repeated_search_uses_shared_cache(client, search_transport):
    first = client.get('/api/map/places/search?q=Example%20Academy')
    second = client.get('/api/map/places/search?q=EXAMPLE%20%20Academy')
    assert first.status_code == second.status_code == 200
    assert first.get_json() == second.get_json()
    assert search_transport.call_count == 1


def test_uncached_searches_are_throttled_across_requests(client, search_transport):
    client.get('/api/map/places/search?q=First%20Academy')
    response = client.get('/api/map/places/search?q=Second%20Academy')
    assert response.status_code == 429
    assert response.headers['Retry-After'] == '1'
    assert search_transport.call_count == 1


@pytest.mark.parametrize('query', ['', 'ab', 'x' * 201])
def test_invalid_query_never_contacts_provider(client, search_transport, query):
    assert client.get('/api/map/places/search', query_string={'q': query}).status_code == 400
    search_transport.assert_not_called()


def test_provider_failure_returns_actionable_error(client, search_transport):
    search_transport.side_effect = requests.Timeout('provider timeout')
    response = client.get('/api/map/places/search?q=Example%20Academy')
    assert response.status_code == 503
    assert 'place a pin' in response.get_json()['error']
    assert map_db_session.query(MapPlaceSearchCache).count() == 0


def test_provider_throttling_applies_application_backoff(client, search_transport):
    search_transport.return_value = SimpleNamespace(status_code=429)
    response = client.get('/api/map/places/search?q=Example%20Academy')
    assert response.status_code == 429
    assert response.headers['Retry-After'] == '30'
    assert client.get('/api/map/places/search?q=Other%20Academy').status_code == 429
    assert search_transport.call_count == 1


def test_malformed_provider_response_is_rejected(client, search_transport):
    search_transport.return_value = SimpleNamespace(status_code=200, json=lambda: {'unexpected': True})
    assert client.get('/api/map/places/search?q=Example%20Academy').status_code == 503


def test_empty_results_are_cached_and_invalid_positions_are_ignored(client, search_transport):
    invalid = feature()
    invalid['geometry']['coordinates'] = [float('inf'), 91]
    search_transport.return_value = SimpleNamespace(status_code=200, json=lambda: {'features': [invalid]})
    assert client.get('/api/map/places/search?q=Missing%20Academy').get_json()['results'] == []
    assert client.get('/api/map/places/search?q=Missing%20Academy').status_code == 200
    assert search_transport.call_count == 1


def test_provider_can_be_switched_without_changing_code(client, search_transport, monkeypatch):
    monkeypatch.setenv('MAP_PLACE_SEARCH_URL', 'https://search.example.com/api/')
    assert client.get('/api/map/places/search?q=Example%20Academy').status_code == 200
    assert search_transport.call_args.args == ('https://search.example.com/api/',)
