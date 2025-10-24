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

    sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'error': 'Session not found'}), 404

    draw = get_or_create_session_draw(session_id)
    
    if not draw.winner_student_id:
        return jsonify({'error': 'No winner to finalize'}), 400

    if draw.finalized:
        return jsonify({'error': 'Draw already finalized'}), 400

    # Finalize the draw
    finalize_draw_db(draw, session.get('user_id'))
    
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

    sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'error': 'Session not found'}), 404

    draw = get_or_create_session_draw(session_id)
    
    if not draw.winner_student_id:
        return jsonify({'error': 'No draw to reset'}), 400

    if draw.finalized and not require_superadmin():
        return jsonify({'error': 'Only super admins can reset a finalized draw'}), 403

    # Reset the draw
    reset_draw_db(draw, session.get('user_id'))

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
    
    # Get student identifier or ID
    student_identifier = data.get('student_identifier')
    student_id = data.get('student_id')
    
    if not student_identifier and not student_id:
        return jsonify({'error': 'student_identifier or student_id required'}), 400

    # Find the student
    query = db_session.query(Student)
    if student_id:
        student = query.filter_by(id=student_id).first()
    else:
        student = query.filter_by(student_identifier=student_identifier).first()
    
    if not student:
        return jsonify({'error': 'Student not found'}), 404

    # Check if student has records in this session
    has_record = (
        db_session.query(SessionRecord)
        .filter(
            SessionRecord.session_id == session_id,
            SessionRecord.student_id == student.id
        )
        .first()
    )
    
    if not has_record:
        return jsonify({'error': 'Student has no records in this session'}), 400

    # Calculate tickets for this student
    ticket_balances = calculate_ticket_balances()
    winner_tickets = ticket_balances.get(student.id, 0.0)
    
    # Calculate probability
    eligible = get_eligible_students_with_tickets(session_id)
    total_tickets = sum(tickets for _, tickets in eligible)
    probability = (winner_tickets / total_tickets * 100.0) if total_tickets > 0 else 0.0

    # Get or create draw record
    draw = get_or_create_session_draw(session_id)
    
    # Update draw with override winner
    draw.winner_student_id = student.id
    draw.method = 'override'
    draw.tickets_at_selection = int(winner_tickets)
    draw.probability_at_selection = int(probability)
    draw.eligible_pool_size = len(eligible)
    draw.override_applied = 1
    draw.finalized = 1  # Auto-finalize overrides
    draw.finalized_by = session.get('user_id')
    draw.finalized_at = _now_utc()
    draw.updated_at = _now_utc()
    
    # Record the override event
    record_draw_event(
        draw=draw,
        event_type='override',
        user_id=session.get('user_id'),
        selected_student_id=student.id,
        tickets_at_event=winner_tickets,
        probability_at_event=probability,
        eligible_pool_size=len(eligible),
    )
    
    db_session.commit()

    winner_data = {
        'student_id': student.id,
        'student_identifier': student.student_identifier,
        'preferred_name': student.preferred_name,
        'last_name': student.last_name,
        'display_name': f"{student.preferred_name} {student.last_name}",
        'grade': student.grade,
        'advisor': student.advisor,
        'house': student.house,
        'clan': student.clan,
        'tickets': winner_tickets,
        'probability': probability,
    }

    return jsonify({
        'status': 'success',
        'override': True,
        'winner': winner_data,
    }), 200
