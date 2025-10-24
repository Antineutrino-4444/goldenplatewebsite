"""Database operations for draw system."""
import random
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import func

from .db import (
    DraftPool,
    Session,
    SessionDraw,
    SessionDrawEvent,
    SessionRecord,
    SessionTicketEvent,
    Student,
    _now_utc,
    db_session,
)

secure_random = random.SystemRandom()


def get_or_create_session_draw(session_id: str) -> SessionDraw:
    """Get existing draw or create new one for session."""
    draw = db_session.query(SessionDraw).filter_by(session_id=session_id).first()
    if not draw:
        # Get the next draw number for this session
        draw_number = 1
        draw = SessionDraw(
            session_id=session_id,
            draw_number=draw_number,
        )
        db_session.add(draw)
        db_session.commit()
    return draw


def calculate_ticket_balances(session_id: str) -> Dict[str, float]:
    """
    Calculate current cumulative ticket balances for all students.
    Gets the most recent ticket balance for each student across all sessions.
    Returns dict mapping student_id to ticket count.
    """
    # Get all unique students
    all_students = db_session.query(DraftPool.student_id).distinct().all()
    
    ticket_balances = {}
    for (student_id,) in all_students:
        if student_id:
            # Get the most recent ticket balance for this student
            balance = get_student_ticket_balance(session_id, student_id)
            if balance > 0:
                ticket_balances[student_id] = balance
    
    return ticket_balances


def get_clean_student_ids_for_session(session_id: str) -> Set[str]:
    """Return student IDs with a clean-plate record in the session."""
    rows = (
        db_session.query(SessionRecord.student_id)
        .filter(
            SessionRecord.session_id == session_id,
            SessionRecord.category == 'clean',
            SessionRecord.student_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {student_id for (student_id,) in rows if student_id}


def get_eligible_students_with_tickets(
    session_id: str
) -> List[Tuple[Student, float]]:
    """
    Get list of (student, ticket_count) for students eligible for draw.
    """
    ticket_balances = calculate_ticket_balances(session_id)
    
    if not ticket_balances:
        return []

    clean_student_ids = get_clean_student_ids_for_session(session_id)
    if not clean_student_ids:
        return []

    eligible_student_ids = [
        student_id for student_id in ticket_balances.keys() if student_id in clean_student_ids
    ]

    if not eligible_student_ids:
        return []
    
    # Get student records
    students = (
        db_session.query(Student)
        .filter(Student.id.in_(eligible_student_ids))
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
    draw: SessionDraw,
    event_type: str,
    user_id: str,
    selected_student_id: Optional[str] = None,
    tickets_at_event: Optional[float] = None,
    probability_at_event: Optional[float] = None,
    eligible_pool_size: Optional[int] = None,
) -> SessionDrawEvent:
    """Record a draw event in the database."""
    event = SessionDrawEvent(
        session_draw_id=draw.id,
        session_id=draw.session_id,
        event_type=event_type,
        selected_student_id=selected_student_id,
        tickets_at_event=int(tickets_at_event) if tickets_at_event is not None else None,
        probability_at_event=int(probability_at_event) if probability_at_event is not None else None,
        eligible_pool_size=eligible_pool_size,
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
    current_tickets = get_student_ticket_balance(session_id, student_id)
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

    update_draft_pool(session_id, student_id, 0.0)
    return True


def finalize_draw(draw: SessionDraw, user_id: str) -> None:
    """Finalize a draw and reset winner's tickets."""
    if draw.finalized:
        return
    
    draw.finalized = 1
    draw.finalized_by = user_id
    draw.finalized_at = _now_utc()
    
    # Record finalize event
    record_draw_event(
        draw=draw,
        event_type='finalize',
        user_id=user_id,
        selected_student_id=draw.winner_student_id,
    )
    
    # Reset winner's tickets to 0
    if draw.winner_student_id:
        reset_student_tickets(
            session_id=draw.session_id,
            student_id=draw.winner_student_id,
            user_id=user_id,
            reason='Winner finalized - tickets reset',
        )
    
    db_session.commit()


def reset_draw(draw: SessionDraw, user_id: str) -> None:
    """Reset a draw, clearing the winner."""
    # Record restore event before resetting
    record_draw_event(
        draw=draw,
        event_type='restore',
        user_id=user_id,
        selected_student_id=draw.winner_student_id,
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
    draw = db_session.query(SessionDraw).filter_by(session_id=session_id).first()
    if not draw:
        return []
    
    events = (
        db_session.query(SessionDrawEvent)
        .filter_by(session_draw_id=draw.id)
        .order_by(SessionDrawEvent.created_at)
        .all()
    )
    
    result = []
    for event in events:
        student = None
        if event.selected_student_id:
            student = db_session.query(Student).filter_by(id=event.selected_student_id).first()
        
        result.append({
            'event_type': event.event_type,
            'timestamp': event.created_at.isoformat() if event.created_at else None,
            'created_by': event.created_by,
            'student_name': f"{student.preferred_name} {student.last_name}" if student else None,
            'student_id': event.selected_student_id,
            'tickets': event.tickets_at_event,
            'probability': event.probability_at_event,
            'pool_size': event.eligible_pool_size,
        })
    
    return result


def get_student_ticket_balance(session_id: str, student_id: str) -> float:
    """
    Get current cumulative ticket balance for a student.
    Looks across all sessions to find the most recent ticket balance.
    """
    # Get the most recent draft_pool entry for this student across all sessions
    pool_entry = (
        db_session.query(DraftPool)
        .join(Session, DraftPool.session_id == Session.id)
        .filter(DraftPool.student_id == student_id)
        .order_by(Session.created_at.desc())
        .first()
    )
    return float(pool_entry.ticket_number) if pool_entry else 0.0


def update_draft_pool(session_id: str, student_id: str, new_balance: float) -> None:
    """Update or create draft_pool entry for a student."""
    pool_entry = (
        db_session.query(DraftPool)
        .filter_by(session_id=session_id, student_id=student_id)
        .first()
    )
    
    if pool_entry:
        pool_entry.ticket_number = int(new_balance)
    else:
        pool_entry = DraftPool(
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
    current_balance = get_student_ticket_balance(session_id, student_id)
    
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
        update_draft_pool(session_id, student_id, new_balance)
        
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
            update_draft_pool(session_id, student_id, new_balance)


__all__ = [
    'calculate_ticket_balances',
    'finalize_draw',
    'get_clean_student_ids_for_session',
    'get_draw_history',
    'get_eligible_students_with_tickets',
    'get_or_create_session_draw',
    'get_student_ticket_balance',
    'perform_weighted_draw',
    'record_draw_event',
    'record_ticket_event',
    'reset_draw',
    'reset_student_tickets',
    'update_draft_pool',
    'update_tickets_for_record',
]
