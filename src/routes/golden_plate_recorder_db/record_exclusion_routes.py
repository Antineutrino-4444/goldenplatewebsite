from flask import jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from . import recorder_bp
from .db import Session, SessionRecord, db_session
from .record_exclusions import review_records, set_record_excluded
from .security import get_current_user, require_auth, require_superadmin
from .storage import hydrate_session_from_db, save_session_data, session_data


def _authorized_session(session_id):
    if not require_auth():
        return None, (jsonify({'error': 'Authentication required'}), 401)
    if not require_superadmin():
        return None, (jsonify({'error': 'Superadmin access required'}), 403)
    user = get_current_user()
    meal = db_session.query(Session).filter_by(id=session_id, school_id=user['school_id']).first()
    if not meal:
        return None, (jsonify({'error': 'Session not found'}), 404)
    return meal, None


@recorder_bp.route('/session/<session_id>/calculation-records', methods=['GET'])
def calculation_records(session_id):
    meal, error = _authorized_session(session_id)
    if error:
        return error
    return jsonify({'records': review_records(meal)})


@recorder_bp.route('/session/<session_id>/records/<record_id>/exclusion', methods=['POST'])
def update_record_exclusion(session_id, record_id):
    meal, error = _authorized_session(session_id)
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or type(payload.get('excluded')) is not bool:
        return jsonify({'error': 'Specify excluded as true or false.'}), 400
    reason = payload.get('reason', '')
    if not isinstance(reason, str) or len(reason) > 1000:
        return jsonify({'error': 'Reason must be text of at most 1,000 characters.'}), 400
    row = db_session.query(SessionRecord).filter_by(
        id=record_id, session_id=meal.id, school_id=meal.school_id,
    ).first()
    if not row:
        return jsonify({'error': 'Record not found'}), 404
    try:
        reset_sessions = set_record_excluded(meal, row, payload['excluded'],
                                             get_current_user()['id'], reason.strip())
        db_session.commit()
    except SQLAlchemyError:
        db_session.rollback()
        return jsonify({'error': 'Unable to save this exclusion. Please try again.'}), 500
    # Rebuild derived JSON used by status, exports, and the legacy ticket rollup.
    hydrate_session_from_db(meal.id, session_model=meal, persist=False)
    for draw_id in reset_sessions:
        if draw_id in session_data:
            draw_info = session_data[draw_id].get('draw_info', {})
            draw_info.update(winner=None, finalized=False, finalized_at=None, finalized_by=None,
                             method=None, tickets_at_selection=None, probability_at_selection=None,
                             eligible_pool_size=None, override=False)
    save_session_data()
    return jsonify({'status': 'success', 'records': review_records(meal),
                    'reset_draw_session_ids': reset_sessions,
                    'message': 'Record excluded from calculations.' if payload['excluded']
                    else 'Record restored to calculations.'})
