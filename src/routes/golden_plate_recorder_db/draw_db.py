"""Database operations for draw system."""
import random
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import func, or_
from .users import readable_user_label, user_labels_for_school

from .db import (
    DEFAULT_SCHOOL_ID,
    DraftPool,
    Session as SessionModel,
    SessionDrawEvent,
    SessionRecord,
    SessionTicketEvent,
    Student,
    Teacher,
    _now_utc,
    db_session,
)
from .person_identity import teacher_names

secure_random = random.SystemRandom()


def _resolve_school_id(session_id: Optional[str] = None, student_id: Optional[str] = None) -> str:
    if session_id:
        session = db_session.query(SessionModel.school_id).filter_by(id=session_id).first()
        if session and session[0]:
            return session[0]
    if student_id:
        student = db_session.query(Student.school_id).filter_by(id=student_id).first()
        if student and student[0]:
            return student[0]
    return DEFAULT_SCHOOL_ID


def get_or_create_session_draw(session_id: str) -> SessionModel:
    """Return the session row that holds draw state."""
    session = db_session.query(SessionModel).filter_by(id=session_id).first()
    if session is None:
        raise ValueError(f'Session {session_id} not found')

    # Ensure draw-related defaults are populated without forcing a commit.
    updated = False
    if session.draw_number is None:
        session.draw_number = 1
        updated = True
    if session.finalized is None:
        session.finalized = 0
        updated = True
    if session.override_applied is None:
        session.override_applied = 0
        updated = True

    if updated:
        session.updated_at = _now_utc()
        db_session.flush()

    return session


def calculate_ticket_balances() -> Dict[str, float]:
    """Return stored cumulative ticket balances for all students.

    This is the roster ledger.  Manual entries are replayed from their
    session's records instead; see :func:`get_draw_ticket_totals`.
    """
    pool_entries = (
        db_session.query(DraftPool.student_id, DraftPool.ticket_number)
        .join(Student, DraftPool.student_id == Student.id)
        .filter(DraftPool.ticket_number > 0)
        .all()
    )

    return {
        student_id: float(ticket_number)
        for student_id, ticket_number in pool_entries
        if student_id
    }


def get_session_ids_for_draw(session_id: str) -> List[str]:
    """Return the session id plus any extra sessions merged into it.

    If the supplied session is itself an extra (has a ``main_session_id``),
    only the session id is returned, since extra sessions cannot host a draw.
    """
    session = db_session.query(SessionModel).filter_by(id=session_id).first()
    if session is None:
        return [session_id]

    if session.main_session_id:
        return [session_id]

    extra_rows = (
        db_session.query(SessionModel.id)
        .filter(SessionModel.main_session_id == session_id)
        .all()
    )
    return [session_id] + [row[0] for row in extra_rows]


def get_clean_student_ids_for_session(session_id: str) -> Set[str]:
    """Return student IDs with a clean-plate record in the session or its extras."""
    session_ids = get_session_ids_for_draw(session_id)
    rows = (
        db_session.query(SessionRecord.student_id)
        .filter(
            SessionRecord.session_id.in_(session_ids),
            SessionRecord.category == 'clean',
            SessionRecord.is_excluded == 0,
            SessionRecord.student_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {student_id for (student_id,) in rows if student_id}


def get_draw_eligible_student_ids(session_id: str) -> Set[str]:
    """Return student IDs eligible for this session's draw.

    A current-session clean plate is required.  Active roster students qualify
    as before.  A student recorded through a manual entry also qualifies even
    though manual entries stay outside the current roster.
    """
    session_ids = get_session_ids_for_draw(session_id)
    rows = (
        db_session.query(SessionRecord.student_id)
        .join(Student, SessionRecord.student_id == Student.id)
        .filter(
            SessionRecord.session_id.in_(session_ids),
            SessionRecord.category == 'clean',
            SessionRecord.is_excluded == 0,
            SessionRecord.student_id.isnot(None),
            or_(Student.is_active == 1, SessionRecord.is_manual_entry == 1),
        )
        .distinct()
        .all()
    )
    return {student_id for (student_id,) in rows if student_id}


def is_manual_draw_participant(session_id: str, student_id: Optional[str]) -> bool:
    """Return whether a student earned draw eligibility through a manual plate."""
    if not student_id:
        return False
    session_ids = get_session_ids_for_draw(session_id)
    return db_session.query(SessionRecord.id).filter(
        SessionRecord.session_id.in_(session_ids),
        SessionRecord.student_id == student_id,
        SessionRecord.category == 'clean',
        SessionRecord.is_excluded == 0,
        SessionRecord.is_manual_entry == 1,
    ).first() is not None


def get_manual_student_ids_for_draw(session_id: str) -> Set[str]:
    """Return students whose draw tickets are local to this session.

    Manual entries are intentionally temporary.  Their tickets are replayed
    from this session's records instead of the cumulative roster ticket pool,
    so a new session always starts them at zero.
    """
    session_ids = get_session_ids_for_draw(session_id)
    rows = (
        db_session.query(SessionRecord.student_id)
        .filter(
            SessionRecord.session_id.in_(session_ids),
            SessionRecord.category.in_(['clean', 'red']),
            SessionRecord.is_excluded == 0,
            SessionRecord.is_manual_entry == 1,
            SessionRecord.student_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {student_id for (student_id,) in rows if student_id}


def get_manual_session_ticket_total(session_id: str, student_id: str) -> float:
    """Replay one manual participant's clean/red records in this draw scope."""
    session_ids = get_session_ids_for_draw(session_id)
    # A finalization remains historical even if the draw is later reset or
    # overridden. Plate records from that finalization are already consumed.
    finalized_at = db_session.query(func.max(SessionDrawEvent.created_at)).filter(
        SessionDrawEvent.session_id == session_id,
        SessionDrawEvent.event_type == 'finalize',
        SessionDrawEvent.selected_student_id == student_id,
    ).scalar()
    query = db_session.query(SessionRecord.category).filter(
        SessionRecord.session_id.in_(session_ids),
        SessionRecord.student_id == student_id,
        SessionRecord.is_excluded == 0,
        SessionRecord.category.in_(['clean', 'red']),
    )
    if finalized_at is not None:
        query = query.filter(SessionRecord.recorded_at > finalized_at)
    rows = query.order_by(SessionRecord.recorded_at, SessionRecord.id).all()
    balance = 0
    for (category,) in rows:
        balance = balance + 1 if category == 'clean' else 0
    return float(balance)


def get_draw_ticket_totals(session_id: str) -> Dict[str, float]:
    """Return ticket totals, using session-local tickets for manual entries."""
    totals = calculate_ticket_balances()
    for student_id in get_manual_student_ids_for_draw(session_id):
        totals[student_id] = get_manual_session_ticket_total(session_id, student_id)
    return totals


def get_eligible_students_with_tickets(
    session_id: str
) -> List[Tuple[Student, float]]:
    """
    Get list of (student, ticket_count) for students eligible for draw.
    """
    ticket_balances = get_draw_ticket_totals(session_id)
    
    if not ticket_balances:
        return []

    eligible_student_ids = [
        student_id for student_id in get_draw_eligible_student_ids(session_id)
        if student_id in ticket_balances
    ]

    if not eligible_student_ids:
        return []
    
    # Get student records. Inactive manual participants are included here;
    # eligibility was already scoped by the qualifying record above.
    students = (
        db_session.query(Student)
        .filter(Student.id.in_(eligible_student_ids),
                Student.school_id == _resolve_school_id(session_id=session_id))
        .all()
    )
    
    result = []
    for student in students:
        tickets = ticket_balances.get(student.id, 0.0)
        if tickets > 0:
            result.append((student, tickets))
    
    return sorted(result, key=lambda x: (-x[1], x[0].preferred_name))


def perform_weighted_draw(
    session_id: str, user_id: str
) -> Tuple[Optional[Student], float, float, int]:
    """
    Perform weighted random draw based on tickets.
    Returns (winner_student, winner_tickets, probability, pool_size)
    """
    eligible = get_eligible_students_with_tickets(session_id)
    
    if not eligible:
        return None, 0.0, 0.0, 0
    
    total_tickets = sum(tickets for _, tickets in eligible)
    
    # Perform weighted random selection
    target = secure_random.random() * total_tickets
    cumulative = 0.0
    winner = None
    winner_tickets = 0.0
    
    for student, tickets in eligible:
        cumulative += tickets
        if target <= cumulative:
            winner = student
            winner_tickets = tickets
            break
    
    # Fallback to first student if something went wrong
    if winner is None and eligible:
        winner, winner_tickets = eligible[0]
    
    probability = (winner_tickets / total_tickets * 100.0) if total_tickets > 0 else 0.0
    
    return winner, winner_tickets, probability, len(eligible)


def record_draw_event(
    draw: SessionModel,
    event_type: str,
    user_id: str,
    selected_student_id: Optional[str] = None,
    tickets_at_event: Optional[float] = None,
    probability_at_event: Optional[float] = None,
    eligible_pool_size: Optional[int] = None,
    comment: Optional[str] = None,
) -> SessionDrawEvent:
    """Record a draw event in the database."""
    event = SessionDrawEvent(
        school_id=draw.school_id,
        session_id=draw.id,
        draw_number=draw.draw_number,
        event_type=event_type,
        selected_student_id=selected_student_id,
        tickets_at_event=int(tickets_at_event) if tickets_at_event is not None else None,
        # Store probability as basis points (multiply by 100) to preserve 2 decimal places
        probability_at_event=int(round(probability_at_event * 100)) if probability_at_event is not None else None,
        eligible_pool_size=eligible_pool_size,
        comment=(comment or '').strip() or None,
        created_by=user_id,
    )
    db_session.add(event)
    return event


def record_ticket_event(
    session_id: str,
    student_id: str,
    event_type: str,
    tickets_delta: float,
    ticket_balance_after: float,
    user_id: Optional[str] = None,
    session_record_id: Optional[str] = None,
    event_metadata: Optional[str] = None,
) -> SessionTicketEvent:
    """Record a ticket event in the database."""
    event = SessionTicketEvent(
        school_id=_resolve_school_id(session_id=session_id, student_id=student_id),
        session_id=session_id,
        session_record_id=session_record_id,
        student_id=student_id,
        event_type=event_type,
        tickets_delta=int(tickets_delta),
        ticket_balance_after=int(ticket_balance_after),
        occurred_by=user_id,
        event_metadata=event_metadata,
    )
    db_session.add(event)
    return event


def reset_student_tickets(
    session_id: str,
    student_id: str,
    user_id: Optional[str],
    reason: str,
) -> bool:
    """Reset a student's tickets to zero, recording the event.

    Returns True if a reset occurred, False if balance already zero.
    """
    current_tickets = get_student_ticket_balance(student_id)
    if current_tickets <= 0:
        return False

    record_ticket_event(
        session_id=session_id,
        student_id=student_id,
        event_type='reset',
        tickets_delta=-current_tickets,
        ticket_balance_after=0.0,
        user_id=user_id,
        event_metadata=reason,
    )

    update_draft_pool(student_id, 0.0, session_id=session_id)
    return True


def finalize_draw(draw: SessionModel, user_id: str, comment: Optional[str] = None) -> None:
    """Finalize a draw and reset winner's tickets."""
    if draw.finalized:
        return
    
    draw.finalized = 1
    draw.finalized_by = user_id
    draw.finalized_at = _now_utc()
    draw.updated_at = _now_utc()
    
    # Record finalize event
    record_draw_event(
        draw=draw,
        event_type='finalize',
        user_id=user_id,
        selected_student_id=draw.winner_student_id,
        comment=comment,
    )
    
    # Reset winner's tickets to 0
    if draw.winner_student_id:
        reset_student_tickets(
            session_id=draw.id,
            student_id=draw.winner_student_id,
            user_id=user_id,
            reason='Winner finalized - tickets reset',
        )
    
    db_session.commit()


def reset_draw(draw: SessionModel, user_id: str, comment: Optional[str] = None) -> None:
    """Reset a draw, clearing the winner."""
    # Record restore event before resetting
    record_draw_event(
        draw=draw,
        event_type='restore',
        user_id=user_id,
        selected_student_id=draw.winner_student_id,
        comment=comment,
    )
    
    draw.winner_student_id = None
    draw.method = None
    draw.finalized = 0
    draw.finalized_by = None
    draw.finalized_at = None
    draw.tickets_at_selection = None
    draw.probability_at_selection = None
    draw.eligible_pool_size = None
    draw.override_applied = 0
    draw.updated_at = _now_utc()
    
    db_session.commit()


def get_draw_history(session_id: str) -> List[Dict]:
    """Get all draw events for a session."""
    events = (
        db_session.query(SessionDrawEvent)
        .filter_by(session_id=session_id)
        .order_by(SessionDrawEvent.created_at)
        .all()
    )

    user_labels = user_labels_for_school(_resolve_school_id(session_id=session_id))
    result = []
    for event in events:
        student = None
        if event.selected_student_id:
            student = db_session.query(Student).filter_by(id=event.selected_student_id).first()
        record = db_session.get(SessionRecord, event.selected_record_id) if event.selected_record_id else None
        is_faculty = event.draw_target == 'faculty' or bool(record and record.category == 'faculty')
        faculty_name = event.faculty_name
        teacher_id = event.selected_teacher_id or (record.teacher_id if record else None)
        teacher = db_session.get(Teacher, teacher_id) if teacher_id else None
        if teacher and teacher.school_id == event.school_id:
            faculty_name = teacher_names(teacher)[2]
        if not faculty_name and is_faculty and record:
            faculty_name = f"{record.preferred_name or ''} {record.last_name or ''}".strip()

        # Convert probability from basis points (stored as * 100) back to percentage
        probability = (
            event.probability_at_event / 100.0
            if event.probability_at_event is not None
            else None
        )

        result.append({
            'event_type': f'faculty_{event.event_type}' if is_faculty else event.event_type,
            'timestamp': event.created_at.isoformat() if event.created_at else None,
            'created_by': readable_user_label(event.created_by, labels=user_labels),
            'student_name': f"{student.preferred_name} {student.last_name}" if student else None,
            'faculty_name': faculty_name if is_faculty else None,
            'recorded_name': event.faculty_name if is_faculty else None,
            'student_id': event.selected_student_id,
            'tickets': event.tickets_at_event,
            'probability': probability,
            'pool_size': event.eligible_pool_size,
            'comment': event.comment,
        })

    return result


def get_student_ticket_balance(student_id: str) -> float:
    """Return the current ticket balance for a student across sessions."""
    pool_entry = (
        db_session.query(DraftPool)
        .filter_by(student_id=student_id)
        .first()
    )
    return float(pool_entry.ticket_number) if pool_entry else 0.0


def update_draft_pool(student_id: str, new_balance: float, session_id: Optional[str] = None) -> None:
    """Update or create the draft_pool entry for a student."""
    school_id = _resolve_school_id(session_id=session_id, student_id=student_id)
    pool_entry = (
        db_session.query(DraftPool)
        .filter_by(school_id=school_id, student_id=student_id)
        .first()
    )
    
    if pool_entry:
        pool_entry.session_id = session_id or pool_entry.session_id
        pool_entry.ticket_number = int(new_balance)
    else:
        pool_entry = DraftPool(
            school_id=school_id,
            session_id=session_id,
            student_id=student_id,
            ticket_number=int(new_balance),
        )
        db_session.add(pool_entry)


def update_tickets_for_record(
    session_id: str,
    student_id: str,
    category: str,
    session_record_id: str,
    user_id: str,
) -> None:
    """
    Update tickets when a record is created.
    - clean: +1 ticket
    - red: reset to 0 tickets
    """
    current_balance = get_student_ticket_balance(student_id)
    
    if category == 'clean':
        # Award 1 ticket for clean plate
        new_balance = current_balance + 1.0
        tickets_delta = 1.0
        event_type = 'earn'
        
        # Record ticket event
        record_ticket_event(
            session_id=session_id,
            student_id=student_id,
            event_type=event_type,
            tickets_delta=tickets_delta,
            ticket_balance_after=new_balance,
            user_id=user_id,
            session_record_id=session_record_id,
            event_metadata=f'Earned ticket for clean plate',
        )
        
        # Update draft pool
        update_draft_pool(student_id, new_balance, session_id=session_id)
        
    elif category == 'red':
        # Reset tickets for red plate
        if current_balance > 0:
            new_balance = 0.0
            tickets_delta = -current_balance
            event_type = 'reset'
            
            # Record ticket event
            record_ticket_event(
                session_id=session_id,
                student_id=student_id,
                event_type=event_type,
                tickets_delta=tickets_delta,
                ticket_balance_after=new_balance,
                user_id=user_id,
                session_record_id=session_record_id,
                event_metadata=f'Tickets reset due to red plate',
            )
            
            # Update draft pool
            update_draft_pool(student_id, new_balance)


__all__ = [
    'calculate_ticket_balances',
    'finalize_draw',
    'get_clean_student_ids_for_session',
    'get_draw_eligible_student_ids',
    'get_draw_history',
    'get_draw_ticket_totals',
    'get_eligible_students_with_tickets',
    'get_manual_session_ticket_total',
    'get_manual_student_ids_for_draw',
    'get_or_create_session_draw',
    'get_session_ids_for_draw',
    'get_student_ticket_balance',
    'is_manual_draw_participant',
    'perform_weighted_draw',
    'record_draw_event',
    'record_ticket_event',
    'reset_draw',
    'reset_student_tickets',
    'update_draft_pool',
    'update_tickets_for_record',
]
