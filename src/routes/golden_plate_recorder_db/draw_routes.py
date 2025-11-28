"""Draw routes for database-backed system."""

from flask import jsonify, request, session

from . import recorder_bp
from .db import Session as SessionModel, SessionRecord, Student, _now_utc, db_session
from .draw_db import (
    calculate_ticket_balances,
    finalize_draw as finalize_draw_db,
    get_draw_history,
    get_eligible_students_with_tickets,
    get_or_create_session_draw,
    perform_weighted_draw,
    record_draw_event,
    reset_draw as reset_draw_db,
)
from .utils import extract_student_id_from_key, format_display_name, make_student_key, normalize_name
from .security import require_admin, require_auth_or_guest, require_superadmin


@recorder_bp.route('/session/<session_id>/draw/summary', methods=['GET'])
def get_draw_summary(session_id):
    """Return draw summary for a session."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'error': 'Session not found'}), 404

    # Check access permissions
    if require_superadmin() is False and require_admin() is False:
        if session.get('guest_access') and not sess.is_public:
            return jsonify({'error': 'Access denied'}), 403

    # Get eligible students with tickets
    eligible = get_eligible_students_with_tickets(session_id)
    total_tickets = sum(tickets for _, tickets in eligible)
    
    candidates = []
    for student, tickets in eligible:
        probability = (tickets / total_tickets * 100.0) if total_tickets > 0 else 0.0
        candidates.append({
            'student_id': student.id,
            'student_identifier': student.student_identifier,
            'preferred_name': student.preferred_name,
            'last_name': student.last_name,
            'display_name': f"{student.preferred_name} {student.last_name}",
            'grade': student.grade,
            'advisor': student.advisor,
            'house': student.house,
            'clan': student.clan,
            'tickets': tickets,
            'probability': probability,
        })
    
    # Get draw info
    draw = db_session.query(SessionModel.__table__.c.id).filter_by(id=session_id).first()
    draw_record = get_or_create_session_draw(session_id)
    
    draw_info = {
        'has_winner': draw_record.winner_student_id is not None,
        'finalized': bool(draw_record.finalized),
        'method': draw_record.method,
        'override_applied': bool(draw_record.override_applied),
        'tickets_at_selection': draw_record.tickets_at_selection,
        'probability_at_selection': draw_record.probability_at_selection,
        'eligible_pool_size': draw_record.eligible_pool_size,
        'finalized_at': draw_record.finalized_at.isoformat() if draw_record.finalized_at else None,
        'winner': None,
    }
    
    if draw_record.winner_student_id:
        winner = db_session.query(Student).filter_by(id=draw_record.winner_student_id).first()
        if winner:
            draw_info['winner'] = {
                'student_id': winner.id,
                'student_identifier': winner.student_identifier,
                'preferred_name': winner.preferred_name,
                'last_name': winner.last_name,
                'display_name': f"{winner.preferred_name} {winner.last_name}",
                'grade': winner.grade,
                'advisor': winner.advisor,
                'house': winner.house,
                'clan': winner.clan,
                'tickets': draw_record.tickets_at_selection,
                'probability': draw_record.probability_at_selection,
            }
    
    # Get history
    history = get_draw_history(session_id)
    
    response = {
        'session_id': session_id,
        'session_name': sess.session_name,
        'created_at': sess.created_at.isoformat() if sess.created_at else None,
        'status': sess.status,
        'total_tickets': total_tickets,
        'eligible_count': len(candidates),
        'top_candidates': candidates[:3],
        'candidates': candidates,
        'draw_info': draw_info,
        'history': history,
    }
    
    return jsonify(response), 200


@recorder_bp.route('/session/<session_id>/draw/start', methods=['POST'])
def start_draw(session_id):
    """Start a weighted random draw for a session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json(silent=True) or {}
    comment = (data.get('comment') or '').strip() or None

    sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'error': 'Session not found'}), 404

    if sess.status == 'discarded':
        return jsonify({'error': 'Session is discarded from draw calculations'}), 400

    # Check if there are any student records
    record_count = (
        db_session.query(SessionRecord)
        .filter(
            SessionRecord.session_id == session_id,
            SessionRecord.category.in_(['clean', 'red'])
        )
        .count()
    )
    
    if record_count == 0:
        return jsonify({'error': 'No student records available for this session'}), 400

    # Perform the draw
    winner, winner_tickets, probability, pool_size = perform_weighted_draw(
        session_id, session.get('user_id')
    )
    
    if not winner:
        return jsonify({'error': 'No eligible tickets available for drawing'}), 400

    # Get or create draw record
    draw = get_or_create_session_draw(session_id)
    
    # Update draw with winner
    draw.winner_student_id = winner.id
    draw.method = 'random'
    draw.tickets_at_selection = int(winner_tickets)
    draw.probability_at_selection = int(probability)
    draw.eligible_pool_size = pool_size
    draw.override_applied = 0
    draw.finalized = 0
    draw.finalized_by = None
    draw.finalized_at = None
    draw.updated_at = _now_utc()
    
    # Record the event
    record_draw_event(
        draw=draw,
        event_type='draw',
        user_id=session.get('user_id'),
        selected_student_id=winner.id,
        tickets_at_event=winner_tickets,
        probability_at_event=probability,
        eligible_pool_size=pool_size,
        comment=comment,
    )

    db_session.commit()

    winner_data = {
        'student_id': winner.id,
        'student_identifier': winner.student_identifier,
        'preferred_name': winner.preferred_name,
        'last_name': winner.last_name,
        'display_name': f"{winner.preferred_name} {winner.last_name}",
        'grade': winner.grade,
        'advisor': winner.advisor,
        'house': winner.house,
        'clan': winner.clan,
        'tickets': winner_tickets,
        'probability': probability,
    }

    return jsonify({
        'status': 'success',
        'winner': winner_data,
        'pool_size': pool_size,
    }), 200


@recorder_bp.route('/session/<session_id>/draw/finalize', methods=['POST'])
def finalize_draw_route(session_id):
    """Finalize the current draw winner for a session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json(silent=True) or {}
    comment = (data.get('comment') or '').strip() or None

    sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'error': 'Session not found'}), 404

    draw = get_or_create_session_draw(session_id)
    
    if not draw.winner_student_id:
        return jsonify({'error': 'No winner to finalize'}), 400

    if draw.finalized:
        return jsonify({'error': 'Draw already finalized'}), 400

    # Finalize the draw
    finalize_draw_db(draw, session.get('user_id'), comment)
    
    winner = db_session.query(Student).filter_by(id=draw.winner_student_id).first()

    return jsonify({
        'status': 'success',
        'finalized': True,
        'winner': {
            'student_id': winner.id,
            'student_identifier': winner.student_identifier,
            'preferred_name': winner.preferred_name,
            'last_name': winner.last_name,
            'display_name': f"{winner.preferred_name} {winner.last_name}",
        } if winner else None,
    }), 200


@recorder_bp.route('/session/<session_id>/draw/reset', methods=['POST'])
def reset_draw_route(session_id):
    """Reset the draw for a session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json(silent=True) or {}
    comment = (data.get('comment') or '').strip() or None

    sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'error': 'Session not found'}), 404

    draw = get_or_create_session_draw(session_id)
    
    if not draw.winner_student_id:
        return jsonify({'error': 'No draw to reset'}), 400

    if draw.finalized and not require_superadmin():
        return jsonify({'error': 'Only super admins can reset a finalized draw'}), 403

    # Reset the draw
    reset_draw_db(draw, session.get('user_id'), comment)

    return jsonify({
        'status': 'success',
        'reset': True,
    }), 200


@recorder_bp.route('/session/<session_id>/draw/override', methods=['POST'])
def override_draw(session_id):
    """Allow a super admin to override the draw winner."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'error': 'Session not found'}), 404

    if sess.status == 'discarded':
        return jsonify({'error': 'Session is discarded from draw calculations'}), 400

    data = request.get_json(silent=True) or {}
    comment = (data.get('comment') or '').strip() or None

    provided_key_raw = data.get('student_key')
    provided_key = normalize_name(provided_key_raw).lower()
    provided_identifier = normalize_name(data.get('student_identifier'))
    provided_student_id = normalize_name(data.get('student_id'))
    input_value = normalize_name(data.get('input_value'))
    provided_preferred = normalize_name(data.get('preferred_name'))
    provided_last = normalize_name(data.get('last_name'))

    if not any([provided_key, provided_identifier, provided_student_id, input_value, provided_preferred and provided_last]):
        return jsonify({'error': 'A student key, name, or identifier is required to override the draw winner'}), 400

    record_rows = (
        db_session.query(SessionRecord, Student)
        .outerjoin(Student, SessionRecord.student_id == Student.id)
        .filter(
            SessionRecord.session_id == session_id,
            SessionRecord.category.in_(['clean', 'red'])
        )
        .all()
    )

    if not record_rows:
        return jsonify({'error': 'No student records available for this session'}), 400

    ticket_balances = calculate_ticket_balances()
    eligible = get_eligible_students_with_tickets(session_id)
    total_tickets = sum(tickets for _, tickets in eligible)

    profiles = {}

    def merge_profile(profile):
        key = profile.get('key')
        if not key:
            return
        existing = profiles.get(key) or {}
        merged = {**profile}
        if existing:
            for field in ['student_id', 'student_identifier', 'preferred_name', 'last_name', 'grade', 'advisor', 'house', 'clan']:
                if not merged.get(field) and existing.get(field):
                    merged[field] = existing[field]
            merged['tickets'] = merged.get('tickets') or existing.get('tickets', 0.0)
            merged['display_name'] = merged.get('display_name') or existing.get('display_name')
        profiles[key] = merged

    for session_record, student in record_rows:
        preferred = normalize_name(session_record.preferred_name or (student.preferred_name if student else ''))
        last = normalize_name(session_record.last_name or (student.last_name if student else ''))
        student_identifier = normalize_name(student.student_identifier if student else '')
        if not student_identifier:
            student_identifier = extract_student_id_from_key(session_record.dedupe_key)
        key = make_student_key(preferred, last, student_identifier)
        profile = {
            'key': key,
            'preferred_name': preferred,
            'last_name': last,
            'grade': normalize_name(student.grade if student else ''),
            'advisor': normalize_name(student.advisor if student else ''),
            'house': normalize_name(student.house if student else ''),
            'clan': normalize_name(student.clan if student else ''),
            'student_id': student.id if student else None,
            'student_identifier': student_identifier,
        }
        profile['display_name'] = format_display_name(profile)
        if profile.get('student_id'):
            profile['tickets'] = ticket_balances.get(profile['student_id'], 0.0)
        merge_profile(profile)

    override_key = provided_key

    if not override_key and provided_identifier:
        match = next(
            (p for p in profiles.values() if normalize_name(p.get('student_identifier')).lower() == provided_identifier.lower()),
            None
        )
        if match:
            override_key = match.get('key')

    if not override_key and provided_student_id:
        match = next(
            (p for p in profiles.values() if normalize_name(p.get('student_id')) == provided_student_id),
            None
        )
        if match:
            override_key = match.get('key')

    if not override_key and input_value:
        normalized_input = input_value.lower()
        match = next(
            (p for p in profiles.values() if (p.get('display_name') or '').lower() == normalized_input),
            None
        )
        if not match and input_value.isdigit():
            match = next(
                (
                    p
                    for p in profiles.values()
                    if normalize_name(p.get('student_identifier')).lower() == normalized_input
                ),
                None
            )
        if match:
            override_key = match.get('key')

    if not override_key and provided_preferred and provided_last:
        override_key = make_student_key(provided_preferred, provided_last, provided_identifier)

    if not override_key:
        return jsonify({
            'error': 'Unable to determine the override candidate from the provided input',
            'details': 'Provide a student name, identifier, or override key for someone recorded in this session.'
        }), 400

    if override_key not in profiles:
        return jsonify({
            'error': 'Specified student is not part of this session',
            'details': 'Only students recorded in this session can be selected for an override.'
        }), 404

    profile = profiles[override_key]

    if not profile.get('student_id'):
        student_identifier = profile.get('student_identifier')
        if not student_identifier:
            return jsonify({
                'error': 'Student record is missing an identifier',
                'details': 'Add a student identifier to this entry or select another recorded student.'
            }), 400
        student = (
            db_session.query(Student)
            .filter_by(student_identifier=student_identifier, school_id=sess.school_id)
            .first()
        )
        if not student:
            student = Student(
                school_id=sess.school_id,
                student_identifier=student_identifier,
                preferred_name=profile.get('preferred_name') or profile.get('display_name'),
                last_name=profile.get('last_name') or '',
                grade=profile.get('grade'),
                advisor=profile.get('advisor'),
                house=profile.get('house'),
                clan=profile.get('clan'),
            )
            db_session.add(student)
            db_session.flush()
        profile['student_id'] = student.id

    winner_tickets = ticket_balances.get(profile['student_id'], 0.0)
    probability = (winner_tickets / total_tickets * 100.0) if total_tickets > 0 else 0.0

    draw = get_or_create_session_draw(session_id)

    draw.winner_student_id = profile['student_id']
    draw.method = 'random'
    draw.tickets_at_selection = int(winner_tickets)
    draw.probability_at_selection = int(probability)
    draw.eligible_pool_size = len(eligible)
    draw.override_applied = 0
    draw.finalized = 0
    draw.finalized_by = None
    draw.finalized_at = None
    draw.updated_at = _now_utc()

    record_draw_event(
        draw=draw,
        event_type='draw',
        user_id=session.get('user_id'),
        selected_student_id=profile['student_id'],
        tickets_at_event=winner_tickets,
        probability_at_event=probability,
        eligible_pool_size=len(eligible),
        comment=comment,
    )

    db_session.commit()

    winner_data = {
        'student_id': profile.get('student_id'),
        'student_identifier': profile.get('student_identifier'),
        'preferred_name': profile.get('preferred_name', ''),
        'last_name': profile.get('last_name', ''),
        'display_name': profile.get('display_name', ''),
        'grade': profile.get('grade', ''),
        'advisor': profile.get('advisor', ''),
        'house': profile.get('house', ''),
        'clan': profile.get('clan', ''),
        'tickets': winner_tickets,
        'probability': probability,
    }

    return jsonify({
        'status': 'success',
        'winner': winner_data,
        'pool_size': len(eligible),
    }), 200
