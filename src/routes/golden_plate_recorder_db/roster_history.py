"""Immutable membership snapshots; never reconstruct old rosters from today's rows."""

import json
from types import SimpleNamespace

from .db import RosterSnapshot, School, Session, SessionRecord, Student, _now_utc, db_session
from .utils import normalize_house


def current_roster_snapshot(school_id, *, refresh=False):
    school = db_session.get(School, school_id)
    previous = db_session.query(RosterSnapshot).filter_by(
        id=school.current_roster_snapshot_id, school_id=school_id,
    ).first() if school.current_roster_snapshot_id else None
    if previous and not refresh:
        return previous
    students = db_session.query(Student).filter_by(school_id=school_id, is_active=1).all()
    members = {student.id: normalize_house(student.house) for student in students}
    if not members:
        school.current_roster_snapshot_id = None
        return None
    populations = {}
    for house in members.values():
        if house:
            populations[house] = populations.get(house, 0) + 1
    data = json.dumps({'members': members, 'populations': populations,
                       'missing_house_count': sum(not house for house in members.values())}, sort_keys=True)
    # Re-uploading identical membership does not change a session's population.
    if previous and previous.data == data:
        return previous
    snapshot = RosterSnapshot(school_id=school_id, filename=school.roster_filename, data=data)
    db_session.add(snapshot)
    db_session.flush()
    school.current_roster_snapshot_id = snapshot.id
    return snapshot


def bind_empty_sessions(school_id, snapshot):
    if not snapshot:
        return
    populated = db_session.query(SessionRecord.session_id).filter(
        SessionRecord.school_id == school_id, SessionRecord.category != 'faculty',
    )
    for meal in db_session.query(Session).filter(
        Session.school_id == school_id, Session.status == 'active', ~Session.id.in_(populated),
    ).all():
        if meal.roster_snapshot_id != snapshot.id:
            meal.roster_matched_at = None
            meal.roster_matched_by = None
        meal.roster_snapshot_id = snapshot.id
        meal.roster_mixed = 0


def prepare_recording_roster(meal):
    """Associate student records with a roster without relabeling historical meals."""
    snapshot = current_roster_snapshot(meal.school_id)
    has_students = db_session.query(SessionRecord.id).filter(
        SessionRecord.session_id == meal.id, SessionRecord.school_id == meal.school_id,
        SessionRecord.category != 'faculty',
    ).first() is not None
    if not has_students:
        if meal.roster_snapshot_id != (snapshot.id if snapshot else None):
            meal.roster_matched_at = None
            meal.roster_matched_by = None
        meal.roster_snapshot_id = snapshot.id if snapshot else None
        meal.roster_mixed = 0
    elif meal.roster_snapshot_id and meal.roster_snapshot_id != (snapshot.id if snapshot else None):
        meal.roster_mixed = 1
    # An old populated session without a snapshot stays unavailable.


def match_session_to_current_roster(meal, actor_id, settings):
    """Explicitly attest a session's roster, after checking all its student counts."""
    from .house_estimation import estimate_house_stats

    snapshot = current_roster_snapshot(meal.school_id, refresh=True)
    if not snapshot:
        raise ValueError('No current student roster is available. Upload a student roster first.')
    matched_at = _now_utc()
    candidate = SimpleNamespace(school_id=meal.school_id, roster_snapshot_id=snapshot.id,
                                roster_mixed=0, roster_matched_at=matched_at)
    records = db_session.query(SessionRecord).filter(
        SessionRecord.school_id == meal.school_id, SessionRecord.session_id == meal.id,
        SessionRecord.category.in_(['clean', 'dirty', 'red']),
    ).all()
    estimation = estimate_house_stats(candidate, records, settings)
    if not estimation['available']:
        raise ValueError(estimation['reason'])
    meal.roster_snapshot_id = snapshot.id
    meal.roster_mixed = 0
    meal.roster_matched_at = matched_at
    meal.roster_matched_by = actor_id
    return estimation
