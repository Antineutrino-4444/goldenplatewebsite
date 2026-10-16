import random

from flask import jsonify
from sqlalchemy import func

from . import recorder_bp
from .db import School, Session as SessionModel, _now_utc, db_session
from .session_metrics import session_metrics


def _available_sessions():
    return db_session.query(SessionModel, School).join(
        School, School.id == SessionModel.school_id,
    ).filter(
        SessionModel.is_public == 1,
        SessionModel.status != 'discarded',
        School.status == 'active',
    )


def _public_dashboard(row):
    db_sess, school = row
    # Explicit aggregate-only guest view: never serialize a roster, account,
    # winner or record. Free-text titles follow the school's guest privacy rule.
    return {
        'session_id': db_sess.id,
        'session_name': 'School session' if school.guest_privacy_enabled else db_sess.session_name,
        'school_name': school.name,
        'status': db_sess.status,
        'updated_at': db_sess.updated_at.isoformat() if db_sess.updated_at else None,
        **session_metrics(db_sess),
    }


def _response(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    # Both randomness and access/privacy changes must survive browser/CDN caches.
    response.headers['Cache-Control'] = 'no-store'
    return response


@recorder_bp.route('/public/sessions/random', methods=['GET'])
def random_public_session():
    query = _available_sessions()
    count = query.count()
    if not count:
        return _response({'session': None})
    row = query.order_by(SessionModel.id).offset(random.randrange(count)).first()
    return _response({'session': _public_dashboard(row) if row else None})


@recorder_bp.route('/public/sessions/<session_id>', methods=['GET'])
def public_session(session_id):
    row = _available_sessions().filter(SessionModel.id == session_id).first()
    if not row:
        return _response({'error': 'This session is no longer available to guests.'}, 404)
    # No guest login or cookie mutation: visitors can open the link without
    # replacing an existing school login or changing its selected session.
    return _response({'session': _public_dashboard(row)})


@recorder_bp.route('/public/counter', methods=['GET'])
def public_counter():
    # The initiative-wide total includes every school's saved sessions, even
    # private ones. Only these combined counts are public, never a breakdown.
    clean, sessions = db_session.query(
        func.coalesce(func.sum(func.coalesce(SessionModel.clean_number, 0)
                               + func.coalesce(SessionModel.faculty_number, 0)), 0),
        func.count(SessionModel.id),
    ).filter(SessionModel.status != 'discarded').one()
    return _response({'clean_count': int(clean), 'session_count': int(sessions),
                      'updated_at': _now_utc().isoformat(), 'refresh_interval_seconds': 5})
