"""Replay clean-plate rewards, balances, and next gains from saved school history.

Session creation order defines consecutive meals, including each merged extra.
The newest unfinished meal is still an opportunity to record a clean plate;
an absence breaks the combo when that meal is over or a later meal exists.
Draw rounding is sampled once and stored on the finalization event.
"""

import hashlib
import secrets
from collections import defaultdict
from dataclasses import dataclass
from datetime import timezone

from sqlalchemy import update

from .db import (DraftPool, School, Session, SessionDrawEvent, SessionRecord,
                 SessionTicketEvent, Student, Teacher, db_session)


@dataclass
class TicketState:
    balance: int = 0
    earned: int = 0
    next_gain: int = 1
    last_session: int = -1
    last_gain: int = 1


def _time(value):
    if value is None:
        return 0
    return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()


def halve_combo(combo, round_up):
    return max(1, combo // 2 + (int(bool(round_up)) if combo % 2 else 0))


def _coin(event):
    # Read-only fallback for an imported legacy event pending initialization.
    # Its random UUID makes this stable across reloads, workers, and replays.
    if event.combo_round_up is not None:
        return event.combo_round_up
    return hashlib.sha256(event.id.encode()).digest()[0] & 1


def faculty_key(record, teacher, sessions):
    roster = record.faculty_roster_entry
    if roster is None:
        roster = bool(teacher and (teacher.is_active or teacher.faculty_identifier))
    identity = teacher.id if teacher else ' '.join(
        f'{record.preferred_name or ""} {record.last_name or ""}'.casefold().split())
    meal = sessions[record.session_id]
    return ('faculty', identity, 'roster' if roster else meal.main_session_id or meal.id)


def replay_school_tickets(school_id):
    """Return participant states and per-record rewards without committing writes."""
    meals = db_session.query(Session).filter_by(school_id=school_id).filter(
        Session.status != 'discarded',
    ).order_by(Session.created_at, Session.id).all()
    sessions = {meal.id: meal for meal in meals}
    positions = {meal.id: index for index, meal in enumerate(meals)}
    next_session_times = {meal.id: _time(meals[index + 1].created_at)
                          for index, meal in enumerate(meals[:-1])}
    students = {row.id: row for row in db_session.query(Student).filter_by(school_id=school_id)}
    teachers = {row.id: row for row in db_session.query(Teacher).filter_by(school_id=school_id)}
    records = db_session.query(SessionRecord).filter(
        SessionRecord.school_id == school_id, SessionRecord.session_id.in_(sessions),
        SessionRecord.is_excluded == 0, ~SessionRecord.dedupe_key.startswith('count:'),
    ).all()
    events = db_session.query(SessionTicketEvent).filter(
        SessionTicketEvent.school_id == school_id, SessionTicketEvent.student_id.in_(students),
    ).order_by(SessionTicketEvent.occurred_at, SessionTicketEvent.id).all()
    all_draws = db_session.query(SessionDrawEvent).filter(
        SessionDrawEvent.school_id == school_id,
        SessionDrawEvent.event_type == 'finalize',
    ).all()
    draws = [event for event in all_draws if event.session_id in sessions]
    states = defaultdict(TicketState)
    operations = []
    by_student = defaultdict(list)
    for row in records:
        if row.category == 'faculty':
            teacher = teachers.get(row.teacher_id)
            if row.teacher_id and not teacher:
                continue
            key = faculty_key(row, teacher, sessions)
            if not key[1]:
                continue
        else:
            if row.student_id not in students:
                continue
            scope = sessions[row.session_id].main_session_id or row.session_id
            key = ('student', row.student_id, scope if row.is_manual_entry else 'roster')
            if not row.is_manual_entry:
                by_student[row.student_id].append(row)
        # Keep actual ordering within a session (including resets before later
        # scans). A backfilled earlier session still precedes the next session.
        occurred_at = max(_time(sessions[row.session_id].created_at), _time(row.recorded_at))
        occurred_at = min(occurred_at, next_session_times.get(row.session_id, float('inf')))
        operations.append((occurred_at, 0, (positions[row.session_id], _time(row.recorded_at)),
                           row.id, 'plate', key, row))

    # Preserve ticket balances whose original earning records no longer exist.
    # Freeze this baseline before the first conversion so future replays cannot
    # mistake newly increased combo rewards for additional legacy tickets.
    pool = {row.student_id: row for row in db_session.query(DraftPool).filter(DraftPool.student_id.in_(students))}
    first_events = {}
    for event in events:
        first_events.setdefault(event.student_id, event)
    baselines = {}
    for key, student in students.items():
        baseline = student.ticket_legacy_balance
        if baseline is None:
            first = first_events.get(key)
            opening = max(0, (first.ticket_balance_after or 0) - first.tickets_delta) if first else (
                pool[key].ticket_number if key in pool else 0)
            old_balance = 0
            cutoff = _time(first.occurred_at) if first else float('inf')
            prefix = [row for row in by_student[key] if _time(row.recorded_at) < cutoff
                      and (not first or row.id != first.session_record_id)]
            old_ops = [(_time(row.recorded_at), 0, row.id, row.category) for row in prefix]
            old_ops.extend((_time(event.created_at), 1, event.id, 'red') for event in draws
                           if event.draw_target != 'faculty' and event.selected_student_id == key
                           and _time(event.created_at) < cutoff)
            for _, _, _, action in sorted(old_ops):
                old_balance = 0 if action == 'red' else old_balance + int(action == 'clean')
            baseline = max(0, opening - old_balance)
        baselines[key] = baseline
        states['student', key, 'roster'] = TicketState(balance=baseline, earned=baseline)

    for event in events:
        if event.session_id in sessions and not event.session_record_id:
            operations.append((_time(event.occurred_at), 2, 0, event.id, 'adjust',
                               ('student', event.student_id, 'roster'), event))

    recorded_wins = set()
    for event in draws:
        if event.draw_target == 'faculty':
            record = db_session.get(SessionRecord, event.selected_record_id) if event.selected_record_id else None
            teacher_id = event.selected_teacher_id or (record.teacher_id if record else None)
            if teacher_id not in teachers and not record:
                continue
            key = faculty_key(record, teachers.get(teacher_id), sessions) if record and record.session_id in sessions else (
                'faculty', teacher_id, event.session_id if event.faculty_ticket_scope == 'session' else 'roster')
        else:
            if event.selected_student_id not in students:
                continue
            manual = any(row.student_id == event.selected_student_id and row.is_manual_entry
                         and (sessions[row.session_id].main_session_id or row.session_id) == event.session_id
                         for row in records)
            key = ('student', event.selected_student_id, event.session_id if manual else 'roster')
        operations.append((_time(event.created_at), 1, 0, event.id, 'win', key, event))
        recorded_wins.add((event.session_id, key[0], key[1]))

    # Older deleted faculty draws retained this durable reset timestamp. Keep
    # it effective without reapplying timestamps belonging to discarded draws.
    for teacher in teachers.values():
        at = teacher.faculty_tickets_reset_at
        if at and not any(event.selected_teacher_id == teacher.id and _time(event.created_at) == _time(at)
                          for event in all_draws):
            coin = teacher.faculty_combo_round_up
            if coin is None:
                coin = hashlib.sha256(f'{teacher.id}:{at.isoformat()}'.encode()).digest()[0] & 1
            operations.append((_time(at), 1, 0, teacher.id, 'legacy_win',
                               ('faculty', teacher.id, 'roster'), coin))

    # Older finalized winners may predate draw-event logging. Initialization
    # creates their durable event; this also makes direct legacy imports safe.
    for meal in meals:
        for target, person, finalized, at in (
            ('student', meal.winner_student_id, meal.finalized, meal.finalized_at),
            ('faculty', meal.faculty_pick_teacher_id, meal.faculty_finalized, meal.faculty_finalized_at),
        ):
            if finalized and person and (meal.id, target, person) not in recorded_wins:
                key = (target, person, 'roster')
                coin = hashlib.sha256(f'{meal.id}:{target}'.encode()).digest()[0] & 1
                operations.append((_time(at or meal.created_at), 1, 0, meal.id + target, 'legacy_win', key, coin))

    awards, snapshots = {}, {}
    for _, _, _, _, action, key, item in sorted(operations, key=lambda op: op[:4]):
        state = states[key]
        if action in ('win', 'legacy_win'):
            state.balance = 0
            state.next_gain = halve_combo(state.next_gain, _coin(item) if action == 'win' else item)
        elif action == 'adjust':
            state.balance = 0 if item.event_type == 'reset' else max(0, state.balance + item.tickets_delta)
            if item.event_type in ('earn', 'manual_adjust'):
                state.earned += max(0, item.tickets_delta)
        else:
            index = positions[item.session_id]
            # Manual participants start afresh in each draw scope, but extras
            # still advance the combo as separate sessions inside that scope.
            preceding = index - 1
            if key[2] != 'roster':
                scope_indices = [positions[meal.id] for meal in meals if (meal.main_session_id or meal.id) == key[2]]
                preceding = max((position for position in scope_indices if position < index), default=-1)
            if state.last_session != index and state.last_session != preceding:
                state.next_gain = 1
            previous = state.balance
            if item.category in ('clean', 'faculty'):
                gain = state.last_gain if state.last_session == index else state.next_gain
                state.balance += gain
                state.earned += gain
                if state.last_session != index:
                    state.next_gain = gain + 1
                state.last_gain = gain
                awards[item.id] = gain
            else:
                state.next_gain = 1
                if item.category == 'red':
                    state.balance = 0
            state.last_session = index
            snapshots[item.id] = (state.balance - previous, state.balance)

    # Display the gain for the next still-available session, never prematurely
    # resetting people who have not been scanned in the current open session.
    for key, state in states.items():
        scope = [meal for meal in meals if key[2] == 'roster' or (meal.main_session_id or meal.id) == key[2]]
        if not scope:
            continue
        latest = scope[-1]
        closed = latest.status == 'archived' or (latest.faculty_finalized if key[0] == 'faculty' else latest.finalized)
        completed = positions[latest.id] if closed else (positions[scope[-2].id] if len(scope) > 1 else -1)
        if state.last_session < completed:
            state.next_gain = 1
    return states, awards, snapshots, baselines


def recalculate_school_tickets(school_id):
    """Synchronize the stored student pool and earn ledger inside the caller's transaction."""
    db_session.flush()
    if db_session.bind.dialect.name == 'sqlite':
        # Serialize concurrent startup/recording replays before reading pools.
        db_session.execute(update(School).where(School.id == school_id).values(id=School.id))
    else:
        db_session.query(School.id).filter_by(id=school_id).with_for_update().one()
    states, _, snapshots, baselines = replay_school_tickets(school_id)
    students = db_session.query(Student).filter_by(school_id=school_id).all()
    pool = {row.student_id: row for row in db_session.query(DraftPool).filter(
        DraftPool.student_id.in_([student.id for student in students]),
    )}
    for student in students:
        if student.ticket_legacy_balance is None:
            student.ticket_legacy_balance = baselines[student.id]
        balance = states['student', student.id, 'roster'].balance
        entry = pool.get(student.id)
        if entry:
            entry.school_id = school_id
            entry.ticket_number = balance
        elif balance:
            db_session.add(DraftPool(school_id=school_id, student_id=student.id, ticket_number=balance))
    for event in db_session.query(SessionTicketEvent).filter_by(school_id=school_id):
        if event.session_record_id in snapshots:
            event.tickets_delta, event.ticket_balance_after = snapshots[event.session_record_id]
        elif event.session_record_id and event.event_type == 'earn':
            event.tickets_delta = 0
    return states


def initialize_ticket_combos():
    """Upgrade existing records automatically, including on WSGI startup."""
    try:
        # Give pre-ledger finalized winners a permanent rounding result too.
        for meal in db_session.query(Session):
            for target, person, finalized, at, actor in (
                ('student', meal.winner_student_id, meal.finalized, meal.finalized_at, meal.finalized_by),
                ('faculty', meal.faculty_pick_teacher_id, meal.faculty_finalized, meal.faculty_finalized_at, meal.faculty_finalized_by),
            ):
                if not finalized or not person:
                    continue
                winner_column = (SessionDrawEvent.selected_teacher_id if target == 'faculty'
                                 else SessionDrawEvent.selected_student_id)
                exists = db_session.query(SessionDrawEvent.id).filter(
                    SessionDrawEvent.school_id == meal.school_id, SessionDrawEvent.session_id == meal.id,
                    SessionDrawEvent.draw_target == target, SessionDrawEvent.event_type == 'finalize',
                    winner_column == person,
                ).first()
                if not exists:
                    # A deterministic key prevents duplicate startup backfills.
                    from sqlalchemy.exc import IntegrityError
                    try:
                        with db_session.begin_nested():
                            db_session.add(SessionDrawEvent(
                                id=f'combo-legacy-{meal.id}-{target}', school_id=meal.school_id,
                                session_id=meal.id, event_type='finalize', draw_target=target,
                                selected_student_id=person if target == 'student' else None,
                                selected_teacher_id=person if target == 'faculty' else None,
                                selected_record_id=meal.faculty_pick_record_id if target == 'faculty' else None,
                                created_at=at or meal.created_at, created_by=actor,
                                combo_round_up=secrets.randbits(1),
                            ))
                    except IntegrityError:
                        pass  # A second WSGI worker already upgraded this winner.
        for event in db_session.query(SessionDrawEvent).filter(
            SessionDrawEvent.event_type == 'finalize', SessionDrawEvent.combo_round_up.is_(None),
        ):
            db_session.execute(update(SessionDrawEvent).where(
                SessionDrawEvent.id == event.id, SessionDrawEvent.combo_round_up.is_(None),
            ).values(combo_round_up=secrets.randbits(1)).execution_options(synchronize_session=False))
            db_session.expire(event, ['combo_round_up'])
        for teacher in db_session.query(Teacher).filter(
            Teacher.faculty_tickets_reset_at.isnot(None), Teacher.faculty_combo_round_up.is_(None),
        ):
            event = db_session.query(SessionDrawEvent).filter_by(
                school_id=teacher.school_id, selected_teacher_id=teacher.id,
                event_type='finalize', created_at=teacher.faculty_tickets_reset_at,
            ).first()
            coin = _coin(event) if event else secrets.randbits(1)
            db_session.execute(update(Teacher).where(
                Teacher.id == teacher.id, Teacher.faculty_combo_round_up.is_(None),
            ).values(faculty_combo_round_up=coin).execution_options(synchronize_session=False))
            db_session.expire(teacher, ['faculty_combo_round_up'])
        for school_id, in db_session.query(School.id):
            recalculate_school_tickets(school_id)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.remove()
