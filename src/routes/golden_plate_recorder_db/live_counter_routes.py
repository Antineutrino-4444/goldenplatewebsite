"""School-scoped live plate totals and administrator-managed date ranges."""

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import jsonify, request, session
from sqlalchemy import case, func

from . import recorder_bp
from .db import School, Session, SessionRecord, _now_utc, db_session
from .security import get_current_user

DEFAULT_TIMEZONE = 'America/New_York'
CUSTOM_RANGE_IDS = {'custom-1', 'custom-2', 'custom-3'}


def _access():
    user = get_current_user()
    if user:
        if user['role'] == 'inter_school':
            return None, None, (jsonify({'error': 'Use a school account to view the live counter.'}), 403)
        school_id = user['school_id']
    elif session.get('guest_access') and session.get('school_id'):
        school_id = session['school_id']
    else:
        return None, None, (jsonify({'error': 'Sign in or enter a school code to view the live counter.'}), 401)
    school = db_session.query(School).filter_by(id=school_id, status='active').first()
    if not school:
        return None, None, (jsonify({'error': 'School is not available.'}), 403)
    return school, user, None


def _settings(school):
    settings = {
        'year': _now_utc().astimezone(ZoneInfo(DEFAULT_TIMEZONE)).year,
        'timezone': DEFAULT_TIMEZONE,
        'default_range': 'year',
        'milestone': None,
        'celebration_title': '',
        'celebration_message': '',
        'celebration_footer': '',
        'custom_ranges': [],
    }
    if school.live_counter_settings:
        settings.update(json.loads(school.live_counter_settings))
    return settings


def _validated_settings(data, existing, can_set_default):
    if not isinstance(data, dict):
        raise ValueError('Enter valid counter settings.')
    year = data.get('year')
    if type(year) is not int or not 1900 <= year <= 9998:
        raise ValueError('Year must be a whole number from 1900 to 9998.')
    timezone_name = data.get('timezone', existing['timezone'])
    if not isinstance(timezone_name, str) or len(timezone_name) > 100:
        raise ValueError('Choose a valid reporting timezone.')
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Choose a valid reporting timezone.') from None
    ranges = data.get('custom_ranges')
    if not isinstance(ranges, list) or len(ranges) > 3:
        raise ValueError('Save up to three custom date ranges.')
    validated = []
    used_ids = set()
    for item in ranges:
        if not isinstance(item, dict):
            raise ValueError('Enter valid custom date ranges.')
        identifier = item.get('id')
        if not isinstance(identifier, str) or identifier not in CUSTOM_RANGE_IDS or identifier in used_ids:
            raise ValueError('Each custom date range must use a different slot.')
        name = item.get('name', '')
        if not isinstance(name, str) or len(name.strip()) > 80:
            raise ValueError('Custom range names must be 80 characters or fewer.')
        dates = []
        for field in ('start_date', 'end_date'):
            value = item.get(field)
            if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError('Choose a start and end date for each custom range.')
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                raise ValueError('Choose valid calendar dates.') from None
            if not 1900 <= parsed.year <= 9998:
                raise ValueError('Custom dates must be between 1900 and 9998.')
            dates.append(parsed)
        if dates[0] > dates[1]:
            raise ValueError('The end date must be on or after the start date.')
        used_ids.add(identifier)
        validated.append({'id': identifier, 'name': name.strip(),
                          'start_date': dates[0].isoformat(), 'end_date': dates[1].isoformat()})
    default = data.get('default_range', existing['default_range'])
    if not can_set_default and default != existing['default_range']:
        raise PermissionError('Only superadmins can change the default time range.')
    if not isinstance(default, str) or default not in {'year', *used_ids}:
        raise ValueError('Choose a saved default range. Only a superadmin can replace or remove the current default.')
    milestone = data.get('milestone', existing['milestone'])
    if not can_set_default and milestone != existing['milestone']:
        raise PermissionError('Only superadmins can change the celebration milestone.')
    if milestone is not None and (type(milestone) is not int or not 1 <= milestone <= 1_000_000_000):
        raise ValueError('Set a clean-plate milestone from 1 to 1,000,000,000, or leave it blank to disable celebrations.')
    celebration = {}
    for field, label, limit in [('celebration_title', 'Banner title', 80),
                                ('celebration_message', 'Banner message', 300),
                                ('celebration_footer', 'Banner closing line', 120)]:
        value = data.get(field, existing[field])
        if not can_set_default and value != existing[field]:
            raise PermissionError('Only superadmins can change the celebration banner text.')
        if not isinstance(value, str) or len(value.strip()) > limit:
            raise ValueError(f'{label} must be text with {limit} characters or fewer.')
        celebration[field] = value.strip()
    return {'year': year, 'timezone': timezone_name, 'default_range': default,
            'custom_ranges': sorted(validated, key=lambda item: item['id']), 'milestone': milestone, **celebration}


def _utc_bounds(start, end, timezone_name):
    """Inclusive local calendar days, converted to a half-open UTC interval."""
    zone = ZoneInfo(timezone_name)
    lower = datetime.combine(date.fromisoformat(start), time.min, zone).astimezone(timezone.utc)
    upper = datetime.combine(date.fromisoformat(end) + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    return lower, upper


def _response(payload):
    response = jsonify(payload)
    response.headers['Cache-Control'] = 'no-store'
    return response


@recorder_bp.route('/live-counter/settings', methods=['PUT'])
def update_live_counter_settings():
    school, user, error = _access()
    if error:
        return error
    if not user or user['role'] not in {'admin', 'superadmin'}:
        return jsonify({'error': 'Admin or superadmin access required.'}), 403
    try:
        settings = _validated_settings(request.get_json(silent=True), _settings(school), user['role'] == 'superadmin')
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 403
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    school.live_counter_settings = json.dumps(settings)
    school.updated_at = _now_utc()
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to save date ranges. Please try again.'}), 500
    return _response({'status': 'success', 'settings': settings})


@recorder_bp.route('/live-counter', methods=['GET'])
def get_live_counter():
    school, user, error = _access()
    if error:
        return error
    settings = _settings(school)
    ranges = [{'id': 'year', 'name': str(settings['year']),
               'start_date': f"{settings['year']}-01-01", 'end_date': f"{settings['year']}-12-31"},
              *settings['custom_ranges']]
    columns = []
    bounds = []
    for index, item in enumerate(ranges):
        lower, upper = _utc_bounds(item['start_date'], item['end_date'], settings['timezone'])
        bounds.append((lower, upper))
        in_range = (SessionRecord.recorded_at >= lower) & (SessionRecord.recorded_at < upper)
        for category in ('clean', 'dirty', 'red', 'faculty'):
            columns.append(func.coalesce(func.sum(case(
                (in_range & (SessionRecord.category == category), 1), else_=0,
            )), 0).label(f'{category}_{index}'))
    query = db_session.query(*columns).select_from(SessionRecord).join(
        Session, (Session.id == SessionRecord.session_id) & (Session.school_id == SessionRecord.school_id),
    ).filter(SessionRecord.school_id == school.id,
             Session.status != 'discarded',
             SessionRecord.recorded_at >= min(lower for lower, _ in bounds),
             SessionRecord.recorded_at < max(upper for _, upper in bounds))
    # Keep private sessions private; never expose student identities here.
    if not user:
        query = query.filter(Session.is_public == 1)
    counts = query.one()._mapping
    results = []
    for index, item in enumerate(ranges):
        clean = int(counts[f'clean_{index}'])
        faculty = int(counts[f'faculty_{index}'])
        dirty = int(counts[f'dirty_{index}']) + int(counts[f'red_{index}'])
        total = clean + faculty + dirty
        results.append({**item, 'clean_count': clean + faculty,
                        'student_clean_count': clean, 'faculty_clean_count': faculty,
                        'total_records': total, 'dirty_count': dirty,
                        'clean_percentage': round((clean + faculty) / total * 100, 1) if total else 0})
    return _response({
        'school': {'name': school.name, 'code': school.slug},
        'settings': settings, 'ranges': results, 'scope': 'both',
        'can_manage_ranges': bool(user and user['role'] in {'admin', 'superadmin'}),
        'can_set_default': bool(user and user['role'] == 'superadmin'),
        'public_sessions_only': user is None,
        'updated_at': _now_utc().isoformat(), 'refresh_interval_seconds': 5,
    })
