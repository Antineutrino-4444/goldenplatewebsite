import random
from datetime import datetime

from flask import jsonify, request, session
from sqlalchemy.exc import IntegrityError

from . import recorder_bp
from .db import Session as SessionModel, SessionRecord, Student, db_session
from .draw_db import (
    calculate_ticket_balances,
    finalize_draw,
    get_draw_history,
    get_eligible_students_with_tickets,
    get_or_create_session_draw,
    perform_weighted_draw,
    record_draw_event,
    reset_draw,
)
from .security import require_admin, require_auth_or_guest, require_superadmin

secure_random = random.SystemRandom()


@recorder_bp.route('/session/<session_id>/draw/summary', methods=['GET'])
def get_draw_summary(session_id):
    """Return draw summary for a session."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    if require_superadmin() is False and require_admin() is False:
        if session.get('guest_access') and not session_info.get('is_public', True):
            return jsonify({'error': 'Access denied'}), 403

    ensure_session_structure(session_info)
    summary, _ = get_ticket_summary_for_session(session_id)
    if not summary:
        summary = {
            'session_id': session_id,
            'session_name': session_info.get('session_name', ''),
            'created_at': session_info.get('created_at'),
            'is_discarded': session_info.get('is_discarded', False),
            'tickets_snapshot': {},
            'total_tickets': 0.0,
            'candidates': [],
            'top_candidates': [],
            'eligible_count': 0,
            'excluded_records': 0,
            'generated_at': datetime.now().isoformat()
        }

    response = {
        'session_id': session_id,
        'session_name': session_info.get('session_name', ''),
        'created_at': session_info.get('created_at'),
        'is_discarded': session_info.get('is_discarded', False),
        'total_tickets': summary.get('total_tickets', 0.0),
        'eligible_count': summary.get('eligible_count', 0),
        'excluded_records': summary.get('excluded_records', 0),
        'top_candidates': summary.get('top_candidates', []),
        'candidates': summary.get('candidates', []),
        'ticket_snapshot': summary.get('tickets_snapshot', {}),
        'generated_at': summary.get('generated_at', datetime.now().isoformat()),
        'draw_info': serialize_draw_info(session_info.get('draw_info', {}))
    }
    return jsonify(response), 200


@recorder_bp.route('/session/<session_id>/draw/start', methods=['POST'])
def start_draw(session_id):
    """Start a weighted random draw for a session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    ensure_session_structure(session_info)

    if session_info.get('is_discarded'):
        return jsonify({'error': 'Session is discarded from draw calculations'}), 400

    student_records_count = len(session_info.get('clean_records', [])) + len(session_info.get('red_records', []))
    if student_records_count <= 0:
        return jsonify({'error': 'No student records available for this session'}), 400

    summary, _ = get_ticket_summary_for_session(session_id)
    if not summary or summary.get('total_tickets', 0.0) <= 0:
        return jsonify({'error': 'No eligible tickets available for drawing'}), 400

    tickets_snapshot = summary.get('tickets_snapshot') or {}
    total_tickets = summary.get('total_tickets', 0.0)
    profiles = summary.get('profiles') or {}

    cumulative = 0.0
    target = secure_random.random() * total_tickets
    chosen_key = None
    for key, value in tickets_snapshot.items():
        cumulative += value
        if target <= cumulative:
            chosen_key = key
            break
    if chosen_key is None and tickets_snapshot:
        chosen_key = next(iter(tickets_snapshot))

    if chosen_key is None:
        return jsonify({'error': 'Unable to determine a winner'}), 400

    profile = profiles.get(chosen_key, {}).copy()
    if not profile:
        preferred, last = split_student_key(chosen_key)
        fallback_id = extract_student_id_from_key(chosen_key)
        profile = {
            'preferred_name': preferred.title() if preferred else '',
            'last_name': last.title() if last else '',
            'grade': '',
            'advisor': '',
            'house': '',
            'clan': '',
            'student_id': fallback_id
        }
    display_name = profile.get('display_name') or format_display_name(profile)
    winner_tickets = tickets_snapshot.get(chosen_key, 0.0)
    probability = (winner_tickets / total_tickets * 100.0) if total_tickets > 0 else 0.0

    winner_data = {
        'key': chosen_key,
        'preferred_name': profile.get('preferred_name', ''),
        'last_name': profile.get('last_name', ''),
        'display_name': display_name,
        'grade': profile.get('grade', ''),
        'advisor': profile.get('advisor', ''),
        'house': profile.get('house', ''),
        'clan': profile.get('clan', ''),
        'student_id': profile.get('student_id', ''),
        'tickets': winner_tickets,
        'probability': probability
    }

    timestamp = datetime.now().isoformat()
    draw_info = session_info['draw_info']
    draw_info['winner'] = winner_data
    draw_info['winner_timestamp'] = timestamp
    draw_info['selected_by'] = session.get('user_id')
    draw_info['method'] = 'random'
    draw_info['finalized'] = False
    draw_info['finalized_at'] = None
    draw_info['finalized_by'] = None
    draw_info['override'] = False
    draw_info['tickets_at_selection'] = total_tickets
    draw_info['probability_at_selection'] = probability
    draw_info['eligible_pool_size'] = summary.get('eligible_count', 0)

    history_entry = {
        'action': 'random_draw',
        'performed_by': session.get('user_id'),
        'timestamp': timestamp,
        'winner_key': chosen_key,
        'winner_display_name': display_name,
        'total_tickets': total_tickets,
        'winner_tickets': winner_tickets,
        'probability': probability
    }
    draw_info['history'].append(history_entry)

    save_session_data()

    updated_summary, _ = get_ticket_summary_for_session(session_id)
    return jsonify({
        'status': 'success',
        'winner': winner_data,
        'draw_info': serialize_draw_info(draw_info),
        'summary': updated_summary
    }), 200


@recorder_bp.route('/session/<session_id>/draw/finalize', methods=['POST'])
def finalize_draw(session_id):
    """Finalize the current draw winner for a session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    ensure_session_structure(session_info)
    draw_info = session_info.get('draw_info', {})
    winner = draw_info.get('winner')
    if not winner:
        return jsonify({'error': 'No winner to finalize'}), 400

    if not draw_info.get('finalized'):
        timestamp = datetime.now().isoformat()
        draw_info['finalized'] = True
        draw_info['finalized_at'] = timestamp
        draw_info['finalized_by'] = session.get('user_id')
        draw_info['history'].append({
            'action': 'finalized',
            'performed_by': session.get('user_id'),
            'timestamp': timestamp,
            'winner_key': winner.get('key'),
            'winner_display_name': winner.get('display_name')
        })
        save_session_data()

    updated_summary, _ = get_ticket_summary_for_session(session_id)
    return jsonify({
        'status': 'success',
        'finalized': True,
        'draw_info': serialize_draw_info(draw_info),
        'summary': updated_summary
    }), 200


@recorder_bp.route('/session/<session_id>/draw/reset', methods=['POST'])
def reset_draw(session_id):
    """Reset the draw for a session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    ensure_session_structure(session_info)
    draw_info = session_info.get('draw_info', {})
    winner = draw_info.get('winner')

    if not winner:
        return jsonify({'error': 'No draw to reset'}), 400

    if draw_info.get('finalized') and not require_superadmin():
        return jsonify({'error': 'Only super admins can reset a finalized draw'}), 403

    timestamp = datetime.now().isoformat()
    draw_info['history'].append({
        'action': 'reset',
        'performed_by': session.get('user_id'),
        'timestamp': timestamp,
        'previous_winner_key': winner.get('key'),
        'previous_winner_display_name': winner.get('display_name')
    })

    draw_info['winner'] = None
    draw_info['winner_timestamp'] = None
    draw_info['selected_by'] = None
    draw_info['method'] = None
    draw_info['finalized'] = False
    draw_info['finalized_at'] = None
    draw_info['finalized_by'] = None
    draw_info['override'] = False
    draw_info['tickets_at_selection'] = None
    draw_info['probability_at_selection'] = None
    draw_info['eligible_pool_size'] = None

    save_session_data()

    updated_summary, _ = get_ticket_summary_for_session(session_id)
    return jsonify({
        'status': 'success',
        'reset': True,
        'draw_info': serialize_draw_info(draw_info),
        'summary': updated_summary
    }), 200


@recorder_bp.route('/session/<session_id>/draw/override', methods=['POST'])
def override_draw(session_id):
    """Allow a super admin to override the draw winner."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    ensure_session_structure(session_info)

    if session_info.get('is_discarded'):
        return jsonify({'error': 'Session is discarded from draw calculations'}), 400

    student_records_count = len(session_info.get('clean_records', [])) + len(session_info.get('red_records', []))
    if student_records_count <= 0:
        return jsonify({'error': 'No student records available for this session'}), 400

    data = request.get_json(silent=True) or {}
    summary, _ = get_ticket_summary_for_session(session_id)
    if not summary:
        return jsonify({'error': 'Unable to load draw summary for this session'}), 400

    tickets_snapshot = summary.get('tickets_snapshot') or {}
    profiles = summary.get('profiles') or {}

    all_profiles = {}
    for key, profile in profiles.items():
        if isinstance(profile, dict):
            copied = profile.copy()
            copied.setdefault('key', key)
            copied.setdefault('display_name', format_display_name(copied))
            all_profiles[key] = copied

    for record in session_info.get('clean_records', []):
        profile = build_profile_from_record(record)
        key = profile.get('key')
        if key and key not in all_profiles:
            all_profiles[key] = profile

    for record in session_info.get('red_records', []):
        profile = build_profile_from_record(record)
        key = profile.get('key')
        if key and key not in all_profiles:
            all_profiles[key] = profile

    for key, info in student_lookup.items():
        if key not in all_profiles:
            profile = info.copy()
            profile['key'] = key
            profile['display_name'] = format_display_name(profile)
            all_profiles[key] = profile

    override_key_raw = data.get('student_key')
    override_key = str(override_key_raw or '').strip().lower()
    student_id = str(data.get('student_id', '')).strip()
    input_value = str(data.get('input_value', '')).strip()
    preferred = data.get('preferred_name')
    last = data.get('last_name')

    if not override_key and student_id:
        normalized_id = student_id.lower()
        match = next(
            (
                profile
                for profile in all_profiles.values()
                if str(profile.get('student_id', '')).strip().lower() == normalized_id
            ),
            None
        )
        if match:
            override_key = match.get('key')

    if not override_key and input_value:
        normalized_input = input_value.lower()
        match = next(
            (
                profile
                for profile in all_profiles.values()
                if (profile.get('display_name') or '').lower() == normalized_input
            ),
            None
        )
        if not match and input_value.isdigit():
            match = next(
                (
                    profile
                    for profile in all_profiles.values()
                    if str(profile.get('student_id', '')).strip() == input_value
                ),
                None
            )
        if match:
            override_key = match.get('key')

    if not override_key and ((preferred and last) or student_id):
        override_key = make_student_key(preferred, last, student_id)

    if not override_key:
        return jsonify({'error': 'Unable to determine the override candidate from the provided input'}), 400

    if override_key not in all_profiles:
        return jsonify({'error': 'Specified student was not found in the uploaded CSV'}), 400

    profile = all_profiles.get(override_key, {}).copy()
    if not profile:
        fallback_preferred, fallback_last = split_student_key(override_key)
        fallback_id = extract_student_id_from_key(override_key)
        profile = {
            'preferred_name': fallback_preferred.title() if fallback_preferred else '',
            'last_name': fallback_last.title() if fallback_last else '',
            'grade': '',
            'advisor': '',
            'house': '',
            'clan': '',
            'student_id': fallback_id
        }
    display_name = profile.get('display_name') or format_display_name(profile)
    winner_tickets = tickets_snapshot.get(override_key, 0.0)
    total_tickets = summary.get('total_tickets', 0.0)
    probability = (winner_tickets / total_tickets * 100.0) if total_tickets > 0 else 0.0

    winner_data = {
        'key': override_key,
        'preferred_name': profile.get('preferred_name', ''),
        'last_name': profile.get('last_name', ''),
        'display_name': display_name,
        'grade': profile.get('grade', ''),
        'advisor': profile.get('advisor', ''),
        'house': profile.get('house', ''),
        'clan': profile.get('clan', ''),
        'student_id': profile.get('student_id', ''),
        'tickets': winner_tickets,
        'probability': probability
    }

    timestamp = datetime.now().isoformat()
    draw_info = session_info['draw_info']
    draw_info['winner'] = winner_data
    draw_info['winner_timestamp'] = timestamp
    draw_info['selected_by'] = session.get('user_id')
    draw_info['method'] = 'random'
    draw_info['finalized'] = True
    draw_info['finalized_at'] = timestamp
    draw_info['finalized_by'] = session.get('user_id')
    draw_info['override'] = True
    draw_info['tickets_at_selection'] = summary.get('total_tickets', 0.0)
    draw_info['probability_at_selection'] = probability
    draw_info['eligible_pool_size'] = summary.get('eligible_count', 0)

    draw_info['history'].append({
        'action': 'override',
        'performed_by': session.get('user_id'),
        'timestamp': timestamp,
        'winner_key': override_key,
        'winner_display_name': display_name,
        'winner_tickets': winner_tickets,
        'probability': probability
    })

    save_session_data()

    updated_summary, _ = get_ticket_summary_for_session(session_id)
    return jsonify({
        'status': 'success',
        'override': True,
        'winner': winner_data,
        'draw_info': serialize_draw_info(draw_info),
        'summary': updated_summary
    }), 200


@recorder_bp.route('/session/<session_id>/draw/discard', methods=['POST'])
def toggle_discard(session_id):
    """Toggle whether a session is included in ticket calculations."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    ensure_session_structure(session_info)

    data = request.get_json(silent=True) or {}
    discard = bool(data.get('discarded'))

    timestamp = datetime.now().isoformat()
    message = 'Session state unchanged'
    if session_info.get('is_discarded') != discard:
        session_info['is_discarded'] = discard
        metadata = session_info.get('discard_metadata')
        if not isinstance(metadata, dict):
            metadata = {}
        if discard:
            metadata['discarded_by'] = session.get('user_id')
            metadata['discarded_at'] = timestamp
            message = 'Session discarded from draw calculations'
        else:
            metadata['restored_by'] = session.get('user_id')
            metadata['restored_at'] = timestamp
            message = 'Session reinstated for draw calculations'
        session_info['discard_metadata'] = metadata
        session_info['draw_info']['history'].append({
            'action': 'session_discarded' if discard else 'session_restored',
            'performed_by': session.get('user_id'),
            'timestamp': timestamp
        })
        save_session_data()

    summary, _ = get_ticket_summary_for_session(session_id)
    return jsonify({
        'status': 'success',
        'discarded': session_info.get('is_discarded', False),
        'message': message,
        'draw_info': serialize_draw_info(session_info.get('draw_info', {})),
        'summary': summary,
        'discard_metadata': session_info.get('discard_metadata', {})
    }), 200

