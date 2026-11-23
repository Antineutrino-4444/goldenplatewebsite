"""On-demand, school-scoped assembly slides built from the saved dashboard counts."""

from datetime import timezone
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Response, jsonify, request
from sqlalchemy import case, func
from sqlalchemy.orm import Bundle
from werkzeug.utils import secure_filename

from . import recorder_bp
from .db import INTERSCHOOL_SCHOOL_ID, School, Session, _now_utc, db_session
from .live_counter_routes import DEFAULT_TIMEZONE, _settings
from .security import get_current_user
from .session_metrics import session_metrics
from .email_policy import account_requires_email
from .users import get_school_by_slug, get_user_by_id


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
        Session.session_name, Session.created_at, Bundle('session_counts', *counts),
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
        'totals': {**_counts_record(school.all_counts), 'session_count': school.result_count},
        'latest': latest, 'previous': previous, 'change': change,
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


def assembly_snapshot_for_owner(school_id, user_id):
    """Recheck a connected teacher's current access before each cloud update."""
    owner = get_user_by_id(user_id)
    if (not owner or owner.status != 'active' or owner.is_record_actor or owner.school_id != school_id
            or owner.role not in ('user', 'admin', 'superadmin') or account_requires_email(owner)):
        return None
    rows = _snapshot_rows(school_id)
    return _snapshot(rows) if rows else None


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
    if access.guest_privacy_enabled != 0 or access.all_public != 1:
        actor = get_current_user()
        if not actor:
            return _error('Sign in with an account at this school to download its results.', 401, 'SCHOOL_LOGIN_REQUIRED')
        if actor['school_id'] != school.id or actor['role'] not in ('user', 'admin', 'superadmin'):
            return _error('Switch to an account at this school to download its results.', 403, 'WRONG_SCHOOL_ACCOUNT')
        if actor['email_required']:
            return _error('Verify your account email to download private school results.', 403, 'ACCOUNT_EMAIL_REQUIRED')

    snapshot = _snapshot(rows)
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
