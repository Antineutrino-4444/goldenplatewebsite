"""School-wide standings across sessions for the current roster."""

import json
from collections import Counter, defaultdict

from sqlalchemy import func, literal

from .db import RosterSnapshot, School, Session, SessionDrawEvent, SessionRecord, SessionTicketEvent, Student, Teacher, db_session
from .draw_db import calculate_ticket_balances
from .faculty_draw import faculty_roster_ticket_totals
from .manual_draw import public_student_identifier
from .person_identity import teacher_names
from .utils import normalize_house


def _current_students(school_id):
    school = db_session.get(School, school_id)
    snapshot = db_session.query(RosterSnapshot).filter_by(
        id=school.current_roster_snapshot_id, school_id=school_id,
    ).first()
    # Historical identities can still be marked active in legacy databases.
    # Require membership in the saved current roster; never rebuild it from
    # those identities or fall back to them when no roster is available.
    members = json.loads(snapshot.data)['members'] if snapshot else {}
    return db_session.query(Student).filter(
        Student.school_id == school_id, Student.is_active == 1, Student.id.in_(members),
    )


def house_ticket_rankings(school_id):
    balances = calculate_ticket_balances(school_id)
    houses = defaultdict(lambda: {'tickets': 0, 'roster_count': 0})
    for student_id, house_name in _current_students(school_id).with_entities(Student.id, Student.house):
        house = normalize_house(house_name)
        if house:
            houses[house]['tickets'] += balances.get(student_id, 0)
            houses[house]['roster_count'] += 1
    return [{'house': name, **totals} for name, totals in sorted(houses.items())]


def _student_row(student):
    return {
        'student_id': student.id,
        'display_name': f'{student.preferred_name} {student.last_name}'.strip(),
    }


def _faculty_row(teacher):
    return {
        'category': 'faculty',
        'teacher_id': teacher.id,
        'display_name': teacher_names(teacher)[2],
    }


def _sort_rows(rows):
    return sorted(rows, key=lambda row: (
        -row['count'], row['display_name'].casefold(),
        row.get('student_id') or row.get('teacher_id') or '',
    ))


def _roster_records(sessions, school_id, roster, person_id, since):
    records = db_session.query(SessionRecord).filter(
        SessionRecord.school_id == school_id,
        SessionRecord.session_id.in_(sessions.with_entities(Session.id)),
        SessionRecord.is_excluded == 0, person_id.in_(roster),
        ~SessionRecord.dedupe_key.startswith('count:'),
    )
    if since is not None:
        records = records.filter(SessionRecord.recorded_at >= since)
    return records


def _plate_totals(records, person_id):
    plates = defaultdict(Counter)
    for key, category, count in records.with_entities(
        person_id, SessionRecord.category, func.count(SessionRecord.id),
    ).group_by(person_id, SessionRecord.category):
        plates[key]['clean' if category == 'faculty' else category] = count
    return plates


def _win_totals(sessions, school_id, *, faculty, since):
    wins = Counter()
    recorded = set()
    events = db_session.query(SessionDrawEvent).filter(
        SessionDrawEvent.school_id == school_id, SessionDrawEvent.event_type == 'finalize',
        SessionDrawEvent.draw_target == ('faculty' if faculty else 'student'),
        SessionDrawEvent.session_id.in_(sessions.with_entities(Session.id)),
    )
    if faculty:
        events = events.outerjoin(
            SessionRecord, (SessionRecord.id == SessionDrawEvent.selected_record_id) &
            (SessionRecord.school_id == school_id),
        )
        winner_id = func.coalesce(SessionDrawEvent.selected_teacher_id, SessionRecord.teacher_id)
    else:
        winner_id = SessionDrawEvent.selected_student_id
    if since is not None:
        events = events.filter(SessionDrawEvent.created_at >= since)
    for meal_id, key in events.with_entities(SessionDrawEvent.session_id, winner_id):
        if key:
            wins[key] += 1
            recorded.add((meal_id, key))

    # Older sessions can retain a finalized winner without a corresponding event.
    if faculty:
        finalized_meals = sessions.outerjoin(
            SessionRecord, (SessionRecord.id == Session.faculty_pick_record_id) &
            (SessionRecord.school_id == school_id),
        ).filter(Session.faculty_finalized == 1)
        winner_id = func.coalesce(Session.faculty_pick_teacher_id, SessionRecord.teacher_id)
        finalized_at = Session.faculty_finalized_at
    else:
        finalized_meals = sessions.filter(Session.finalized == 1)
        winner_id, finalized_at = Session.winner_student_id, Session.finalized_at
    if since is not None:
        finalized_meals = finalized_meals.filter(func.coalesce(finalized_at, Session.created_at) >= since)
    for meal_id, key in finalized_meals.with_entities(Session.id, winner_id):
        if key and (meal_id, key) not in recorded:
            wins[key] += 1
    return wins


def _student_ticket_balances(records, sessions, school_id, since):
    if since is None:
        # All-time standings use cumulative balances, including legacy tickets.
        return calculate_ticket_balances(school_id)

    plates = records.filter(SessionRecord.category.in_(['clean', 'red'])).with_entities(
        SessionRecord.student_id, SessionRecord.recorded_at.label('occurred_at'),
        literal(0).label('priority'), SessionRecord.id.label('event_id'),
        SessionRecord.category.label('action'), literal(1).label('delta'),
    )
    # Plate actions come from the surviving records. Independent actions, such as
    # finalizing a winner, come from the ticket ledger.
    actions = db_session.query(
        SessionTicketEvent.student_id, SessionTicketEvent.occurred_at, literal(1),
        SessionTicketEvent.id, SessionTicketEvent.event_type, SessionTicketEvent.tickets_delta,
    ).filter(
        SessionTicketEvent.school_id == school_id, SessionTicketEvent.occurred_at >= since,
        SessionTicketEvent.session_id.in_(sessions.with_entities(Session.id)),
        SessionTicketEvent.session_record_id.is_(None),
        SessionTicketEvent.event_type.in_(['reset', 'manual_adjust']),
    )
    balances = Counter()
    for key, _, _, _, action, delta in plates.union_all(actions).order_by('occurred_at', 'priority', 'event_id'):
        balances[key] = 0 if action in ('red', 'reset') else max(0, balances[key] + delta)
    return balances


def _historical_student_ticket_totals(plates, sessions, school_id, roster):
    # Every valid roster clean plate earned one ticket, including legacy plates
    # recorded before the ticket ledger existed. Resets never subtract earnings.
    totals = Counter({key: counts['clean'] for key, counts in plates.items()})
    # Independent grants have no plate record; count them once, without adding
    # the normal linked earn events a second time or counting negative actions.
    grants = db_session.query(
        SessionTicketEvent.student_id, func.sum(SessionTicketEvent.tickets_delta),
    ).filter(
        SessionTicketEvent.school_id == school_id,
        SessionTicketEvent.student_id.in_(roster),
        SessionTicketEvent.session_id.in_(sessions.with_entities(Session.id)),
        SessionTicketEvent.session_record_id.is_(None),
        SessionTicketEvent.event_type.in_(['earn', 'manual_adjust']),
        SessionTicketEvent.tickets_delta > 0,
    ).group_by(SessionTicketEvent.student_id)
    totals.update(dict(grants.all()))
    return totals


def school_individual_rankings(school_id, *, public_only=False):
    school = db_session.get(School, school_id)
    sessions = db_session.query(Session).filter(Session.school_id == school_id, Session.status != 'discarded')
    if public_only:
        sessions = sessions.filter(Session.is_public == 1)
    rankings = {'clean': {}, 'red': {}, 'tickets': None if public_only else {},
                'historical_tickets': None if public_only else {}}
    groups = (
        # Membership comes from today's roster; a returning student's permanent
        # identity keeps their totals from earlier rosters as well.
        ('students', Student, SessionRecord.student_id, None, _student_row),
        ('faculty', Teacher, SessionRecord.teacher_id, school.teacher_roster_uploaded_at, _faculty_row),
    )
    for group, model, person_id, since, make_row in groups:
        is_faculty = group == 'faculty'
        roster_query = (db_session.query(model).filter_by(school_id=school_id, is_active=1)
                        if is_faculty else _current_students(school_id))
        roster = {person.id: person for person in roster_query}
        records = _roster_records(sessions, school_id, roster_query.with_entities(model.id), person_id, since)
        if is_faculty:
            records = records.filter(SessionRecord.category == 'faculty',
                                     SessionRecord.faculty_roster_entry.is_distinct_from(0))
        else:
            records = records.filter(SessionRecord.category != 'faculty', SessionRecord.is_manual_entry == 0)
        plates = _plate_totals(records, person_id)
        wins = _win_totals(sessions, school_id, faculty=is_faculty, since=since)
        rows = {key: make_row(person) for key, person in roster.items()}
        if not public_only:
            balances = (faculty_roster_ticket_totals(school_id, since=since) if is_faculty else
                        _student_ticket_balances(records, sessions, school_id, since))
            if is_faculty:
                lifetime_records = _roster_records(
                    sessions, school_id, roster_query.with_entities(model.id), person_id, None,
                ).filter(SessionRecord.category == 'faculty',
                         SessionRecord.faculty_roster_entry.is_distinct_from(0))
                historical = {key: counts['clean'] for key, counts in
                              _plate_totals(lifetime_records, person_id).items()}
            else:
                historical = _historical_student_ticket_totals(plates, sessions, school_id, roster)
            names = Counter(' '.join(row['display_name'].casefold().split()) for row in rows.values())

        for key, row in rows.items():
            clean, dirty, red = (plates[key][metric] for metric in ('clean', 'dirty', 'red'))
            total = clean + dirty + red
            stats = {'clean': clean, 'red': None if is_faculty else red, 'wins': wins[key],
                     'clean_rate': clean / total * 100 if not is_faculty and total else None}
            row['stats'] = stats
            if not public_only:
                stats['tickets'] = balances.get(key, 0)
                stats['historical_tickets'] = historical.get(key, 0)
                if names[' '.join(row['display_name'].casefold().split())] > 1:
                    person = roster[key]
                    if is_faculty and person.faculty_identifier:
                        row['faculty_identifier'] = person.faculty_identifier
                    elif not is_faculty:
                        identifier = public_student_identifier(person.student_identifier)
                        if identifier:
                            row['student_identifier'] = identifier

        metrics = ['clean'] if is_faculty else ['clean', 'red']
        if not public_only:
            metrics.extend(['tickets', 'historical_tickets'])
        for metric in metrics:
            rankings[metric][group] = _sort_rows(
                {**row, 'count': row['stats'][metric]} for row in rows.values()
                if metric != 'red' or row['stats'][metric]
            )
    return rankings
