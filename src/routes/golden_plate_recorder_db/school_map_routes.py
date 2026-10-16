import logging
import math

from flask import jsonify, request
from sqlalchemy import func, or_

from . import recorder_bp
from .db import INTERSCHOOL_SCHOOL_ID, School, Session, db_session
from .map_db import MapSchoolLocation, MapSchoolMapPreference, _map_now_utc, map_db_session
from .place_search import PlaceSearchError, search_places
from .security import get_current_user

logger = logging.getLogger(__name__)


def _public_session_counts(school_ids):
    # Keep private and discarded sessions out of this public activity signal.
    return dict(db_session.query(Session.school_id, func.count(Session.id)).filter(
        Session.school_id.in_(school_ids), Session.is_public == 1,
        Session.status.in_(('active', 'archived')),
    ).group_by(Session.school_id).all())


def _serialize_location(location, school, session_count=None):
    return {
        'id': f'school:{school.id}', 'type': 'school', 'school_id': school.id,
        'name': school.name, 'code': school.slug, 'location_name': location.location_name,
        'unmapped': False,
        'location_state': 'mapped',
        'address': location.address, 'latitude': location.latitude, 'longitude': location.longitude,
        'source': location.source, 'place_id': location.place_id,
        'updated_at': location.updated_at.isoformat() if location.updated_at else None,
        **({'session_count': session_count} if session_count is not None else {}),
    }


def _serialize_unmapped_school(school, state='unmapped', session_count=None):
    return {
        'id': f'school:{school.id}', 'type': 'school', 'school_id': school.id,
        'name': school.name, 'code': school.slug, 'unmapped': True,
        'location_state': state,
        'latitude': None, 'longitude': None,
        **({'session_count': session_count} if session_count is not None else {}),
    }


def _location_state(location, preference):
    if preference and preference.unmapped:
        return 'unmapped'
    return 'mapped' if location else 'pending'


@recorder_bp.route('/map/places/search', methods=['GET'])
def search_map_places():
    query = ' '.join(request.args.get('q', '').split())
    if not 1 <= len(query) <= 200:
        return jsonify({'error': 'Enter a school code, name, or address (up to 200 characters).'}), 400
    try:
        term = query.casefold()
        schools = db_session.query(School).filter(
            School.status == 'active', School.id != INTERSCHOOL_SCHOOL_ID,
            or_(func.lower(School.slug).contains(term, autoescape=True),
                func.lower(School.name).contains(term, autoescape=True)),
        ).order_by((func.lower(School.slug) == term).desc(), func.lower(School.name)).limit(8).all()
        if request.args.get('scope') == 'places':
            exact = next((school for school in schools if school.slug.casefold() == term), None)
            if exact:
                query = exact.name
        elif schools:
            results = []
            counts = _public_session_counts([school.id for school in schools])
            for school in schools:
                location = map_db_session.get(MapSchoolLocation, school.id)
                preference = map_db_session.get(MapSchoolMapPreference, school.id)
                state = _location_state(location, preference)
                count = counts.get(school.id, 0)
                results.append(_serialize_location(location, school, count) if state == 'mapped'
                               else _serialize_unmapped_school(school, state, count))
            return jsonify({'status': 'success', 'results': results, 'provider': 'Golden Plate schools'})
        if len(query) < 3:
            return jsonify({'error': 'No school matches that code. Enter at least 3 characters to search places.'}), 400
        results = search_places(query)
        return jsonify({'status': 'success', 'results': results, 'provider': 'Photon / OpenStreetMap'})
    except PlaceSearchError as exc:
        response = jsonify({'error': str(exc)})
        response.status_code = exc.status
        if exc.retry_after:
            response.headers['Retry-After'] = str(exc.retry_after)
        return response
    except Exception:
        map_db_session.rollback()
        logger.exception('Unable to search map places')
        return jsonify({'error': 'Place search is temporarily unavailable. Please try again.'}), 503


@recorder_bp.route('/map/schools', methods=['GET'])
def list_map_schools():
    locations = {location.school_id: location for location in map_db_session.query(MapSchoolLocation).all()}
    unmapped_ids = {entry.school_id for entry in map_db_session.query(MapSchoolMapPreference)
                    .filter_by(unmapped=1).all()}
    schools = db_session.query(School).filter(
        School.status == 'active', School.id != INTERSCHOOL_SCHOOL_ID,
    ).all()
    counts = _public_session_counts([school.id for school in schools])
    result = []
    for school in schools:
        count = counts.get(school.id, 0)
        if school.id in unmapped_ids:
            result.append(_serialize_unmapped_school(school, session_count=count))
        elif school.id in locations:
            result.append(_serialize_location(locations[school.id], school, count))
        else:
            result.append(_serialize_unmapped_school(school, 'pending', count))
    return jsonify({'status': 'success', 'schools': sorted(result, key=lambda item: item['name'].casefold())})


@recorder_bp.route('/map/school-location', methods=['GET', 'PUT'])
def school_map_location():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Sign in to choose your school location.'}), 401
    interschool = user['role'] == 'inter_school'
    requested_school_id = request.args.get('school_id')
    if interschool:
        if not requested_school_id or not requested_school_id.strip():
            return jsonify({'error': 'Choose a school to manage.'}), 400
        school_id = requested_school_id.strip()
    else:
        school_id = user['school_id']
        if requested_school_id is not None and requested_school_id != school_id:
            return jsonify({'error': 'You can only access your own school location.'}), 403
    school = db_session.get(School, school_id)
    if not school or school.status != 'active' or school.id == INTERSCHOOL_SCHOOL_ID:
        return jsonify({'error': 'School is unavailable.'}), 403
    can_edit = user['role'] in ('superadmin', 'inter_school')
    location = map_db_session.get(MapSchoolLocation, school.id)
    preference = map_db_session.get(MapSchoolMapPreference, school.id)
    if request.method == 'GET':
        state = _location_state(location, preference)
        response = jsonify({'school_id': school.id, 'school_name': school.name, 'can_edit': can_edit,
                            'location_state': state,
                            'decision_required': user['role'] == 'superadmin' and state == 'pending',
                            'location': _serialize_location(location, school) if state == 'mapped' else None})
        response.headers['Cache-Control'] = 'no-store'
        return response
    if not can_edit:
        return jsonify({'error': 'Only school superadmins and interschool admins can save school locations.'}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Choose a location on the map.'}), 400
    if 'unmapped' in data and type(data['unmapped']) is not bool:
        return jsonify({'error': 'Choose whether your school should remain unmapped.'}), 400
    if data.get('unmapped') is True:
        # Explicitly remove an earlier location rather than retaining hidden GPS data.
        if location:
            map_db_session.delete(location)
        if not preference:
            preference = MapSchoolMapPreference(school_id=school.id)
            map_db_session.add(preference)
        preference.unmapped = 1
        preference.updated_at = _map_now_utc()
        preference.updated_by_user_id = user['id']
        try:
            map_db_session.commit()
        except Exception:
            map_db_session.rollback()
            logger.exception('Unable to save unmapped school preference')
            return jsonify({'error': 'Unable to save your school map preference. Please try again.'}), 500
        return jsonify({'status': 'success', 'location_state': 'unmapped',
                        'decision_required': False, 'location': None})
    try:
        if any(isinstance(data.get(key), bool) for key in ('latitude', 'longitude')):
            raise ValueError
        latitude, longitude = float(data.get('latitude')), float(data.get('longitude'))
        if not (math.isfinite(latitude) and math.isfinite(longitude)
                and -90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        return jsonify({'error': 'Choose a valid location on the map.'}), 400
    name = data.get('location_name', school.name)
    address = data.get('address', '')
    place_id = data.get('place_id') or ''
    source = data.get('source', 'manual')
    if (not isinstance(name, str) or not name.strip() or len(name) > 200
            or not isinstance(address, str) or len(address) > 500
            or not isinstance(place_id, str) or len(place_id) > 100
            or source not in ('manual', 'photon')):
        return jsonify({'error': 'Choose a valid school name and address.'}), 400
    if not location:
        location = MapSchoolLocation(school_id=school.id)
        map_db_session.add(location)
    location.latitude, location.longitude = latitude, longitude
    location.location_name, location.address = name.strip(), address.strip()
    location.place_id, location.source = place_id or None, source
    location.updated_at = _map_now_utc()
    location.updated_by_user_id = user['id']
    if preference:
        map_db_session.delete(preference)
    try:
        map_db_session.commit()
    except Exception:
        map_db_session.rollback()
        logger.exception('Unable to save school location')
        return jsonify({'error': 'Unable to save your school location. Please try again.'}), 500
    return jsonify({'status': 'success', 'location_state': 'mapped',
                    'decision_required': False, 'location': _serialize_location(location, school)})
