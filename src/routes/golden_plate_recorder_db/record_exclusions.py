"""Session-scoped, reversible exclusions with consistent totals and draw state."""

import json
from datetime import timezone

from sqlalchemy import func

from .db import (RecordExclusionEvent, RosterSnapshot, School, Session, SessionRecord,
                 SessionTicketEvent, Student, _now_utc, db_session)
from .draw_db import (get_clean_student_ids_for_session, get_student_ticket_balance,
                      record_draw_event, update_draft_pool)
from .utils import normalize_house, plate_count_label


def review_records(meal, roster_scope='auto'):
    snapshot = db_session.query(RosterSnapshot).filter_by(
        id=meal.roster_snapshot_id, school_id=meal.school_id,
    ).first() if meal.roster_snapshot_id else None
    if snapshot and roster_scope != 'current':
        members = json.loads(snapshot.data)['members']
        source = 'saved'
        filename = snapshot.filename
    else:
        # Preview current membership without assigning a roster to the session
        # or creating a snapshot during a read-only review.
        students = db_session.query(Student).filter_by(school_id=meal.school_id, is_active=1).all()
        members = {student.id: student.house for student in students}
        source = 'current'
        filename = db_session.get(School, meal.school_id).roster_filename
    roster_label = 'this session’s saved roster' if source == 'saved' else 'the current roster'
    rows = db_session.query(SessionRecord).filter_by(
        school_id=meal.school_id, session_id=meal.id,
    ).order_by(SessionRecord.recorded_at, SessionRecord.id).all()
    result = []
    for row in rows:
        named = bool(row.student_id or (row.preferred_name or '').strip() or (row.last_name or '').strip())
        issue = None
        if members and row.category != 'faculty' and named:
            if row.student_id and row.student_id not in members:
                issue = f'Student is not in {roster_label}.'
            elif row.student_id and normalize_house(row.house) and normalize_house(members[row.student_id]):
                if normalize_house(row.house) != normalize_house(members[row.student_id]):
                    issue = f'Recorded house conflicts with {roster_label}.'
        name = f'{row.preferred_name or ""} {row.last_name or ""}'.strip()
        result.append({'record_id': row.id, 'name': name or plate_count_label(row.category),
                       'category': row.category, 'house': normalize_house(row.house),
                       'is_count_only': not named, 'is_excluded': bool(row.is_excluded),
                       'issue': issue, 'exclusion_reason': row.exclusion_reason,
                       'excluded_at': row.excluded_at.isoformat() if row.excluded_at else None})
    return {'records': result, 'roster_review': {'source': source, 'filename': filename,
                                               'available': bool(members), 'has_saved_roster': bool(snapshot)}}


def _time(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _recalculate_tickets(student_id, school_id):
    """Replay plate outcomes and independent ticket actions; preserve audit events.

    Reset deltas are historical snapshots, so subtracting a removed clean/red
    event from today's balance is incorrect. Replay resets as resets instead.
    """
    events = db_session.query(SessionTicketEvent).filter_by(
        student_id=student_id, school_id=school_id,
    ).order_by(SessionTicketEvent.occurred_at, SessionTicketEvent.id).all()
    if not events:
        return False
    previous = get_student_ticket_balance(student_id)
    first = events[0]
    balance = max(0, (first.ticket_balance_after or 0) - first.tickets_delta)
    records = db_session.query(SessionRecord).filter_by(
        student_id=student_id, school_id=school_id,
    ).filter(SessionRecord.category.in_(['clean', 'red'])).all()
    linked_events = {event.session_record_id: event for event in events if event.session_record_id}
    operations = []
    for row in records:
        if row.is_excluded:
            continue
        event = linked_events.get(row.id)
        # Clean records without a ticket event may predate the ticket system.
        # Red plates must still reset even if they originally encountered zero.
        if event or row.category == 'red':
            operations.append((_time(event.occurred_at if event else row.recorded_at),
                               0, row.id, 'reset' if row.category == 'red' else 'earn', 1))
    for event in events:
        if not event.session_record_id:
            operations.append((_time(event.occurred_at), 1, event.id, event.event_type, event.tickets_delta))
    for _, _, _, action, delta in sorted(operations):
        balance = 0 if action == 'reset' else max(0, balance + delta)
    update_draft_pool(student_id, balance)
    return balance != previous


def set_record_excluded(meal, row, excluded, actor_id, reason):
    if bool(row.is_excluded) == excluded:
        return []
    row.is_excluded = int(excluded)
    row.excluded_at = _now_utc() if excluded else None
    row.excluded_by = actor_id if excluded else None
    row.exclusion_reason = reason if excluded else None
    db_session.add(RecordExclusionEvent(school_id=meal.school_id, session_id=meal.id,
                                      record_id=row.id, is_excluded=int(excluded),
                                      changed_by=actor_id, reason=reason))
    db_session.flush()
    counts = dict(db_session.query(SessionRecord.category, func.count(SessionRecord.id)).filter_by(
        school_id=meal.school_id, session_id=meal.id, is_excluded=0,
    ).group_by(SessionRecord.category).all())
    for category, field in [('clean', 'clean_number'), ('dirty', 'dirty_number'),
                            ('red', 'red_number'), ('faculty', 'faculty_number')]:
        setattr(meal, field, counts.get(category, 0))
    meal.total_records = sum(counts.values())
    meal.total_clean = meal.clean_number + meal.faculty_number
    meal.total_dirty = meal.dirty_number + meal.red_number
    meal.updated_at = _now_utc()
    tickets_changed = bool(row.student_id and row.category in ('clean', 'red') and
                           _recalculate_tickets(row.student_id, meal.school_id))
    reset_sessions = []
    target_id = meal.main_session_id or meal.id
    draws = db_session.query(Session).filter_by(school_id=meal.school_id).filter(
        Session.winner_student_id.isnot(None),
    ).all()
    for draw in draws:
        affected = draw.id == target_id and row.category in ('clean', 'red')
        if tickets_changed and not draw.finalized:
            affected = affected or row.student_id in get_clean_student_ids_for_session(draw.id)
        if not affected:
            continue
        record_draw_event(draw, 'restore', actor_id, selected_student_id=draw.winner_student_id,
                          comment='Draw cleared after a session record was excluded or restored.')
        for field in ('winner_student_id', 'method', 'finalized_by', 'finalized_at',
                      'tickets_at_selection', 'probability_at_selection', 'eligible_pool_size'):
            setattr(draw, field, None)
        draw.finalized = draw.override_applied = 0
        draw.updated_at = _now_utc()
        reset_sessions.append(draw.id)
    if row.category == 'faculty' and meal.faculty_pick_display_name:
        event = record_draw_event(meal, 'restore', actor_id,
                                  comment='Faculty draw cleared after a record was excluded or restored.')
        event.draw_target = 'faculty'
        event.faculty_name = meal.faculty_pick_display_name
        event.selected_record_id = meal.faculty_pick_record_id
        for field in ('faculty_pick_preferred_name', 'faculty_pick_last_name', 'faculty_pick_display_name',
                      'faculty_pick_recorded_at', 'faculty_pick_recorded_by', 'faculty_pick_record_id',
                      'faculty_finalized_at', 'faculty_finalized_by'):
            setattr(meal, field, None)
        meal.faculty_finalized = 0
    return reset_sessions
