"""School-wide standings and the relevant draw odds for each person."""

from collections import Counter, defaultdict

from sqlalchemy import case, func

from .db import Session, SessionDrawEvent, SessionRecord, Student, Teacher, db_session
from .draw_db import calculate_ticket_balances, get_eligible_students_with_tickets
from .faculty_draw import faculty_roster_ticket_totals, faculty_ticket_summary
from .manual_draw import public_student_identifier
from .person_identity import teacher_names
from .utils import make_student_key, normalize_house, normalize_name


def house_ticket_rankings(school_id):
    balances = calculate_ticket_balances(school_id)
    houses = defaultdict(lambda: {'tickets': 0, 'roster_count': 0})
    for student_id, house_name in db_session.query(Student.id, Student.house).filter_by(
        school_id=school_id, is_active=1,
    ):
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


def _plate_totals(sessions, school_id, students, faculty, people, plates):
    unlinked = (SessionRecord.student_id.is_(None)) & (SessionRecord.teacher_id.is_(None))
    preferred_group = case((unlinked, func.lower(func.trim(SessionRecord.preferred_name))))
    last_group = case((unlinked, func.lower(func.trim(SessionRecord.last_name))))
    records = db_session.query(
        SessionRecord.category, SessionRecord.student_id, SessionRecord.teacher_id,
        func.min(SessionRecord.preferred_name), func.min(SessionRecord.last_name), func.count(SessionRecord.id),
    ).filter(
        SessionRecord.session_id.in_(sessions.with_entities(Session.id)),
        SessionRecord.school_id == school_id, SessionRecord.is_excluded == 0,
        ~SessionRecord.dedupe_key.startswith('count:'),
    )

    for category, student_id, teacher_id, preferred, last, count in records.group_by(
        SessionRecord.category, SessionRecord.student_id, SessionRecord.teacher_id, preferred_group, last_group,
    ):
        student = students.get(student_id)
        teacher = faculty.get(teacher_id)
        group = 'faculty' if category == 'faculty' else 'students'
        if category == 'faculty' and teacher:
            key, row = teacher.id, _faculty_row(teacher)
        elif category != 'faculty' and student:
            key, row = student.id, _student_row(student)
        else:
            preferred, last = normalize_name(preferred), normalize_name(last)
            display_name = f'{preferred} {last}'.strip()
            if not display_name:
                continue
            row = {'display_name': display_name, 'category': category}
            if category != 'faculty':
                row['student_key'] = make_student_key(preferred, last)
            key = row.get('student_key') or display_name.casefold()
        people[group][key] = row
        plates[group][key]['clean' if category == 'faculty' else category] += count


def _win_totals(sessions, school_id):
    wins = {'students': Counter(), 'faculty': Counter()}
    recorded = set()
    # A confirmed redraw leaves prior finalizations in the draw history.
    events = db_session.query(
        SessionDrawEvent.session_id, SessionDrawEvent.draw_target, SessionDrawEvent.selected_student_id,
        SessionDrawEvent.selected_teacher_id, SessionDrawEvent.faculty_name, SessionRecord.teacher_id,
    ).outerjoin(
        SessionRecord, (SessionRecord.id == SessionDrawEvent.selected_record_id) &
        (SessionRecord.school_id == school_id),
    ).filter(
        SessionDrawEvent.school_id == school_id, SessionDrawEvent.event_type == 'finalize',
        SessionDrawEvent.session_id.in_(sessions.with_entities(Session.id)),
    )
    for session_id, target, student_id, teacher_id, name, record_teacher_id in events:
        group = 'faculty' if target == 'faculty' else 'students'
        key = (teacher_id or record_teacher_id or normalize_name(name).casefold()) if group == 'faculty' else student_id
        if key:
            wins[group][key] += 1
            recorded.add((session_id, group, key))

    # Older sessions can retain a finalized winner without a corresponding event.
    finalized_meals = sessions.outerjoin(
        SessionRecord, (SessionRecord.id == Session.faculty_pick_record_id) &
        (SessionRecord.school_id == school_id),
    ).with_entities(
        Session.id, Session.winner_student_id, Session.finalized, Session.faculty_pick_teacher_id,
        SessionRecord.teacher_id, Session.faculty_pick_display_name, Session.faculty_finalized,
    ).filter((Session.finalized == 1) | (Session.faculty_finalized == 1))
    for meal_id, student_id, student_finalized, teacher_id, record_teacher_id, name, faculty_finalized in finalized_meals:
        for group, key, finalized in (
            ('students', student_id, student_finalized),
            ('faculty', teacher_id or record_teacher_id or normalize_name(name).casefold(), faculty_finalized),
        ):
            if finalized and key and (meal_id, group, key) not in recorded:
                wins[group][key] += 1
    return wins


def _draw_pool(sessions, current, group, balances, roster):
    finalized = Session.finalized if group == 'students' else Session.faculty_finalized
    eligible_sessions = sessions.filter(Session.main_session_id.is_(None), finalized == 0)
    if current and current.status != 'discarded' and not getattr(current, finalized.key):
        meal, source = current, 'current'
    else:
        if current:
            eligible_sessions = eligible_sessions.filter(Session.created_at > current.created_at)
        meal = eligible_sessions.filter(Session.status == 'active').order_by(Session.created_at, Session.id).first()
        source = 'upcoming'

    if not meal:
        return {'source': 'projected'}, {
            key: tickets for key, tickets in balances.items() if key in roster and roster[key].is_active
        }

    if group == 'students':
        pool = {student.id: tickets for student, tickets in get_eligible_students_with_tickets(meal.id)}
    else:
        pool = {row['teacher_id'] or row['display_name'].casefold(): row['tickets']
                for row in faculty_ticket_summary(meal)['candidates']}
    return {'source': source, 'session_name': meal.session_name}, pool


def school_individual_rankings(school_id, *, session_id=None, public_only=False):
    students = {student.id: student for student in db_session.query(Student).filter_by(school_id=school_id)}
    faculty = {teacher.id: teacher for teacher in db_session.query(Teacher).filter_by(school_id=school_id)}
    sessions = db_session.query(Session).filter(Session.school_id == school_id, Session.status != 'discarded')
    if public_only:
        sessions = sessions.filter(Session.is_public == 1)

    rosters = {'students': students, 'faculty': faculty}
    people = {group: {} for group in rosters}
    plates = {group: defaultdict(Counter) for group in rosters}
    _plate_totals(sessions, school_id, students, faculty, people, plates)
    wins = _win_totals(sessions, school_id)
    rankings = {'clean': {}, 'red': {}, 'tickets': None, 'draw_context': {}}

    if not public_only:
        rankings['tickets'] = {}
        balances = {'students': calculate_ticket_balances(school_id),
                    'faculty': faculty_roster_ticket_totals(school_id, active_only=False)}
        current = db_session.query(Session).filter_by(school_id=school_id, id=session_id).first() if session_id else None
        if current and current.main_session_id:
            current = db_session.query(Session).filter_by(school_id=school_id, id=current.main_session_id).first()
        for group, roster in rosters.items():
            make_row = _student_row if group == 'students' else _faculty_row
            for key in balances[group]:
                if key in roster and key not in people[group]:
                    people[group][key] = make_row(roster[key])

    names = Counter(' '.join(row['display_name'].casefold().split())
                    for rows in people.values() for row in rows.values())
    for group, roster in rosters.items():
        is_student = group == 'students'
        group_balances = pool = {}
        if not public_only:
            group_balances = balances[group]
            rankings['draw_context'][group], pool = _draw_pool(sessions, current, group, group_balances, roster)
        pool_total = sum(pool.values())
        rows = []
        for key, identity in people[group].items():
            clean, dirty, red = (plates[group][key][metric] for metric in ('clean', 'dirty', 'red'))
            total = clean + dirty + red
            stats = {'clean': clean, 'red': red if is_student else None, 'wins': wins[group][key],
                     'clean_rate': clean / total * 100 if is_student and total else None}
            row = {**identity, 'stats': stats}
            if not public_only:
                draw_tickets = pool.get(key, 0)
                stats.update(tickets=group_balances.get(key, 0), draw_tickets=draw_tickets,
                             draw_odds=draw_tickets / pool_total * 100 if pool_total else 0)
                if names[' '.join(row['display_name'].casefold().split())] > 1:
                    person = roster.get(key)
                    if is_student:
                        row['student_identifier'] = public_student_identifier(person.student_identifier) if person else None
                    else:
                        row['faculty_identifier'] = person.faculty_identifier if person else None
            rows.append(row)

        rankings['clean'][group] = _sort_rows({**row, 'count': row['stats']['clean']} for row in rows if row['stats']['clean'])
        if is_student:
            rankings['red'][group] = _sort_rows({**row, 'count': row['stats']['red']} for row in rows if row['stats']['red'])
        if not public_only:
            id_field = 'student_id' if is_student else 'teacher_id'
            rankings['tickets'][group] = _sort_rows({**row, 'count': row['stats']['tickets']} for row in rows
                                                   if id_field in row or row['stats']['draw_tickets'])
    return rankings
