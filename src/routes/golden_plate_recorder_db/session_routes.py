import csv
import io
import json
import re
import uuid
from datetime import datetime

from flask import Response, current_app, jsonify, request, session
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from . import recorder_bp
import random
from .db import (
    DEFAULT_SCHOOL_ID,
    Session as SessionModel,
    SessionDeleteRequest,
    SessionDrawEvent,
    SessionRecord,
    RecordExclusionEvent,
    Student,
    Teacher,
    _now_utc,
    db_session,
)
from .domain import serialize_draw_info
from .person_identity import faculty_pick_names, record_names, teacher_names
from .users import readable_user_label, user_labels_for_school
from .draw_db import record_draw_event
from .house_scoring import house_score_settings
from .clean_percentage_estimation import estimate_session_percentages
from .session_metrics import session_metrics
from .roster_history import current_roster_snapshot, match_session_to_current_roster, prepare_recording_roster
from .security import get_current_user, is_guest, is_interschool_user, require_admin, require_auth, require_auth_or_guest
from .storage import (
    delete_requests,
    ensure_session_structure,
    get_dirty_count,
    get_session_entry,
    get_student_lookup_for_school,
    hydrate_session_from_db,
    save_delete_requests,
    save_session_data,
    session_data,
    update_student_lookup,
)
from .utils import (
    extract_student_id_from_key,
    format_display_name,
    make_student_key,
    normalize_house,
    normalize_name,
    plate_count_label,
    split_student_key,
)
from .manual_draw import MANUAL_STUDENT_PREFIX, manual_student_identifier


def _get_request_actor():
    user = get_current_user()
    if user:
        return user['id'], user['username'], user['school_id']
    return (
        session.get('user_uuid'),
        session.get('username') or session.get('user_id'),
        session.get('school_id', DEFAULT_SCHOOL_ID),
    )


def _forbid_interschool_accounts():
    if is_interschool_user():
        return jsonify({'error': 'Inter-school accounts cannot manage sessions'}), 403
    return None


def _isoformat_timestamp(value):
    if not value:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        try:
            return datetime.fromisoformat(str(value)).isoformat()
        except Exception:
            return str(value)


def _parse_iso_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _serialize_faculty_pick(db_sess, fallback=None):
    if db_sess and (
        db_sess.faculty_pick_display_name
        or db_sess.faculty_pick_preferred_name
        or db_sess.faculty_pick_last_name
    ):
        return {
            **faculty_pick_names(db_sess),
            'recorded_at': _isoformat_timestamp(db_sess.faculty_pick_recorded_at),
            'recorded_by': db_sess.faculty_pick_recorded_by,
            'finalized': bool(db_sess.faculty_finalized),
            'finalized_at': _isoformat_timestamp(db_sess.faculty_finalized_at),
            'finalized_by': db_sess.faculty_finalized_by,
        }
    if isinstance(fallback, dict) and fallback:
        return {
            'preferred_name': fallback.get('preferred_name'),
            'last_name': fallback.get('last_name'),
            'display_name': fallback.get('display_name'),
            'recorded_at': fallback.get('recorded_at'),
            'recorded_by': fallback.get('recorded_by'),
            'finalized': bool(fallback.get('finalized')),
            'finalized_at': fallback.get('finalized_at'),
            'finalized_by': fallback.get('finalized_by'),
        }
    return None


def _delete_session_with_dependencies(db_sess):
    """Remove a session and any dependent draw and record rows."""
    session_id = db_sess.id
    session_name = db_sess.session_name

    # Explicitly delete dependents because SQLite foreign key cascades
    # are easy to disable accidentally and we do not want orphan rows.
    db_session.query(RecordExclusionEvent).filter_by(session_id=session_id).delete(synchronize_session=False)
    db_session.query(SessionRecord).filter_by(session_id=session_id).delete(synchronize_session=False)
    db_session.query(SessionDrawEvent).filter_by(session_id=session_id).delete(synchronize_session=False)

    db_session.delete(db_sess)
    db_session.commit()

    save_delete_requests()

    if session_id in session_data:
        del session_data[session_id]
        save_session_data()

    if session.get('session_id') == session_id:
        session.pop('session_id', None)

    return session_name


@recorder_bp.route('/session/request-delete', methods=['POST'])
def request_delete_session():
    """Submit a delete request for a session."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    forbidden = _forbid_interschool_accounts()
    if forbidden:
        return forbidden

    data = request.get_json() or {}
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({'error': 'Session ID is required'}), 400

    actor_id, actor_username, school_id = _get_request_actor()

    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    current_user = get_current_user()

    if current_user['role'] in ['admin', 'superadmin']:
        session_name = _delete_session_with_dependencies(db_sess)

        return jsonify({
            'status': 'success',
            'message': f'Session "{session_name}" deleted successfully',
            'deleted_session_id': session_id
        }), 200

    existing = (
        db_session.query(SessionDeleteRequest)
        .filter(
            SessionDeleteRequest.session_id == session_id,
            SessionDeleteRequest.school_id == school_id,
            SessionDeleteRequest.status == 'pending'
        )
        .first()
    )
    if existing:
        return jsonify({'error': 'Delete request already submitted for this session'}), 400

    new_request = SessionDeleteRequest(
        school_id=school_id,
        session_id=session_id,
        requested_by=actor_id,
        status='pending'
    )

    try:
        db_session.add(new_request)
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Failed to submit delete request'}), 500

    refreshed_requests = save_delete_requests()

    request_obj = next((req for req in refreshed_requests if req['id'] == new_request.id), None)
    if not request_obj:
        request_obj = {
            'id': new_request.id,
            'session_id': session_id,
            'session_name': db_sess.session_name,
            'requester_id': actor_id,
            'requester': actor_username,
            'requester_name': current_user['name'],
            'requested_at': new_request.requested_at.isoformat() if new_request.requested_at else _now_utc().isoformat(),
            'status': new_request.status,
            'reviewed_by_id': None,
            'reviewed_by': None,
            'reviewed_at': None,
            'approved_by': None,
            'approved_at': None,
            'rejected_by': None,
            'rejected_at': None,
            'rejection_reason': None,
            'total_records': db_sess.total_records or 0,
            'clean_records': db_sess.clean_number or 0,
            'dirty_records': db_sess.dirty_number or 0,
            'red_records': db_sess.red_number or 0,
            'faculty_clean_records': db_sess.faculty_number or 0,
            'school_id': school_id,
        }

    return jsonify({
        'status': 'success',
        'message': f'Delete request submitted for "{db_sess.session_name}"',
        'request': request_obj
    }), 200


@recorder_bp.route('/session/create', methods=['POST'])
def create_session():
    """Create a new session."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    forbidden = _forbid_interschool_accounts()
    if forbidden:
        return forbidden

    data = request.get_json(silent=True) or {}
    custom_name = data.get('session_name', '').strip()
    is_public = data.get('is_public', True)

    session_id = str(uuid.uuid4())
    actor_id, actor_username, school_id = _get_request_actor()

    base_name = None
    counter = 1

    if custom_name:
        existing = db_session.query(SessionModel).filter_by(
            session_name=custom_name,
            school_id=school_id
        ).first()
        if existing:
            return jsonify({'error': 'Session name already exists'}), 400
        session_name = custom_name
    else:
        now = datetime.now()
        base_name = f"Golden_Plate_{now.strftime('%B_%d_%Y')}"
        session_name = base_name
        while db_session.query(SessionModel).filter_by(
            session_name=session_name,
            school_id=school_id
        ).first():
            session_name = f"{base_name}_{counter}"
            counter += 1

    def _make_session(name: str) -> SessionModel:
        snapshot = current_roster_snapshot(school_id, refresh=school_id == DEFAULT_SCHOOL_ID)
        return SessionModel(
            id=session_id,
            school_id=school_id,
            session_name=name,
            roster_snapshot_id=snapshot.id if snapshot else None,
            created_by=actor_id,
            is_public=1 if is_public else 0,
            status='active',
            clean_number=0,
            dirty_number=0,
            red_number=0,
            faculty_number=0,
            total_records=0,
            total_clean=0,
            total_dirty=0
        )

    new_session = _make_session(session_name)
    db_session.add(new_session)
    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
        if base_name is None:
            return jsonify({'error': 'Session name already exists'}), 400
        while True:
            candidate = f"{base_name}_{counter}"
            counter += 1
            if not db_session.query(SessionModel.id).filter_by(session_name=candidate, school_id=school_id).first():
                session_name = candidate
                break
        new_session = _make_session(session_name)
        db_session.add(new_session)
        try:
            db_session.commit()
        except IntegrityError:
            db_session.rollback()
            return jsonify({'error': 'Could not allocate unique session name'}), 500

    # Keep backward compatibility with JSON storage for draw_info and other features
    session_data[session_id] = {
        'session_name': session_name,
        'owner': actor_username,
        'school_id': school_id,
        'created_at': new_session.created_at.isoformat(),
        'clean_records': [],
        'dirty_count': 0,
        'red_records': [],
        'faculty_clean_records': [],
        'scan_history': [],
        'faculty_pick': None,
        'is_public': is_public,
        'draw_info': {
            'winner': None,
            'winner_timestamp': None,
            'selected_by': None,
            'method': None,
            'finalized': False,
            'finalized_at': None,
            'finalized_by': None,
            'history': [],
            'override': False,
            'tickets_at_selection': None,
            'probability_at_selection': None,
            'eligible_pool_size': None
        },
        'is_discarded': False,
        'discard_metadata': {}
    }

    save_session_data()
    session['session_id'] = session_id

    return jsonify({
        'session_id': session_id,
        'session_name': session_name,
        'owner': actor_username
    }), 200


@recorder_bp.route('/session/list', methods=['GET'])
def list_sessions():
    """List sessions. Guests only see public ones."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    if not is_guest():
        forbidden = _forbid_interschool_accounts()
        if forbidden:
            return forbidden

    _, _, school_id = _get_request_actor()
    delete_request_cache = save_delete_requests()
    current_delete_requests = [
        req for req in delete_request_cache
        if req.get('session_id') and req.get('school_id') == school_id
    ]

    query = db_session.query(SessionModel).filter(SessionModel.school_id == school_id)
    
    # Filter out non-public sessions for guests
    if is_guest():
        query = query.filter(SessionModel.is_public == 1)
    
    db_sessions = query.order_by(SessionModel.created_at.desc()).all()
    user_labels = user_labels_for_school(school_id)

    user_sessions = []
    for db_sess in db_sessions:
        # Use cached counts from session table
        clean_count = db_sess.clean_number or 0
        dirty_count = db_sess.dirty_number or 0
        red_count = db_sess.red_number or 0
        faculty_clean_count = db_sess.faculty_number or 0

        total_records = clean_count + dirty_count + red_count + faculty_clean_count
        combined_clean_count = clean_count + faculty_clean_count
        total_for_ratio = total_records

        clean_percentage = (combined_clean_count / total_for_ratio * 100) if total_for_ratio > 0 else 0
        dirty_percentage = ((dirty_count + red_count) / total_for_ratio * 100) if total_for_ratio > 0 else 0

        # Get draw_info from JSON storage for backward compatibility
        json_data = session_data.get(db_sess.id, {})
        if json_data.get('school_id') and json_data.get('school_id') != school_id:
            json_data = {}
        draw_info = serialize_draw_info(json_data.get('draw_info', {}))

        pending = any(
            req['session_id'] == db_sess.id and req['status'] == 'pending'
            for req in current_delete_requests
        )
        
        user_sessions.append({
            'session_id': db_sess.id,
            'session_name': db_sess.session_name,
            'owner': readable_user_label(db_sess.created_by, labels=user_labels),
            'total_records': total_records,
            'clean_count': clean_count,
            'dirty_count': dirty_count + red_count,
            'faculty_clean_count': faculty_clean_count,
            'clean_percentage': round(clean_percentage, 1),
            'dirty_percentage': round(dirty_percentage, 1),
            'is_public': bool(db_sess.is_public),
            'delete_requested': pending,
            'is_discarded': db_sess.status == 'discarded',
            'draw_info': draw_info,
            'main_session_id': db_sess.main_session_id,
            'is_extra': bool(db_sess.main_session_id),
        })

    return jsonify({
        'sessions': user_sessions,
        'has_global_csv': db_session.query(Student.id).filter(Student.school_id == school_id).first() is not None
    }), 200


@recorder_bp.route('/session/<session_id>/draw/discard', methods=['POST'])
def toggle_discard(session_id):
    """Reuse the legacy discard control with persistent session state."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    if user['role'] != 'superadmin':
        return jsonify({'error': 'Superadmin access required'}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or type(data.get('discarded')) is not bool:
        return jsonify({'error': 'Choose whether to discard or restore this session.'}), 400
    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=user['school_id']).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404
    discarded = data['discarded']
    if (db_sess.status == 'discarded') != discarded:
        db_sess.status = 'discarded' if discarded else 'active'
        db_sess.updated_at = _now_utc()
        db_sess.discarded_at = _now_utc() if discarded else None
        db_sess.discarded_by = user['id'] if discarded else None
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            return jsonify({'error': 'Unable to update discard status. Please try again.'}), 500
    cached = session_data.get(session_id)
    if cached is not None:
        cached['is_discarded'] = discarded
    return jsonify({'status': 'success', 'session_id': session_id, 'discarded': discarded,
                    'message': 'Session excluded from live totals and draws. Records remain saved.' if discarded
                    else 'Session restored to live totals and draws.'})


@recorder_bp.route('/session/switch/<session_id>', methods=['POST'])
def switch_session(session_id):
    """Switch to a different session. Guests may only access public sessions."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    _, _, school_id = _get_request_actor()

    if not is_guest():
        forbidden = _forbid_interschool_accounts()
        if forbidden:
            return forbidden

    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    if is_guest() and not db_sess.is_public:
        return jsonify({'error': 'Access denied'}), 403

    # Hydrate legacy session cache so subsequent calls can rely on it
    hydrate_session_from_db(session_id, session_model=db_sess)

    session['session_id'] = session_id

    return jsonify({
        'session_id': session_id,
        'session_name': db_sess.session_name,
        'owner': readable_user_label(db_sess.created_by, school_id=school_id),
    }), 200


@recorder_bp.route('/session/<session_id>/merge', methods=['POST'])
def merge_session(session_id):
    """Merge this session as an extra into a main session.

    Only admins and superadmins may combine sessions. The extra session's
    draw is disabled; its clean records are pooled into the main session's
    draw eligibility. Both sessions must belong to the same school, and
    neither chains nor self-merges are permitted.
    """
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    forbidden = _forbid_interschool_accounts()
    if forbidden:
        return forbidden

    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    _, _, school_id = _get_request_actor()

    data = request.get_json(silent=True) or {}
    main_session_id = (data.get('main_session_id') or '').strip()
    if not main_session_id:
        return jsonify({'error': 'main_session_id is required'}), 400

    if main_session_id == session_id:
        return jsonify({'error': 'A session cannot be merged into itself'}), 400

    extra_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not extra_sess:
        return jsonify({'error': 'Session not found'}), 404

    main_sess = db_session.query(SessionModel).filter_by(id=main_session_id, school_id=school_id).first()
    if not main_sess:
        return jsonify({'error': 'Main session not found'}), 404

    if main_sess.main_session_id:
        return jsonify({'error': 'The selected main session is itself an extra session'}), 400

    # Disallow merging a session that already has extras of its own
    has_dependents = (
        db_session.query(SessionModel.id)
        .filter(SessionModel.main_session_id == session_id)
        .first()
    )
    if has_dependents:
        return jsonify({'error': 'This session already has extras merged into it; remove them first'}), 400

    extra_sess.main_session_id = main_session_id
    extra_sess.updated_at = _now_utc()

    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Failed to merge sessions'}), 500

    return jsonify({
        'status': 'success',
        'message': f'Session "{extra_sess.session_name}" merged into "{main_sess.session_name}"',
        'session_id': extra_sess.id,
        'main_session_id': main_sess.id,
        'is_extra': True,
    }), 200


@recorder_bp.route('/session/<session_id>/unmerge', methods=['POST'])
def unmerge_session(session_id):
    """Remove the merge link so this session is no longer an extra."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    forbidden = _forbid_interschool_accounts()
    if forbidden:
        return forbidden

    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    _, _, school_id = _get_request_actor()

    extra_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not extra_sess:
        return jsonify({'error': 'Session not found'}), 404

    if not extra_sess.main_session_id:
        return jsonify({'error': 'Session is not currently merged'}), 400

    extra_sess.main_session_id = None
    extra_sess.updated_at = _now_utc()

    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Failed to unmerge session'}), 500

    return jsonify({
        'status': 'success',
        'message': f'Session "{extra_sess.session_name}" is no longer merged',
        'session_id': extra_sess.id,
        'main_session_id': None,
        'is_extra': False,
    }), 200


@recorder_bp.route('/session/delete/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session directly."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    forbidden = _forbid_interschool_accounts()
    if forbidden:
        return forbidden

    actor_id, _, school_id = _get_request_actor()
    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    current_user = get_current_user()

    if current_user['role'] == 'user' and db_sess.created_by != actor_id:
        return jsonify({'error': 'You can only delete sessions that you created'}), 403

    session_name = _delete_session_with_dependencies(db_sess)

    return jsonify({
        'status': 'success',
        'message': f'Session "{session_name}" deleted successfully',
        'deleted_session_id': session_id
    }), 200


@recorder_bp.route('/session/status', methods=['GET'])
def get_session_status():
    """Get current session status with percentage calculations."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    _, _, school_id = _get_request_actor()
    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    if is_guest() and not db_sess.is_public:
        return jsonify({'error': 'Access denied'}), 403

    # Get scan history count and draw_info from JSON storage for backward compatibility
    json_data = session_data.get(session_id, {})
    if json_data.get('school_id') and json_data.get('school_id') != school_id:
        json_data = {}
    ensure_session_structure(json_data)
    scan_history_count = len(json_data.get('scan_history', []))
    draw_info = serialize_draw_info(json_data.get('draw_info', {}))
    faculty_pick = _serialize_faculty_pick(db_sess, json_data.get('faculty_pick'))

    return jsonify({
        'session_id': session_id,
        'session_name': db_sess.session_name,
        'owner': readable_user_label(db_sess.created_by, school_id=school_id),
        **session_metrics(db_sess),
        'scan_history_count': scan_history_count,
        'is_discarded': db_sess.status == 'discarded',
        'draw_info': draw_info,
        'faculty_pick': faculty_pick,
        'main_session_id': db_sess.main_session_id,
        'is_extra': bool(db_sess.main_session_id),
    }), 200


@recorder_bp.route('/session/history', methods=['GET'])
def get_session_history():
    """Get scan history for current session."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400

    _, _, school_id = _get_request_actor()

    data = get_session_entry(session_id)
    if data is None or (data.get('school_id') and data.get('school_id') != school_id):
        return jsonify({'error': 'Session not found'}), 404
    if is_guest() and not data.get('is_public', True):
        return jsonify({'error': 'Access denied'}), 403

    data = hydrate_session_from_db(session_id, persist=False) or data
    return jsonify({
        'scan_history': data['scan_history']
    }), 200


@recorder_bp.route('/session/<session_id>/faculty/pick', methods=['GET', 'POST'])
def pick_random_faculty(session_id):
    """Return a random faculty clean record for the given session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    actor_id, _, school_id = _get_request_actor()
    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    if is_guest() and not db_sess.is_public:
        return jsonify({'error': 'Access denied'}), 403

    data = get_session_entry(session_id) or {}
    if data.get('school_id') and data.get('school_id') != school_id:
        data = {}

    data = hydrate_session_from_db(session_id, session_model=db_sess) or data
    ensure_session_structure(data)

    if db_sess.status == 'discarded':
        return jsonify({'error': 'Session is discarded from draw calculations'}), 400

    if db_sess.main_session_id:
        return jsonify({'error': 'Draws are disabled for extra sessions merged into a main session'}), 400

    faculty_records = [record for record in data.get('faculty_clean_records', [])
                       if format_display_name(record)]
    if not faculty_records:
        return jsonify({'error': 'No named faculty records available for this session'}), 400

    payload = request.get_json(silent=True) or {}
    if db_sess.faculty_finalized and payload.get('confirm_redraw') is not True:
        return jsonify({'error': 'Confirm repeating the finalized faculty draw. This action is recorded in the public draw log.'}), 409

    chosen = random.choice(faculty_records)
    preferred = normalize_name(chosen.get('preferred_name') or chosen.get('first_name'))
    last = normalize_name(chosen.get('last_name'))
    display_name = format_display_name({'preferred_name': preferred, 'last_name': last})
    recorded_at = chosen.get('timestamp')

    faculty_payload = {
        'preferred_name': preferred,
        'last_name': last,
        'display_name': display_name,
        'recorded_at': recorded_at,
        'recorded_by': chosen.get('recorded_by') or actor_id,
        'finalized': False,
        'finalized_at': None,
        'finalized_by': None,
    }

    db_sess.faculty_pick_preferred_name = preferred
    db_sess.faculty_pick_last_name = last
    db_sess.faculty_pick_display_name = display_name
    db_sess.faculty_pick_recorded_at = _parse_iso_timestamp(recorded_at)
    db_sess.faculty_pick_recorded_by = faculty_payload['recorded_by']
    db_sess.faculty_pick_record_id = chosen.get('record_id')
    db_sess.faculty_pick_teacher_id = chosen.get('teacher_id')
    faculty_payload['teacher_id'] = db_sess.faculty_pick_teacher_id
    db_sess.faculty_finalized = 0
    db_sess.faculty_finalized_at = None
    db_sess.faculty_finalized_by = None
    db_sess.updated_at = _now_utc()
    event = record_draw_event(db_sess, 'draw', actor_id, comment='Faculty draw')
    event.selected_record_id = db_sess.faculty_pick_record_id
    event.selected_teacher_id = db_sess.faculty_pick_teacher_id
    event.draw_target = 'faculty'
    event.faculty_name = display_name

    data['faculty_pick'] = faculty_payload
    session_data[session_id] = data
    save_session_data()
    db_session.commit()

    return jsonify({
        'status': 'success',
        'faculty': faculty_payload,
        'session_id': session_id
    }), 200


@recorder_bp.route('/session/<session_id>/faculty/finalize', methods=['POST'])
def finalize_faculty_winner(session_id):
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    actor_id, _, school_id = _get_request_actor()
    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404
    if db_sess.main_session_id or db_sess.status == 'discarded':
        return jsonify({'error': 'Faculty draws are unavailable for merged or discarded sessions'}), 400
    if not _serialize_faculty_pick(db_sess):
        return jsonify({'error': 'Choose a faculty winner first'}), 400
    if not db_sess.faculty_finalized:
        db_sess.faculty_finalized = 1
        db_sess.faculty_finalized_at = _now_utc()
        db_sess.faculty_finalized_by = actor_id
        db_sess.updated_at = _now_utc()
        # Recover the recorded faculty entry for winners selected before this update.
        if not db_sess.faculty_pick_record_id:
            record = db_session.query(SessionRecord).filter_by(
                session_id=session_id, category='faculty',
                preferred_name=db_sess.faculty_pick_preferred_name,
                last_name=db_sess.faculty_pick_last_name,
            ).first()
            db_sess.faculty_pick_record_id = record.id if record else None
        event = record_draw_event(db_sess, 'finalize', actor_id, comment='Faculty winner finalized')
        event.selected_record_id = db_sess.faculty_pick_record_id
        event.selected_teacher_id = faculty_pick_names(db_sess)['teacher_id']
        event.draw_target = 'faculty'
        event.faculty_name = _serialize_faculty_pick(db_sess)['display_name']
        db_session.commit()
    faculty = _serialize_faculty_pick(db_sess)
    data = get_session_entry(session_id)
    if data is not None:
        data['faculty_pick'] = faculty
    return jsonify({'status': 'success', 'faculty': faculty})


@recorder_bp.route('/session/<session_id>/roster/current', methods=['POST'])
def match_current_session_roster(session_id):
    """Match one session to this school's current roster, without changing plates."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    if not require_admin():
        return jsonify({'error': 'Admin or superadmin access required'}), 403
    actor_id, _, school_id = _get_request_actor()
    meal = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not meal:
        return jsonify({'error': 'Session not found'}), 404
    try:
        estimation = match_session_to_current_roster(meal, actor_id, house_score_settings(school_id))
        db_session.commit()
    except ValueError as exc:
        db_session.rollback()
        return jsonify({'error': str(exc)}), 400
    except SQLAlchemyError:
        db_session.rollback()
        return jsonify({'error': 'Unable to save the roster match. Please try again.'}), 500
    return jsonify({'status': 'success', 'session_id': session_id, 'estimation': estimation,
                    'message': 'Session matched to the current roster. Estimates have been recalculated.'})


@recorder_bp.route('/session/<session_id>/house-stats', methods=['GET'])
def get_house_stats(session_id):
    """Get house statistics for a specific session."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    _, _, school_id = _get_request_actor()

    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    if is_guest() and not db_sess.is_public:
        return jsonify({'error': 'Access denied'}), 403

    # Check if house data exists in the students table for this school
    has_house_data = db_session.query(Student.id).filter(
        Student.school_id == school_id,
        Student.house.isnot(None),
        Student.house != ''
    ).first() is not None

    score_settings = house_score_settings(school_id)

    # Get house statistics from session records
    records = (
        db_session.query(SessionRecord)
        .filter(
            SessionRecord.session_id == session_id,
            SessionRecord.school_id == school_id,
            SessionRecord.category.in_(['clean', 'dirty', 'red'])  # Only student categories
        )
        .all()
    )

    # Aggregate by house
    house_counts = {}
    total_with_house = 0

    for record in records:
        if record.is_excluded:
            continue
        # Anonymous counts never earn or deduct points, even if legacy data
        # accidentally includes a house. Only identifiable student plates rank.
        if not (record.student_id or (record.preferred_name or '').strip() or (record.last_name or '').strip()):
            continue
        house = normalize_house(record.house)
        if not house:
            # Try to get house from linked student
            if record.student_id:
                student = db_session.query(Student).filter_by(id=record.student_id, school_id=school_id).first()
                if student:
                    house = normalize_house(student.house)

        if house:
            if house not in house_counts:
                house_counts[house] = {'clean': 0, 'dirty': 0, 'red': 0, 'total': 0}
            house_counts[house][record.category] += 1
            house_counts[house]['total'] += 1
            total_with_house += 1

    # Calculate percentages and build response
    house_stats = []
    for house_name, counts in house_counts.items():
        percentage = (counts['total'] / total_with_house * 100) if total_with_house > 0 else 0
        clean_rate = (counts['clean'] / counts['total'] * 100) if counts['total'] > 0 else 0
        house_stats.append({
            'house': house_name,
            'clean_count': counts['clean'],
            'red_count': counts['red'],
            'dirty_count': counts['dirty'],
            'total_count': counts['total'],
            'percentage': round(percentage, 1),
            'clean_rate': round(clean_rate, 1),
            'score': (
                counts['clean'] * score_settings['clean_points']
                - counts['dirty'] * score_settings['dirty_penalty']
                - counts['red'] * score_settings['very_dirty_penalty']
            ),
        })

    # Recalculate from current settings so historical sessions update too.
    house_stats.sort(key=lambda x: (-x['score'], x['house']))

    return jsonify({
        'has_house_data': has_house_data or bool(house_stats),
        'message': 'No house data available in the student database' if not has_house_data and not house_stats else '',
        'score_settings': score_settings,
        'session_id': session_id,
        'session_name': db_sess.session_name,
        'total_records_with_house': total_with_house,
        'house_stats': house_stats,
        'estimation': estimate_session_percentages(
            db_sess, records, score_settings,
            include_separation=request.args.get('estimate_separation') == '1',
        ),
    }), 200


@recorder_bp.route('/session/scan-history', methods=['GET'])
def get_scan_history():
    """Get scan history for current session (formatted) from session_records table."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400

    session_id = session['session_id']
    _, _, school_id = _get_request_actor()

    # Verify session exists
    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404
    
    # Check guest access
    if is_guest() and not db_sess.is_public:
        return jsonify({'error': 'Access denied'}), 403

    # Get all records from session_records table
    records = (
        db_session.query(SessionRecord, Student, Teacher)
        .outerjoin(Student, SessionRecord.student_id == Student.id)
        .outerjoin(Teacher, SessionRecord.teacher_id == Teacher.id)
        .filter(
            SessionRecord.session_id == session_id,
            SessionRecord.school_id == school_id
        )
        .order_by(SessionRecord.recorded_at.desc())
        .all()
    )

    formatted_history = []
    for session_record, student, teacher in records:
        category = session_record.category.lower()
        
        labels = record_names(session_record, student=student, teacher=teacher)
        name = labels['display_name']
        
        # Handle special categories
        if not name:
            name = plate_count_label(category)

        formatted_history.append({
            'record_id': session_record.id,
            'is_excluded': bool(session_record.is_excluded),
            'exclusion_reason': session_record.exclusion_reason,
            'timestamp': session_record.recorded_at.isoformat() if session_record.recorded_at else '',
            'name': name,
            'recorded_name': labels['recorded_name'],
            'category': category.upper(),
            'is_manual_entry': bool(session_record.is_manual_entry),
            'is_count_only': not bool(session_record.student_id or session_record.preferred_name or session_record.last_name),
        })

    return jsonify({
        'scan_history': formatted_history
    }), 200


@recorder_bp.route('/record/<category>', methods=['POST'])
def record_student(category):
    try:
        return _record_student(category)
    except SQLAlchemyError:
        db_session.rollback()
        current_app.logger.exception('Unable to save plate record')
        return jsonify({'error': 'record_save_failed',
                        'message': 'The plate could not be saved. Please try again.'}), 503


def _record_student(category):
    """Record a student in a category."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    forbidden = _forbid_interschool_accounts()
    if forbidden:
        return forbidden

    actor_id, actor_username, school_id = _get_request_actor()

    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400

    session_info = get_session_entry(session_id)
    if session_info is None:
        return jsonify({'error': 'Session not found'}), 404

    if category not in ['clean', 'dirty', 'red', 'faculty']:
        return jsonify({'error': 'Invalid category'}), 400

    data = request.get_json(silent=True) or {}
    input_value = str(data.get('input_value', '') or '').strip()
    provided_student_id = normalize_name(data.get('student_id'))
    provided_teacher_id = normalize_name(data.get('teacher_id'))
    provided_key_raw = str(data.get('student_key') or '').strip()
    provided_key = provided_key_raw.lower() if provided_key_raw else ''
    provided_preferred = normalize_name(data.get('preferred_name') or data.get('preferred'))
    provided_last = normalize_name(data.get('last_name') or data.get('last'))

    ensure_session_structure(session_info)
    school_lookup = get_student_lookup_for_school(school_id)

    has_reference = bool(input_value or provided_student_id or provided_teacher_id or provided_key or
                         provided_preferred or provided_last)
    if not has_reference:
        if category != 'faculty':
            prepare_recording_roster(db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).one())
        # Each unnamed plate is a separate count, never a student or draw entry.
        record = {
            'category': category,
            'timestamp': datetime.now().isoformat(),
            'recorded_by': actor_username,
            'is_count_only': True,
            'display_name': plate_count_label(category),
        }
        records_key = 'faculty_clean_records' if category == 'faculty' else f'{category}_records'
        db_session.add(SessionRecord(
            school_id=school_id, session_id=session_id, category=category,
            recorded_by=actor_id, is_manual_entry=0,
            dedupe_key=f'count:{category}:{uuid.uuid4().hex}',
        ))
        db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
        if db_sess:
            count_field = {'clean': 'clean_number', 'dirty': 'dirty_number',
                           'red': 'red_number', 'faculty': 'faculty_number'}[category]
            setattr(db_sess, count_field, (getattr(db_sess, count_field) or 0) + 1)
            total_field = 'total_clean' if category in ['clean', 'faculty'] else 'total_dirty'
            setattr(db_sess, total_field, (getattr(db_sess, total_field) or 0) + 1)
            db_sess.total_records = (db_sess.total_records or 0) + 1
            db_sess.updated_at = datetime.now()
        db_session.commit()
        session_info[records_key].append(record)
        if category == 'dirty':
            session_info['dirty_count'] += 1
        session_info['scan_history'].append(record)
        save_session_data()
        return jsonify({
            'status': 'success', 'category': category, 'is_count_only': True,
            'dirty_count': session_info['dirty_count'], 'display_name': record['display_name'],
        }), 200

    if category == 'faculty':
        input_value = input_value or ' '.join(filter(None, [provided_preferred, provided_last]))
        if not input_value and not provided_teacher_id:
            return jsonify({'error': 'Faculty name is required'}), 400

        if provided_teacher_id:
            teacher = db_session.query(Teacher).filter_by(id=provided_teacher_id, school_id=school_id).first()
            if not teacher:
                return jsonify({'error': 'Faculty member not found'}), 404
        else:
            matches = db_session.query(Teacher).filter(Teacher.school_id == school_id, or_(
                func.lower(Teacher.display_name) == input_value.lower(),
                func.lower(Teacher.name) == input_value.lower(),
            )).all()
            if len(matches) > 1:
                return jsonify({'error': 'Multiple faculty members have this name. Select the person from the suggestions.'}), 409
            teacher = matches[0] if matches else None
        if teacher is None:
            parts = input_value.split(maxsplit=1)
            preferred_name = provided_preferred or parts[0].title()
            last_name = provided_last or (parts[1].title() if len(parts) > 1 else '')
            teacher = Teacher(school_id=school_id, name=f'{preferred_name} {last_name}'.strip(),
                              display_name=f'{preferred_name} {last_name}'.strip(),
                              preferred_name=preferred_name, last_name=last_name, is_active=0)
            db_session.add(teacher)
            db_session.flush()
        preferred_name, last_name, _ = teacher_names(teacher)

        # Persisted records are authoritative; an old cache cannot reject a save.
        existing_faculty = db_session.query(SessionRecord).filter(
            SessionRecord.session_id == session_id, SessionRecord.school_id == school_id,
            SessionRecord.category == 'faculty',
            or_(SessionRecord.teacher_id == teacher.id,
                (SessionRecord.teacher_id.is_(None)) &
                (SessionRecord.dedupe_key == f"faculty_{preferred_name.lower()}_{last_name.lower()}")),
        ).first()

        if existing_faculty:
            return jsonify({
                'error': 'duplicate',
                'existing_category': 'faculty',
                'message': 'This faculty member already has a FACULTY CLEAN plate recorded in this session. No new plate was added.'
            }), 409

        record = {
            'teacher_id': teacher.id,
            'preferred_name': preferred_name,
            'first_name': preferred_name,
            'last_name': last_name,
            'grade': '',
            'advisor': '',
            'house': '',
            'clan': '',
            'category': 'faculty',
            'timestamp': datetime.now().isoformat(),
                'recorded_by': actor_username,
            'is_manual_entry': True
        }
        
        # Save to database
        dedupe_key = f'faculty-id:{teacher.id}'
        db_record = SessionRecord(
            teacher_id=teacher.id,
            school_id=school_id,
            session_id=session_id,
            category='faculty',
            grade='',
            house='',
            recorded_by=actor_id,
            is_manual_entry=1,
            dedupe_key=dedupe_key,
            preferred_name=preferred_name,
            last_name=last_name
        )
        db_session.add(db_record)
        
        # Update session counts
        db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
        if db_sess:
            db_sess.faculty_number = (db_sess.faculty_number or 0) + 1
            db_sess.total_clean = (db_sess.total_clean or 0) + 1
            db_sess.total_records = (db_sess.total_records or 0) + 1
            db_sess.updated_at = datetime.now()
        
        db_session.commit()
        session_info['faculty_clean_records'].append(record)
        session_info['scan_history'].append(record)
        save_session_data()
        
        return jsonify({
            'status': 'success',
            'teacher_id': teacher.id,
            'preferred_name': preferred_name,
            'first_name': preferred_name,
            'last_name': last_name,
            'category': 'faculty',
            'is_manual_entry': True,
            'recorded_by': actor_username
        }), 200

    student_record = None
    lookup_profile = None
    dataset_match = False

    def build_student_record(student_obj):
        if not student_obj:
            return None
        preferred_val = str(student_obj.preferred_name or '').strip()
        last_val = str(student_obj.last_name or '').strip()
        return {
            'Preferred': preferred_val,
            'Last': last_val,
            'Grade': str(student_obj.grade or '').strip(),
            'Advisor': str(student_obj.advisor or '').strip(),
            'House': normalize_house(student_obj.house),
            'Clan': str(student_obj.clan or '').strip(),
            'Student ID': str(student_obj.student_identifier or '').strip()
        }

    candidate_ids = []
    if provided_student_id:
        candidate_ids.append(provided_student_id)
    key_id = extract_student_id_from_key(provided_key) if provided_key else ''
    if key_id:
        candidate_ids.append(key_id)
    if input_value:
        exact_identifier = (db_session.query(Student.student_identifier)
                            .filter(Student.school_id == school_id,
                                    func.lower(Student.student_identifier) == input_value.lower())
                            .first())
        if exact_identifier:
            candidate_ids.append(exact_identifier[0])
    if input_value.isdigit():
        candidate_ids.append(input_value)
    else:
        id_match = re.search(r'\b(\d{3,})\b', input_value)
        if id_match:
            candidate_ids.append(id_match.group(1))

    normalized_ids = []
    for candidate_id in candidate_ids:
        norm_id = normalize_name(candidate_id)
        if norm_id and norm_id not in normalized_ids:
            normalized_ids.append(norm_id)

    student_obj = None
    if normalized_ids:
        student_obj = (
            db_session.query(Student)
            .filter(
                Student.school_id == school_id,
                func.lower(Student.student_identifier) == normalized_ids[0].lower()
            )
            .first()
        )
        if student_obj:
            dataset_match = bool(student_obj.is_active)

    cleaned_input = input_value
    if cleaned_input:
        cleaned_input = re.sub(r'\([^)]*\)', '', cleaned_input).strip()

    candidate_preferred = provided_preferred
    candidate_last = provided_last

    if (not candidate_preferred or not candidate_last) and provided_key and not provided_key.startswith('id:'):
        key_preferred, key_last = split_student_key(provided_key)
        if key_preferred and not candidate_preferred:
            candidate_preferred = key_preferred
        if key_last and not candidate_last:
            candidate_last = key_last

    if not candidate_preferred or not candidate_last:
        name_parts = cleaned_input.split()
        if len(name_parts) >= 2:
            candidate_preferred = candidate_preferred or name_parts[0]
            candidate_last = candidate_last or ' '.join(name_parts[1:])
        elif len(name_parts) == 1:
            candidate_preferred = candidate_preferred or name_parts[0]
            candidate_last = candidate_last or ''

    name_matches = []
    if not student_obj and not normalized_ids and candidate_preferred and candidate_last:
        name_matches = (
            db_session.query(Student)
            .filter(Student.school_id == school_id)
            .filter(func.lower(Student.preferred_name) == candidate_preferred.lower())
            .filter(func.lower(Student.last_name) == candidate_last.lower())
            # Synthetic manual identities never stand in for a roster match.
            .filter(~func.lower(Student.student_identifier).like(f'{MANUAL_STUDENT_PREFIX}%'))
            .all()
        )
        if len(name_matches) == 1:
            student_obj = name_matches[0]
            dataset_match = bool(student_obj.is_active)

    student_record = build_student_record(student_obj)

    if not student_record and provided_key and not normalized_ids:
        lookup_profile = school_lookup.get(provided_key)
        if lookup_profile:
            dataset_match = True
    else:
        lookup_profile = None

    preferred_name = ''
    last_name = ''
    grade = ''
    advisor = ''
    house = ''
    clan = ''
    student_id = ''

    if student_record:
        preferred_name = str(student_record.get('Preferred', '') or '').strip()
        last_name = str(student_record.get('Last', '') or '').strip()
        grade = str(student_record.get('Grade', '') or '').strip()
        advisor = str(student_record.get('Advisor', '') or '').strip()
        house = normalize_house(student_record.get('House'))
        clan = str(student_record.get('Clan', '') or '').strip()
        student_id = str(student_record.get('Student ID', '') or '').strip()
    elif lookup_profile:
        preferred_name = normalize_name(lookup_profile.get('preferred_name'))
        last_name = normalize_name(lookup_profile.get('last_name'))
        grade = normalize_name(lookup_profile.get('grade'))
        advisor = normalize_name(lookup_profile.get('advisor'))
        house = normalize_house(lookup_profile.get('house'))
        clan = normalize_name(lookup_profile.get('clan'))
        student_id = normalize_name(lookup_profile.get('student_id'))
    else:
        preferred_name = normalize_name(candidate_preferred or (cleaned_input.split()[0] if cleaned_input else input_value))
        if cleaned_input:
            parts = cleaned_input.split()
            if len(parts) >= 2:
                candidate_last = candidate_last or ' '.join(parts[1:])
        last_name = normalize_name(candidate_last)

    if not preferred_name and provided_preferred:
        preferred_name = provided_preferred
    if not last_name and provided_last:
        last_name = provided_last
    if not student_id and provided_student_id:
        student_id = provided_student_id
    if not student_id and provided_key:
        extracted_id = extract_student_id_from_key(provided_key)
        if extracted_id:
            student_id = extracted_id
    if not student_id and normalized_ids:
        student_id = normalized_ids[0]

    preferred_name = preferred_name or ''
    last_name = last_name or ''
    grade = grade or ''
    advisor = advisor or ''
    house = house or ''
    clan = clan or ''
    student_id = student_id or ''

    student_key = make_student_key(preferred_name, last_name, student_id) or provided_key or None
    if student_key:
        student_key = student_key.lower()

    is_manual_entry = not dataset_match

    student_key = student_key or ''
    dedupe_key_to_check = student_key or f"{preferred_name.lower()}_{last_name.lower()}_{grade}_{house}"
    identity_filters = [SessionRecord.dedupe_key == dedupe_key_to_check]
    if student_obj:
        identity_filters.append(SessionRecord.student_id == student_obj.id)
    existing_record = db_session.query(SessionRecord).filter(
        SessionRecord.school_id == school_id, SessionRecord.session_id == session_id,
        or_(*identity_filters),
    ).first()
    if existing_record:
        existing_category = existing_record.category
        return jsonify({
            'error': 'duplicate',
            'existing_category': existing_category,
            'message': f'This student already has a {"VERY DIRTY" if existing_category == "red" else (existing_category or "student").upper()} plate recorded in this session. No new plate was added.'
        }), 409

    prepare_recording_roster(db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).one())
    record = {
        'preferred_name': preferred_name,
        'first_name': preferred_name,
        'last_name': last_name,
        'grade': grade,
        'advisor': advisor,
        'house': house,
        'clan': clan,
        'student_id': student_id,
        'student_key': student_key,
        'category': category,
        'timestamp': datetime.now().isoformat(),
        'recorded_by': actor_username,
        'is_manual_entry': is_manual_entry
    }

    # Save to database
    # Look up or create student in database. Name-only manual entries receive a
    # stable internal identity so their tickets can participate in the draw
    # without adding them to the current roster.
    db_student = None
    lookup_refresh_needed = False
    manual_identifier = (
        manual_student_identifier(preferred_name, last_name)
        if is_manual_entry and not student_id else ''
    )
    if student_id:
        db_student = (
            db_session.query(Student)
            .filter(Student.school_id == school_id,
                    func.lower(Student.student_identifier) == student_id.lower())
            .first()
        )
        if not db_student:
            db_student = Student(
                school_id=school_id,
                student_identifier=student_id,
                preferred_name=preferred_name,
                last_name=last_name,
                grade=grade,
                advisor=advisor,
                house=house,
                clan=clan,
                is_active=1 if dataset_match else 0,
            )
            db_session.add(db_student)
            db_session.flush()  # Get the ID
            lookup_refresh_needed = True
    elif manual_identifier:
        db_student = (
            db_session.query(Student)
            .filter(Student.school_id == school_id,
                    func.lower(Student.student_identifier) == manual_identifier.lower())
            .first()
        )
        if not db_student:
            db_student = Student(
                school_id=school_id,
                student_identifier=manual_identifier,
                preferred_name=preferred_name,
                last_name=last_name,
                grade=grade,
                advisor=advisor,
                house=house,
                clan=clan,
                is_active=0,
            )
            db_session.add(db_student)
            db_session.flush()  # Get the ID
    
    # Create dedupe key from student info
    dedupe_key = student_key or f"{preferred_name.lower()}_{last_name.lower()}_{grade}_{house}"
    
    db_record = SessionRecord(
        school_id=school_id,
        session_id=session_id,
        student_id=db_student.id if db_student else None,
        category=category,
        grade=grade,
        house=house,
        recorded_by=actor_id,
        is_manual_entry=1 if is_manual_entry else 0,
        dedupe_key=dedupe_key,
        preferred_name=preferred_name,
        last_name=last_name,
        student_profile=json.dumps({
            'Student ID': student_id, 'Preferred': preferred_name, 'Last': last_name,
            'Grade': grade, 'Advisor': advisor, 'House': house, 'Clan': clan,
            '_roster_conflicts': json.loads(db_student.roster_conflicts or '[]') if db_student else [],
            '_recording_candidates': [match.student_identifier for match in name_matches] if len(name_matches) > 1 else [],
            '_matched_by_name': len(name_matches) == 1,
            '_recording_conflicts': [
                {'field': 'Student ID', 'kept': student_id, 'other': candidate_id}
                for candidate_id in normalized_ids if candidate_id.casefold() != student_id.casefold()
            ] + [
                {'field': field, 'kept': actual, 'other': supplied}
                for field, actual, supplied in [('Preferred', preferred_name, provided_preferred),
                                               ('Last', last_name, provided_last)]
                if supplied and supplied.casefold() != actual.casefold()
            ],
        }, ensure_ascii=False),
    )
    db_session.add(db_record)
    db_session.flush()  # Flush to get db_record.id
    
    # Update session counts
    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if db_sess:
        if category == 'clean':
            db_sess.clean_number = (db_sess.clean_number or 0) + 1
            db_sess.total_clean = (db_sess.total_clean or 0) + 1
            db_sess.total_records = (db_sess.total_records or 0) + 1
        elif category == 'dirty':
            db_sess.dirty_number = (db_sess.dirty_number or 0) + 1
            db_sess.total_dirty = (db_sess.total_dirty or 0) + 1
            db_sess.total_records = (db_sess.total_records or 0) + 1
        elif category == 'red':
            db_sess.red_number = (db_sess.red_number or 0) + 1
            db_sess.total_dirty = (db_sess.total_dirty or 0) + 1
            db_sess.total_records = (db_sess.total_records or 0) + 1
        db_sess.updated_at = datetime.now()
    
    # Roster students keep a cumulative ticket ledger. Manual entries are
    # temporary to this session, so their tickets are replayed from the
    # session's records at draw time instead of growing a global balance.
    if db_student and db_student.id and not is_manual_entry:
        from .draw_db import update_tickets_for_record
        update_tickets_for_record(
            session_id=session_id,
            student_id=db_student.id,
            category=category,
            session_record_id=db_record.id,
            user_id=actor_id
        )
    
    db_session.commit()
    session_info[f'{category}_records'].append(record)
    if category == 'dirty':
        session_info['dirty_count'] += 1
    session_info['scan_history'].append(record)
    save_session_data()
    if lookup_refresh_needed:
        try:
            update_student_lookup()
        except Exception:
            # The record is committed. A cache refresh must not report a failed save.
            current_app.logger.exception('Plate saved, but student suggestions could not refresh')

    return jsonify({
        'status': 'success',
        'preferred_name': preferred_name,
        'first_name': preferred_name,
        'last_name': last_name,
        'grade': grade,
        'advisor': advisor,
        'house': house,
        'clan': clan,
        'student_id': student_id,
        'student_key': student_key,
        'category': category,
        'is_manual_entry': is_manual_entry,
        'recorded_by': actor_username
    }), 200


@recorder_bp.route('/export/csv', methods=['GET'])
def export_csv():
    """Export session records as CSV."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400

    _, _, school_id = _get_request_actor()

    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    data = get_session_entry(session_id)
    if data is None or (data.get('school_id') and data.get('school_id') != school_id):
        return jsonify({'error': 'Session not found'}), 404

    ensure_session_structure(data)

    output = io.StringIO()
    output.write("CLEAN,DIRTY,RED,FACULTY CLEAN\n")
    data = hydrate_session_from_db(session_id, persist=False, session_model=db_sess) or data

    def format_name(record, category):
        preferred = (record.get('preferred_name') or record.get('first_name', '') or '').strip()
        last = (record.get('last_name') or '').strip()
        full_name = f"{preferred} {last}".strip()
        return full_name or record.get('display_name') or plate_count_label(category)

    clean_names = [format_name(record, 'clean') for record in data['clean_records']]
    red_names = [format_name(record, 'red') for record in data['red_records']]
    faculty_names = [format_name(record, 'faculty') for record in data.get('faculty_clean_records', [])]
    dirty_count = get_dirty_count(data)

    max_records = max(
        len(clean_names),
        len(red_names),
        len(faculty_names),
        1 if dirty_count > 0 else 0
    )

    for i in range(max_records):
        clean_name = clean_names[i] if i < len(clean_names) else ""
        red_name = red_names[i] if i < len(red_names) else ""
        faculty_name = faculty_names[i] if i < len(faculty_names) else ""
        dirty_value = str(dirty_count) if i == 0 and dirty_count > 0 else ""

        output.write(f'"{clean_name}","{dirty_value}","{red_name}","{faculty_name}"\n')

    csv_content = output.getvalue()
    output.close()

    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{data["session_name"]}_records.csv"'}
    )


@recorder_bp.route('/export/csv/detailed', methods=['GET'])
def export_detailed_csv():
    """Export recorded student profiles with current-roster comparisons."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400

    _, _, school_id = _get_request_actor()

    db_sess = db_session.query(SessionModel).filter_by(id=session_id, school_id=school_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    # Read the database on every export so roster markers cannot be stale in the cache.
    from .session_exports import detailed_sessions_export
    csv_content, _ = detailed_sessions_export([db_sess], school_id, set(), sectioned=False)
    safe_name = re.sub(r'[^\w. -]', '_', db_sess.session_name).strip(' .-_')[:100] or 'session'
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{safe_name}_detailed_records.csv"',
                 'Cache-Control': 'no-store'}
    )


__all__ = []
