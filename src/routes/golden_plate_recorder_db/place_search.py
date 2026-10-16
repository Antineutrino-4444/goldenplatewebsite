"""Small, cached place searches through a configurable Photon service."""

import hashlib
import json
import math
import os
import time
from urllib.parse import urlparse

import requests as http_requests
from sqlalchemy.exc import IntegrityError

from .map_db import MapPlaceSearchCache, MapPlaceSearchQuota, map_db_session

DEFAULT_SEARCH_URL = 'https://photon.komoot.io/api/'
CACHE_SECONDS = 24 * 60 * 60


class PlaceSearchError(Exception):
    def __init__(self, message, status=503, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def _text(value, limit=200):
    return value.strip()[:limit] if isinstance(value, str) else ''


def _normalize_results(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('features'), list):
        raise PlaceSearchError('Place search returned an unexpected response. Please try again.')
    results = []
    seen = set()
    for feature in payload['features'][:20]:
        if not isinstance(feature, dict):
            continue
        geometry = feature.get('geometry') or {}
        properties = feature.get('properties') or {}
        if not isinstance(geometry, dict) or not isinstance(properties, dict):
            continue
        coordinates = geometry.get('coordinates')
        if geometry.get('type') != 'Point' or not isinstance(coordinates, list) or len(coordinates) < 2:
            continue
        try:
            if any(isinstance(value, bool) for value in coordinates[:2]):
                continue
            longitude, latitude = map(float, coordinates[:2])
        except (ValueError, TypeError, OverflowError):
            continue
        if not (math.isfinite(latitude) and math.isfinite(longitude)
                and -90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue
        street = ' '.join(filter(None, [_text(properties.get('housenumber')), _text(properties.get('street'))]))
        parts = [street] + [_text(properties.get(key)) for key in ('city', 'district', 'state', 'postcode', 'country')]
        address = ', '.join(dict.fromkeys(part for part in parts if part))[:500]
        name = _text(properties.get('name')) or street or address or 'Map location'
        identity = (name.casefold(), latitude, longitude)
        if identity in seen:
            continue
        seen.add(identity)
        osm_type = _text(properties.get('osm_type'), 10)
        osm_id = str(properties.get('osm_id', ''))[:50]
        results.append({
            'name': name, 'address': address, 'latitude': latitude, 'longitude': longitude,
            'source': 'photon', 'place_id': f'{osm_type}{osm_id}' if osm_type and osm_id else '',
        })
        if len(results) == 5:
            break
    return results


def search_places(query):
    url = os.environ.get('MAP_PLACE_SEARCH_URL', DEFAULT_SEARCH_URL).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise PlaceSearchError('Place search is not configured correctly.')
    now = time.time()
    key = hashlib.sha256(f'{url}\n{query.casefold()}'.encode()).hexdigest()
    cached = map_db_session.get(MapPlaceSearchCache, key)
    if cached and cached.expires_at > now:
        return json.loads(cached.results_json)

    quota_key = hashlib.sha256(url.encode()).hexdigest()
    if not map_db_session.get(MapPlaceSearchQuota, quota_key):
        map_db_session.add(MapPlaceSearchQuota(key=quota_key, next_allowed_at=0))
        try:
            map_db_session.commit()
        except IntegrityError:
            map_db_session.rollback()
    # The conditional update shares the limit across server workers.
    reserved = map_db_session.query(MapPlaceSearchQuota).filter(
        MapPlaceSearchQuota.key == quota_key, MapPlaceSearchQuota.next_allowed_at <= now,
    ).update({'next_allowed_at': now + 1}, synchronize_session=False)
    map_db_session.commit()
    if not reserved:
        raise PlaceSearchError('Place search is busy. Please wait a moment and search again.', 429, 1)

    try:
        response = http_requests.get(url, params={'q': query, 'limit': 5, 'lang': 'en'},
                                     headers={'User-Agent': 'GoldenPlate/1.0 (+https://goldenplate.ca)',
                                              'Accept': 'application/json'},
                                     timeout=(3, 8), allow_redirects=False)
        if response.status_code == 429:
            # Back off the whole application, not only the requesting browser.
            map_db_session.query(MapPlaceSearchQuota).filter_by(key=quota_key).update(
                {'next_allowed_at': time.time() + 30}, synchronize_session=False)
            map_db_session.commit()
            raise PlaceSearchError('Place search is busy. Please try again in 30 seconds.', 429, 30)
        if response.status_code != 200:
            raise PlaceSearchError('Place search is temporarily unavailable. You can still place a pin on the map.')
        results = _normalize_results(response.json())
    except (http_requests.RequestException, ValueError) as exc:
        raise PlaceSearchError('Place search could not connect. Please try again, or place a pin on the map.') from exc

    map_db_session.query(MapPlaceSearchCache).filter(MapPlaceSearchCache.expires_at <= now).delete()
    map_db_session.merge(MapPlaceSearchCache(key=key, results_json=json.dumps(results), expires_at=now + CACHE_SECONDS))
    map_db_session.commit()
    return results
