"""On-demand, school-scoped assembly slides built from the saved dashboard counts."""

from datetime import timezone
from hashlib import sha256
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Response, jsonify, request
from sqlalchemy import case, func
from sqlalchemy.orm import Bundle
from werkzeug.utils import secure_filename

from . import recorder_bp
from .db import INTERSCHOOL_SCHOOL_ID, School, Session, SessionDrawEvent, SessionRecord, Student, Teacher, _now_utc, db_session
from .draw_db import is_manual_draw_participant
from .live_counter_routes import DEFAULT_TIMEZONE, _settings
from .security import get_current_user
from .session_metrics import session_metrics
from .email_policy import account_requires_email
from .person_identity import faculty_pick_names
from .ticket_combos import faculty_key, replay_school_tickets
from .users import get_school_by_slug, get_user_by_id
from .utils import normalize_house


_RESULT_STATUSES = ('active', 'archived')


def public_presentation_school_name(school_id):
    private_result = db_session.query(Session.id).filter(
        Session.school_id == School.id, Session.status.in_(_RESULT_STATUSES),
        Session.is_public.is_distinct_from(1),
    ).exists()
    return db_session.query(School.name).filter(
        School.id == school_id, School.status == 'active', School.id != INTERSCHOOL_SCHOOL_ID,
        School.guest_privacy_enabled == 0, ~private_result,
    ).scalar()


def _snapshot_rows(school_id):
    # Read privacy, totals, and the last two results in one database snapshot.
    # Changes to session visibility during a download cannot split the access
    # decision from the data it covers. Only these two rows leave the database.
    counts = (Session.clean_number, Session.faculty_number, Session.dirty_number, Session.red_number)
    has_result = sum(func.coalesce(column, 0) for column in counts) > 0
    return db_session.query(
        School.name, School.slug, School.guest_privacy_enabled, School.live_counter_settings,
        Session.id.label('lunch_id'), Session.main_session_id, Session.session_name, Session.created_at,
        Bundle('session_counts', *counts),
        Bundle('all_counts', *(func.sum(column).over().label(column.key) for column in counts)),
        func.sum(case((has_result, 1), else_=0)).over().label('result_count'),
        func.min(case((Session.id.is_(None), 1), (Session.is_public == 1, 1), else_=0)).over().label('all_public'),
    ).select_from(School).outerjoin(
        Session, (Session.school_id == School.id) & Session.status.in_(_RESULT_STATUSES),
    ).filter(
        School.id == school_id, School.status == 'active', School.id != INTERSCHOOL_SCHOOL_ID,
    ).order_by(has_result.desc(), Session.created_at.desc().nullslast(), Session.id.desc()).limit(2).all()


def _counts_record(counts):
    metrics = session_metrics(counts)
    return {
        'student_clean': metrics['clean_count'],
        'faculty_clean': metrics['faculty_clean_count'],
        'clean': metrics['clean_count'] + metrics['faculty_clean_count'],
        'dirty': metrics['dirty_count'],
        'very_dirty': metrics['red_count'],
        'total': metrics['total_recorded'],
        'clean_percentage': metrics['clean_percentage'],
    }


def _snapshot(rows):
    school = rows[0]
    try:
        settings = _settings(school)
    except (TypeError, ValueError):
        settings = {}
    try:
        reporting_zone = ZoneInfo(settings.get('timezone', DEFAULT_TIMEZONE))
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        reporting_zone = ZoneInfo(DEFAULT_TIMEZONE)
    milestone = settings.get('milestone')
    results = []
    for row in rows:
        metrics = _counts_record(row.session_counts)
        if metrics['total']:
            stamp = row.created_at
            if stamp is not None and stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)  # SQLite stores UTC without an offset.
            results.append({
                'name': row.session_name,
                'date': stamp.astimezone(reporting_zone).date().isoformat() if stamp else None,
                **metrics,
            })
    latest = results[0] if results else None
    previous = results[1] if len(results) > 1 else None
    change = None
    if previous:
        clean_delta = latest['clean'] - previous['clean']
        change = {
            'clean': clean_delta,
            'total': latest['total'] - previous['total'],
            'clean_percentage_points': round(latest['clean_percentage'] - previous['clean_percentage'], 1),
            'clean_relative_percent': round(100 * clean_delta / previous['clean'], 1) if previous['clean'] else None,
        }
    return {
        'school_name': school.name,
        'school_code': school.slug,
        'milestone': milestone if type(milestone) is int and milestone > 0 else None,
        'generated_at': _now_utc().isoformat(),
        'reporting_timezone': reporting_zone.key,
        'totals': {**_counts_record(school.all_counts), 'session_count': school.result_count},
        'latest': latest, 'previous': previous, 'change': change,
    }


def _latest_selection(draw, role):
    event = SessionDrawEvent
    # Draw Center also identifies older faculty events by the selected record.
    target = case(((event.draw_target == 'faculty') | (SessionRecord.category == 'faculty'), 'faculty'),
                  else_='student')
    round_filter = event.draw_number == draw.draw_number
    if draw.draw_number == 1:
        round_filter = round_filter | event.draw_number.is_(None)
    pick = db_session.query(
        event.event_type, event.selected_student_id, event.selected_teacher_id, event.selected_record_id,
        event.faculty_name, event.faculty_ticket_scope, event.tickets_at_event, event.probability_at_event,
        event.eligible_pool_size,
    ).outerjoin(SessionRecord, (SessionRecord.id == event.selected_record_id)
                & (SessionRecord.school_id == event.school_id)).filter(
        event.school_id == draw.school_id, event.session_id == draw.id, round_filter, target == role,
        event.event_type.in_(('draw', 'override', 'restore')),
    ).order_by(event.created_at.desc().nullslast(), event.id.desc()).first()
    return pick if pick and pick.event_type != 'restore' else None


def _matches_faculty_pick(event, draw, faculty):
    if not event:
        return False
    ids = [(event.selected_teacher_id, faculty['teacher_id']),
           (event.selected_record_id, draw.faculty_pick_record_id)]
    matches = [selected == winner for selected, winner in ids if selected and winner]
    if matches:
        return all(matches)
    # Older picks sometimes have only their recorded display name. Use the
    # name at selection even if the roster display name has changed since.
    return (not event.selected_teacher_id and not event.selected_record_id and bool(event.faculty_name)
            and event.faculty_name.strip().casefold() == faculty['recorded_name'].strip().casefold())


def _selection_details(event, student_draw=None):
    data = {}
    if student_draw:
        method = {'random': 'random', 'manual': 'manual', 'override': 'manual'}.get(student_draw.method)
        if not method and student_draw.override_applied:
            method = 'manual'
        data.update(tickets=student_draw.tickets_at_selection, probability=student_draw.probability_at_selection,
                    pool_size=student_draw.eligible_pool_size, method=method)
    if event:
        saved = dict(tickets=event.tickets_at_event, probability=event.probability_at_event,
                     pool_size=event.eligible_pool_size, method='manual' if event.event_type == 'override' else 'random')
        data.update({key: value for key, value in saved.items() if value is not None})
    if data.get('probability') is not None:
        data['probability'] /= 100  # Draw Center persists percentages as basis points.
    return {key: value for key, value in data.items() if value is not None}


def _faculty_combo_key(draw, faculty, pick):
    record_id = draw.faculty_pick_record_id or (pick.selected_record_id if pick else None)
    if record_id:
        entry = db_session.query(SessionRecord, Teacher, Session).select_from(SessionRecord).join(
            Session, Session.id == SessionRecord.session_id,
        ).outerjoin(Teacher, (Teacher.id == SessionRecord.teacher_id) & (Teacher.school_id == draw.school_id)).filter(
            SessionRecord.id == record_id, SessionRecord.school_id == draw.school_id, SessionRecord.category == 'faculty',
            Session.school_id == draw.school_id, Session.status.in_(_RESULT_STATUSES),
            (Session.id == draw.id) | (Session.main_session_id == draw.id),
        ).one_or_none()
        if entry:
            record, teacher, meal = entry
            if record.teacher_id and (not teacher or faculty['teacher_id'] not in (None, record.teacher_id)):
                return None
            return faculty_key(record, teacher, {meal.id: meal})
    teacher_id = draw.faculty_pick_teacher_id or (pick.selected_teacher_id if pick else None)
    if teacher_id:
        teacher = db_session.query(Teacher).filter_by(id=teacher_id, school_id=draw.school_id).one_or_none()
        if teacher is None:
            return None
        scope = pick.faculty_ticket_scope if pick else None
        roster = scope == 'roster' if scope else teacher.is_active or teacher.faculty_identifier
        return 'faculty', teacher.id, 'roster' if roster else draw.id
    if record_id:
        return None  # An unmatched explicit record cannot identify a person by name.
    # A name-only manual record is keyed by its normalized name in this draw.
    # Only an existing replay state can supply a gain for that legacy identity.
    return 'faculty', ' '.join(faculty['recorded_name'].casefold().split()), draw.id


def _attach_finalized_winners(snapshot, school_id, latest_row):
    if not snapshot['latest']:
        return
    # An extra lunch participates in the main lunch's draw.
    draw_id = latest_row.main_session_id or latest_row.lunch_id
    draw = db_session.query(Session).filter(
        Session.id == draw_id, Session.school_id == school_id, Session.status.in_(_RESULT_STATUSES),
    ).one_or_none()
    if draw is None:
        return
    people, details = {}, {}
    student = faculty_combo = None
    if draw.finalized and draw.winner_student_id:
        student = db_session.query(Student).filter_by(id=draw.winner_student_id, school_id=school_id).one_or_none()
        if student:
            people['student'] = (f'{student.preferred_name} {student.last_name}'.strip(), student.id)
            pick = _latest_selection(draw, 'student')
            values = _selection_details(pick if pick and pick.selected_student_id == student.id else None, draw)
            profile = {'grade': student.grade, 'house': normalize_house(student.house), 'clan': student.clan}
            values.update({key: value for key, value in profile.items() if value})
            if values:
                details['student'] = values
    if draw.faculty_finalized:
        faculty = faculty_pick_names(draw)
        name = faculty['display_name']
        if name:
            people['faculty'] = (name, faculty['teacher_id'] or draw.faculty_pick_record_id or name)
            pick = _latest_selection(draw, 'faculty')
            pick = pick if _matches_faculty_pick(pick, draw, faculty) else None
            if pick:
                details['faculty'] = _selection_details(pick)
            faculty_combo = _faculty_combo_key(draw, faculty, pick)
    if people:
        states = replay_school_tickets(school_id)[0]
        if student:
            manual = is_manual_draw_participant(draw.id, student.id)
            if student.is_active or manual:
                state = states.get(('student', student.id, draw.id if manual else 'roster'))
                details.setdefault('student', {})['next_ticket_gain'] = state.next_gain if state else 1
        if faculty_combo:
            state = states.get(faculty_combo)
            if state or faculty_combo[2] == 'roster':
                details.setdefault('faculty', {})['next_ticket_gain'] = state.next_gain if state else 1
        snapshot['winner_names'] = {role: name for role, (name, _) in people.items()}
        if details:
            snapshot['winner_details'] = details
        # A new recipient can share a display name with last week's recipient.
        # Discriminate awards without exporting the lunch or roster identifiers.
        snapshot['winner_keys'] = {
            role: sha256(f'gp-award/v1|{school_id}|{draw.id}|{role}|{person}'.encode()).hexdigest()
            for role, (_, person) in people.items()
        }


def _error(message, status, code=None):
    payload = {'error': message}
    if code:
        payload['code'] = code
    return jsonify(payload), status, {'Cache-Control': 'no-store'}


def school_label_from(data):
    value = data.get('school_label')
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('Enter a school display name as text.')
    label = ' '.join(value.split())
    if len(label) > 200 or any(unicodedata.category(c) in ('Cc', 'Cs') or c in '\ufffe\uffff' for c in label):
        raise ValueError('Enter a school display name of up to 200 characters without control characters.')
    return label or None


def assembly_snapshot_for_owner(school_id, user_id, *, with_winners=False):
    """Recheck a connected teacher's current access before each cloud update."""
    owner = get_user_by_id(user_id)
    if (not owner or owner.status != 'active' or owner.is_record_actor or owner.school_id != school_id
            or owner.role not in ('user', 'admin', 'superadmin') or account_requires_email(owner)):
        return None
    rows = _snapshot_rows(school_id)
    if not rows:
        return None
    snapshot = _snapshot(rows)
    if with_winners:
        _attach_finalized_winners(snapshot, school_id, rows[0])
    return snapshot


@recorder_bp.post('/resources/presentations/download')
def download_school_presentation():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error('Enter the school code and presentation options.', 400)
    school_code = data.get('school_code')
    kind = data.get('kind')
    theme = data.get('theme')
    output = data.get('format')
    if not isinstance(school_code, str) or not school_code.strip():
        return _error('Enter a school code.', 400)
    if kind not in ('assembly', 'overview') or theme not in ('light', 'dark') or output not in ('pptx', 'google-slides', 'pdf'):
        return _error('Choose a presentation, theme, and file format.', 400)
    try:
        school_label = school_label_from(data)
    except ValueError as error:
        return _error(str(error), 400)

    school = get_school_by_slug(school_code)
    rows = _snapshot_rows(school.id) if school else []
    if not rows:
        return _error('No active school matches this code.', 404)
    access = rows[0]
    is_private = access.guest_privacy_enabled != 0 or access.all_public != 1
    is_powerpoint_assembly = kind == 'assembly' and output == 'pptx'
    actor = get_current_user() if is_private or is_powerpoint_assembly else None
    is_school_member = bool(actor and actor['school_id'] == school.id
                            and actor['role'] in ('user', 'admin', 'superadmin'))
    if is_private:
        if not actor:
            return _error('Sign in with an account at this school to download its results.', 401, 'SCHOOL_LOGIN_REQUIRED')
        if not is_school_member:
            return _error('Switch to an account at this school to download its results.', 403, 'WRONG_SCHOOL_ACCOUNT')
        if actor['email_required']:
            return _error('Verify your account email to download private school results.', 403, 'ACCOUNT_EMAIL_REQUIRED')

    snapshot = _snapshot(rows)
    if is_powerpoint_assembly and is_school_member and not actor['email_required']:
        _attach_finalized_winners(snapshot, school.id, access)
    snapshot['school_label'] = school_label
    platform = 'powerpoint' if output == 'pptx' else output
    from src.services.presentation_exports import generate_deck
    content = generate_deck(kind, theme, snapshot, platform=platform)
    extension = 'pdf' if output == 'pdf' else 'pptx'
    mime = 'application/pdf' if extension == 'pdf' else 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    school_filename = secure_filename(snapshot['school_code'])[:80] or 'school'
    filename = f"{school_filename}-{kind}-{theme}-{snapshot['generated_at'][:10]}.{extension}"
    return Response(content, mimetype=mime, headers={
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
    })
