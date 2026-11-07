"""Ticket standings and selection details for the faculty draw."""

from collections import defaultdict

from sqlalchemy import func, or_

from .db import Session, SessionDrawEvent, SessionRecord, Teacher, _now_utc, db_session
from .draw_db import get_session_ids_for_draw, record_draw_event
from .person_identity import teacher_names
from .utils import normalize_name


def faculty_record_names(record, teacher=None):
    if teacher:
        return teacher_names(teacher)
    preferred = normalize_name(record.preferred_name)
    last = normalize_name(record.last_name)
    if not (preferred or last) and record.dedupe_key.startswith('faculty_'):
        preferred, _, last = record.dedupe_key.removeprefix('faculty_').replace('_', ' ').rpartition(' ')
        preferred, last = (preferred.title(), last.title()) if preferred else (last.title(), '')
    return preferred, last, f'{preferred} {last}'.strip()


def _faculty_clean_plates(school_id):
    return (
        db_session.query(SessionRecord)
        .join(Session, SessionRecord.session_id == Session.id)
        .filter(
            SessionRecord.school_id == school_id,
            SessionRecord.category == 'faculty',
            SessionRecord.is_excluded == 0,
            Session.school_id == school_id,
            Session.status != 'discarded',
            ~SessionRecord.dedupe_key.startswith('count:'),
        )
    )


def faculty_roster_ticket_totals(school_id, *, teacher_ids=None, active_only=True, since=None):
    """Return cumulative roster balances, optionally including past members."""
    resets = (
        db_session.query(
            SessionDrawEvent.selected_teacher_id.label('teacher_id'),
            func.max(SessionDrawEvent.created_at).label('last_reset'),
        )
        .filter_by(school_id=school_id, draw_target='faculty', event_type='finalize')
        .filter(or_(SessionDrawEvent.faculty_ticket_scope == 'roster',
                    SessionDrawEvent.faculty_ticket_scope.is_(None)))
        .group_by(SessionDrawEvent.selected_teacher_id)
        .subquery()
    )
    totals = (
        _faculty_clean_plates(school_id).with_entities(SessionRecord.teacher_id, func.count(SessionRecord.id))
        .join(Teacher, (Teacher.id == SessionRecord.teacher_id) & (Teacher.school_id == school_id))
        .outerjoin(resets, resets.c.teacher_id == SessionRecord.teacher_id)
        .filter(
            or_(
                SessionRecord.faculty_roster_entry == 1,
                SessionRecord.faculty_roster_entry.is_(None) &
                or_(Teacher.is_active == 1, Teacher.faculty_identifier.isnot(None)),
            ),
            or_(resets.c.last_reset.is_(None), SessionRecord.recorded_at > resets.c.last_reset),
            or_(Teacher.faculty_tickets_reset_at.is_(None),
                SessionRecord.recorded_at > Teacher.faculty_tickets_reset_at),
        )
        .group_by(SessionRecord.teacher_id)
    )
    if active_only:
        totals = totals.filter(Teacher.is_active == 1)
    if teacher_ids is not None:
        totals = totals.filter(SessionRecord.teacher_id.in_(teacher_ids))
    if since is not None:
        totals = totals.filter(SessionRecord.recorded_at >= since)
    return dict(totals.all())


def eligible_faculty_with_tickets(meal, *, include_zero=False):
    """Require a clean plate in scope, using cumulative or session-local tickets."""
    if meal.status == 'discarded':
        return []

    session_ids = get_session_ids_for_draw(meal.id)
    qualifying = (
        _faculty_clean_plates(meal.school_id).add_entity(Teacher)
        .outerjoin(Teacher, (Teacher.id == SessionRecord.teacher_id) & (Teacher.school_id == meal.school_id))
        .filter(SessionRecord.session_id.in_(session_ids))
        .order_by(SessionRecord.recorded_at.desc(), SessionRecord.id)
        .all()
    )
    candidates = defaultdict(list)
    manual_keys = set()
    for record, teacher in qualifying:
        name = faculty_record_names(record, teacher)[2]
        if not name or (record.teacher_id and not teacher):
            continue
        key = ('teacher', teacher.id) if teacher else ('legacy', name.casefold())
        # Older faculty records used the manual flag for roster entries too.
        # Active membership or a roster ID is evidence of a legacy roster entry.
        roster_entry = record.faculty_roster_entry
        if roster_entry is None:
            roster_entry = teacher and (teacher.is_active or teacher.faculty_identifier)
        if roster_entry and not teacher.is_active:
            continue
        if not roster_entry:
            manual_keys.add(key)
        candidates[key].append((record, teacher))

    if not candidates:
        return []

    finalizations = db_session.query(SessionDrawEvent).filter_by(
        school_id=meal.school_id, draw_target='faculty', event_type='finalize',
    )
    roster_ids = [key[1] for key in candidates if key not in manual_keys]
    balances = faculty_roster_ticket_totals(meal.school_id, teacher_ids=roster_ids) if roster_ids else {}
    manual_resets = {}
    if manual_keys:
        local_finalizations = finalizations.filter(
            SessionDrawEvent.session_id == meal.id,
            or_(SessionDrawEvent.faculty_ticket_scope == 'session', SessionDrawEvent.faculty_ticket_scope.is_(None)),
        ).order_by(SessionDrawEvent.created_at)
        for event in local_finalizations:
            key = (
                ('teacher', event.selected_teacher_id) if event.selected_teacher_id
                else ('legacy', normalize_name(event.faculty_name).casefold())
            )
            manual_resets[key] = event.created_at

    eligible = []
    for key, plates in candidates.items():
        scope = 'session' if key in manual_keys else 'roster'
        if scope == 'session':
            reset = manual_resets.get(key)
            tickets = sum(1 for record, _ in plates if reset is None or record.recorded_at > reset)
        else:
            tickets = balances.get(key[1], 0)
        if tickets or include_zero:
            record, teacher = plates[0]
            eligible.append(((record, teacher, scope), tickets))
    return sorted(eligible, key=lambda entry: (
        -entry[1], faculty_record_names(*entry[0][:2])[2].casefold(), entry[0][0].id,
    ))


def faculty_ticket_summary(meal, *, can_override=False):
    candidates = eligible_faculty_with_tickets(meal, include_zero=can_override)
    eligible = [(candidate, tickets) for candidate, tickets in candidates if tickets > 0]
    total_tickets = sum(tickets for _, tickets in eligible)
    standings = [{
        'category': 'faculty',
        'display_name': faculty_record_names(record, teacher)[2],
        'teacher_id': record.teacher_id,
        'tickets': tickets,
        'probability': tickets / total_tickets * 100,
    } for (record, teacher, _), tickets in eligible]
    summary = {'total_tickets': total_tickets, 'eligible_count': len(standings), 'candidates': standings}
    if can_override:
        summary['override_candidates'] = [{
            'record_id': record.id,
            'teacher_id': record.teacher_id,
            'display_name': faculty_record_names(record, teacher)[2],
            'faculty_identifier': teacher.faculty_identifier if teacher else None,
        } for (record, teacher, _), _tickets in candidates]
    return summary


def clear_faculty_pick(draw, actor_id, comment):
    event = record_draw_event(draw, 'restore', actor_id, comment=comment)
    event.draw_target = 'faculty'
    event.faculty_name = draw.faculty_pick_display_name
    event.selected_record_id = draw.faculty_pick_record_id
    event.selected_teacher_id = draw.faculty_pick_teacher_id
    for field in ('faculty_pick_preferred_name', 'faculty_pick_last_name', 'faculty_pick_display_name',
                  'faculty_pick_recorded_at', 'faculty_pick_recorded_by', 'faculty_pick_record_id',
                  'faculty_pick_teacher_id', 'faculty_finalized_at', 'faculty_finalized_by'):
        setattr(draw, field, None)
    draw.faculty_finalized = 0
    draw.updated_at = _now_utc()
