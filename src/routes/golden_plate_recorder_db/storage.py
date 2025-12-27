import json
import os
import uuid
from datetime import datetime

from .db import (
    DEFAULT_SCHOOL_ID,
    Session as SessionModel,
    SessionDeleteRequest,
    SessionRecord,
    Student,
    Teacher,
    User,
    db_session,
)
from .users import (
    DEFAULT_SUPERADMIN,
    ensure_default_superadmin,
    list_all_users,
    migrate_legacy_invite_codes,
    migrate_legacy_users,
    reset_user_store,
)
from .utils import extract_student_id_from_key, make_student_key, normalize_name, split_student_key

# Student lookup cache keyed by school for fast eligibility checks
student_lookup = {}

# Global in-memory state
session_data = {}
delete_requests = []
global_csv_data = {}
global_teacher_data = {}


def sync_students_table_from_csv_rows(rows, *, school_id=None):
    """Persist uploaded student roster into the students table."""
    result = {'processed': 0, 'created': 0, 'updated': 0}
    if not isinstance(rows, list) or not rows:
        return result

    school_id = school_id or DEFAULT_SCHOOL_ID

    unique_rows = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = normalize_name(row.get('Student ID'))
        if not identifier:
            continue
        key = identifier.lower()
        if key not in unique_rows:
            unique_rows[key] = (identifier, row)

    if not unique_rows:
        return result

    identifiers = [item[0] for item in unique_rows.values()]
    existing_students = (
        db_session.query(Student)
        .filter(Student.school_id == school_id, Student.student_identifier.in_(identifiers))
        .all()
    )
    existing_map = {student.student_identifier.lower(): student for student in existing_students}

    for key, (identifier, row) in unique_rows.items():
        preferred = normalize_name(row.get('Preferred'))
        last = normalize_name(row.get('Last'))
        if not preferred or not last:
            continue

        grade = normalize_name(row.get('Grade'))
        advisor = normalize_name(row.get('Advisor'))
        house = normalize_name(row.get('House'))
        clan = normalize_name(row.get('Clan'))

        student = existing_map.get(key)
        if student:
            changes = False
            if student.preferred_name != preferred:
                student.preferred_name = preferred
                changes = True
            if student.last_name != last:
                student.last_name = last
                changes = True
            new_grade = grade or None
            if student.grade != new_grade:
                student.grade = new_grade
                changes = True
            new_advisor = advisor or None
            if student.advisor != new_advisor:
                student.advisor = new_advisor
                changes = True
            new_house = house or None
            if student.house != new_house:
                student.house = new_house
                changes = True
            new_clan = clan or None
            if student.clan != new_clan:
                student.clan = new_clan
                changes = True
            if changes:
                result['updated'] += 1
        else:
            student = Student(
                id=str(uuid.uuid4()),
                school_id=school_id,
                student_identifier=identifier,
                preferred_name=preferred,
                last_name=last,
                grade=grade or None,
                advisor=advisor or None,
                house=house or None,
                clan=clan or None,
            )
            db_session.add(student)
            existing_map[key] = student
            result['created'] += 1

        result['processed'] += 1

    if result['processed']:
        try:
            db_session.commit()
            update_student_lookup()
        except Exception:
            db_session.rollback()
            raise

    return result


def sync_teacher_table_from_list(teachers, *, school_id=None):
    """Persist uploaded teacher roster into the teachers table."""
    result = {'processed': 0, 'created': 0, 'updated': 0}
    if not isinstance(teachers, list) or not teachers:
        return result

    school_id = school_id or DEFAULT_SCHOOL_ID

    unique_entries = {}
    for entry in teachers:
        if isinstance(entry, dict):
            name = normalize_name(entry.get('name'))
            display = normalize_name(entry.get('display_name') or entry.get('name'))
        else:
            name = normalize_name(entry)
            display = name
        if not name:
            continue
        key = name.lower()
        if key not in unique_entries:
            unique_entries[key] = (name, display)

    if not unique_entries:
        return result

    names = [item[0] for item in unique_entries.values()]
    existing_teachers = (
        db_session.query(Teacher)
        .filter(Teacher.school_id == school_id, Teacher.name.in_(names))
        .all()
    )
    existing_map = {teacher.name.lower(): teacher for teacher in existing_teachers}

    for key, (name, display) in unique_entries.items():
        teacher = existing_map.get(key)
        desired_display = display or None

        if teacher:
            if teacher.display_name != desired_display:
                teacher.display_name = desired_display
                result['updated'] += 1
        else:
            teacher = Teacher(
                id=str(uuid.uuid4()),
                school_id=school_id,
                name=name,
                display_name=desired_display,
            )
            db_session.add(teacher)
            existing_map[key] = teacher
            result['created'] += 1

        result['processed'] += 1

    if result['processed']:
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    return result


def update_student_lookup():
    """Hydrate the student lookup cache from the students table."""
    global student_lookup
    student_lookup = {}

    try:
        students = db_session.query(Student).all()
    except Exception as exc:
        db_session.rollback()
        print(f"Error building student lookup: {exc}")
        return

    for student in students:
        preferred = normalize_name(student.preferred_name)
        last = normalize_name(student.last_name)
        student_id = normalize_name(student.student_identifier)
        key = make_student_key(preferred, last, student_id)
        if not key:
            continue
        school_bucket = student_lookup.setdefault(student.school_id or DEFAULT_SCHOOL_ID, {})
        school_bucket[key] = {
            'preferred_name': preferred,
            'last_name': last,
            'grade': normalize_name(student.grade),
            'advisor': normalize_name(student.advisor),
            'house': normalize_name(student.house),
            'clan': normalize_name(student.clan),
            'student_id': student_id,
            'key': key
        }


def get_student_lookup_for_school(school_id):
    if not school_id:
        return {}
    return student_lookup.get(school_id, {})


def save_all_data():
    """Save all data - now a no-op as data persists in database tables."""
    print("All data is persisted in database tables")
    return True


def save_session_data():
    """Save session data - now a no-op as sessions persist in database tables."""
    return True


def _refresh_delete_requests_cache():
    """Refresh in-memory delete requests cache from the database."""
    global delete_requests

    try:
        db_session.expire_all()
    except Exception:
        db_session.rollback()

    try:
        request_rows = (
            db_session.query(SessionDeleteRequest)
            .order_by(SessionDeleteRequest.requested_at.desc())
            .all()
        )
    except Exception as exc:
        db_session.rollback()
        print(f"Error loading delete requests: {exc}")
        delete_requests = []
        return delete_requests

    session_ids = {row.session_id for row in request_rows if row.session_id}
    user_ids = set()
    for row in request_rows:
        if row.requested_by:
            user_ids.add(row.requested_by)
        if row.reviewed_by:
            user_ids.add(row.reviewed_by)

    sessions_map = {}
    if session_ids:
        try:
            sessions = (
                db_session.query(SessionModel)
                .filter(SessionModel.id.in_(session_ids))
                .all()
            )
            sessions_map = {sess.id: sess for sess in sessions}
        except Exception as exc:
            db_session.rollback()
            print(f"Error loading sessions for delete request cache: {exc}")

    users_map = {}
    if user_ids:
        try:
            users = db_session.query(User).filter(User.id.in_(user_ids)).all()
            users_map = {user.id: user for user in users}
        except Exception as exc:
            db_session.rollback()
            print(f"Error loading users for delete request cache: {exc}")

    serialized = []
    for row in request_rows:
        session_model = sessions_map.get(row.session_id)
        requester_user = users_map.get(row.requested_by)
        reviewer_user = users_map.get(row.reviewed_by)

        approved_by = reviewer_user.username if reviewer_user and row.status == 'approved' else None
        approved_at = _isoformat_timestamp(row.reviewed_at) if row.status == 'approved' else None
        rejected_by = reviewer_user.username if reviewer_user and row.status == 'rejected' else None
        rejected_at = _isoformat_timestamp(row.reviewed_at) if row.status == 'rejected' else None

        serialized.append({
            'id': row.id,
            'session_id': row.session_id,
            'school_id': row.school_id,
            'session_name': session_model.session_name if session_model else None,
            'requester_id': row.requested_by,
            'requester': requester_user.username if requester_user else None,
            'requester_name': requester_user.display_name if requester_user else None,
            'requested_at': _isoformat_timestamp(row.requested_at),
            'status': row.status,
            'reviewed_by_id': row.reviewed_by,
            'reviewed_by': reviewer_user.username if reviewer_user else None,
            'reviewed_at': _isoformat_timestamp(row.reviewed_at),
            'rejection_reason': row.rejection_reason,
            'approved_by': approved_by,
            'approved_at': approved_at,
            'rejected_by': rejected_by,
            'rejected_at': rejected_at,
            'total_records': (session_model.total_records or 0) if session_model else 0,
            'clean_records': (session_model.clean_number or 0) if session_model else 0,
            'dirty_records': (session_model.dirty_number or 0) if session_model else 0,
            'red_records': (session_model.red_number or 0) if session_model else 0,
            'faculty_clean_records': (session_model.faculty_number or 0) if session_model else 0,
        })

    delete_requests = serialized
    return delete_requests


def save_delete_requests():
    """Refresh delete requests cache from the database."""
    return _refresh_delete_requests_cache()


def save_global_csv_data():
    """Save global CSV data - now handled by students table."""
    update_student_lookup()
    return True


def save_global_teacher_data():
    """Save global teacher data - now handled by teachers table."""
    return True


def ensure_session_structure(session_info):
    """Ensure session data has the expected structure for counters and records."""
    if 'dirty_count' not in session_info:
        dirty_records = session_info.get('dirty_records', [])
        if isinstance(dirty_records, list):
            session_info['dirty_count'] = len(dirty_records)
        else:
            session_info['dirty_count'] = 0

    # Remove legacy dirty record tracking that stored names
    if 'dirty_records' in session_info:
        session_info['dirty_records'] = []

    if 'faculty_clean_records' not in session_info or not isinstance(session_info['faculty_clean_records'], list):
        session_info['faculty_clean_records'] = []

    if 'scan_history' not in session_info or not isinstance(session_info['scan_history'], list):
        session_info['scan_history'] = []

    if 'faculty_pick' not in session_info:
        session_info['faculty_pick'] = None

    # Strip any stored names from historic dirty scan history entries
    for record in session_info['scan_history']:
        if record.get('category') == 'dirty':
            record.pop('preferred_name', None)
            record.pop('first_name', None)
            record.pop('last_name', None)
            if not record.get('display_name'):
                record['display_name'] = 'Dirty Plate'

    for category in ['clean_records', 'red_records']:
        records = session_info.get(category)
        if not isinstance(records, list):
            session_info[category] = []
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            preferred = record.get('preferred_name') or record.get('first_name')
            last = record.get('last_name')
            student_id = record.get('student_id')
            key = record.get('student_key')
            if not key:
                key = make_student_key(preferred, last, student_id)
            if key:
                key_lower = key.lower()
                record['student_key'] = key_lower
                if not record.get('student_id'):
                    extracted = extract_student_id_from_key(key_lower)
                    if extracted:
                        record['student_id'] = extracted

    # Ensure draw information structure exists
    draw_info = session_info.get('draw_info')
    if not isinstance(draw_info, dict):
        draw_info = {}
        session_info['draw_info'] = draw_info
    draw_info.setdefault('winner', None)
    draw_info.setdefault('winner_timestamp', None)
    draw_info.setdefault('selected_by', None)
    draw_info.setdefault('method', None)
    draw_info.setdefault('finalized', False)
    draw_info.setdefault('finalized_at', None)
    draw_info.setdefault('finalized_by', None)
    draw_info.setdefault('history', [])
    draw_info.setdefault('override', False)
    draw_info.setdefault('tickets_at_selection', None)
    draw_info.setdefault('probability_at_selection', None)
    draw_info.setdefault('eligible_pool_size', None)
    session_info['draw_info'] = draw_info

    if 'is_discarded' not in session_info:
        session_info['is_discarded'] = False
    if 'discard_metadata' not in session_info or not isinstance(session_info['discard_metadata'], dict):
        session_info['discard_metadata'] = {}


def _isoformat_timestamp(value):
    if not value:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        try:
            return datetime.fromisoformat(str(value)).isoformat()
        except Exception:
            return str(value)


def _extract_faculty_names(dedupe_key):
    if not dedupe_key:
        return '', ''
    key = dedupe_key
    if key.startswith('faculty_'):
        key = key[len('faculty_'):]
    preferred = key
    last = ''
    if '_' in key:
        preferred, last = key.rsplit('_', 1)
    return normalize_name(preferred).title(), normalize_name(last).title()


def hydrate_session_from_db(session_id, *, persist=True, session_model=None):
    """Rebuild session metadata from relational tables when legacy JSON is missing."""
    if not session_id:
        return None

    session_info = session_data.get(session_id)
    if session_info is None:
        session_info = {}
        session_data[session_id] = session_info

    try:
        db_sess = session_model or db_session.query(SessionModel).filter_by(id=session_id).first()
    except Exception as exc:
        db_session.rollback()
        print(f"Error fetching session {session_id} for hydration: {exc}")
        return None

    if not db_sess:
        session_data.pop(session_id, None)
        return None

    session_info.setdefault('session_name', db_sess.session_name)
    session_info.setdefault('owner', db_sess.created_by)
    session_info.setdefault('created_at', _isoformat_timestamp(db_sess.created_at) or datetime.now().isoformat())
    session_info.setdefault('is_public', bool(db_sess.is_public))
    session_info.setdefault('draw_info', session_info.get('draw_info') or {})
    session_info['is_discarded'] = bool(db_sess.status == 'discarded')
    discard_metadata = session_info.get('discard_metadata') or {}
    if db_sess.discarded_at and not discard_metadata.get('discarded_at'):
        discard_metadata['discarded_at'] = _isoformat_timestamp(db_sess.discarded_at)
    if db_sess.discarded_by and not discard_metadata.get('discarded_by'):
        discard_metadata['discarded_by'] = db_sess.discarded_by
    session_info['discard_metadata'] = discard_metadata
    if (
        db_sess.faculty_pick_display_name
        or db_sess.faculty_pick_preferred_name
        or db_sess.faculty_pick_last_name
    ):
        session_info['faculty_pick'] = {
            'preferred_name': db_sess.faculty_pick_preferred_name,
            'last_name': db_sess.faculty_pick_last_name,
            'display_name': db_sess.faculty_pick_display_name,
            'recorded_at': _isoformat_timestamp(db_sess.faculty_pick_recorded_at),
            'recorded_by': db_sess.faculty_pick_recorded_by,
        }
    else:
        session_info.setdefault('faculty_pick', None)

    try:
        records = (
            db_session.query(SessionRecord)
            .filter(SessionRecord.session_id == session_id)
            .order_by(SessionRecord.recorded_at.asc(), SessionRecord.id.asc())
            .all()
        )
    except Exception as exc:
        db_session.rollback()
        print(f"Error fetching session records for {session_id}: {exc}")
        records = []

    student_ids = {record.student_id for record in records if record.student_id}
    students_map = {}
    if student_ids:
        try:
            students = db_session.query(Student).filter(Student.id.in_(student_ids)).all()
            students_map = {student.id: student for student in students}
        except Exception as exc:
            db_session.rollback()
            print(f"Error loading students for session {session_id}: {exc}")

    clean_records = []
    red_records = []
    faculty_records = []
    scan_history = []
    dirty_count = 0

    for record in records:
        timestamp = _isoformat_timestamp(record.recorded_at)
        base_entry = {
            'timestamp': timestamp,
            'recorded_by': record.recorded_by,
            'category': record.category,
            'is_manual_entry': bool(record.is_manual_entry),
        }

        if record.category == 'dirty':
            dirty_count += 1
            entry = base_entry.copy()
            entry['display_name'] = f"Dirty Plate #{dirty_count}"
            scan_history.append(entry)
            continue

        if record.category == 'faculty':
            preferred_name, last_name = _extract_faculty_names(record.dedupe_key)
            faculty_entry = {
                **base_entry,
                'preferred_name': preferred_name,
                'first_name': preferred_name,
                'last_name': last_name,
                'grade': '',
                'advisor': '',
                'house': '',
                'clan': '',
                'student_id': '',
                'student_key': None,
            }
            faculty_records.append(faculty_entry)
            scan_history.append(faculty_entry.copy())
            continue

        student_obj = students_map.get(record.student_id)
        preferred_name = normalize_name(student_obj.preferred_name) if student_obj else ''
        last_name = normalize_name(student_obj.last_name) if student_obj else ''
        student_identifier = normalize_name(student_obj.student_identifier) if student_obj else ''
        advisor = normalize_name(student_obj.advisor) if student_obj else ''
        grade = normalize_name(record.grade or (student_obj.grade if student_obj else ''))
        house = normalize_name(record.house or (student_obj.house if student_obj else ''))
        clan = normalize_name(student_obj.clan) if student_obj else ''

        if (not preferred_name or not last_name) and record.dedupe_key:
            key_preferred, key_last = split_student_key(record.dedupe_key)
            if not preferred_name:
                preferred_name = normalize_name(key_preferred)
            if not last_name:
                last_name = normalize_name(key_last)

        student_key = make_student_key(preferred_name, last_name, student_identifier)
        entry = {
            **base_entry,
            'preferred_name': preferred_name,
            'first_name': preferred_name,
            'last_name': last_name,
            'grade': grade,
            'advisor': advisor,
            'house': house,
            'clan': clan,
            'student_id': student_identifier,
            'student_key': student_key.lower() if student_key else None,
        }

        if record.category == 'clean':
            clean_records.append(entry)
        else:
            red_records.append(entry)
        scan_history.append(entry.copy())

    scan_history.sort(key=lambda item: item.get('timestamp') or '', reverse=True)

    session_info['clean_records'] = clean_records
    session_info['red_records'] = red_records
    session_info['faculty_clean_records'] = faculty_records
    session_info['scan_history'] = scan_history
    session_info['dirty_count'] = dirty_count
    session_info['_hydrated_from_db'] = True

    ensure_session_structure(session_info)

    if persist:
        save_session_data()

    return session_info


def get_session_entry(session_id, *, hydrate=True):
    """Fetch session JSON entry, hydrating from the database when required."""
    if not session_id:
        return None

    info = session_data.get(session_id)
    if info is None and hydrate:
        return hydrate_session_from_db(session_id)

    if info is not None:
        ensure_session_structure(info)
    return info


def backfill_session_data_from_db():
    """Ensure all database sessions have matching JSON cache entries."""
    try:
        db_sessions = db_session.query(SessionModel).all()
    except Exception as exc:
        db_session.rollback()
        print(f"Error loading sessions for backfill: {exc}")
        return

    hydrated = False
    for db_sess in db_sessions:
        if db_sess.id not in session_data:
            info = hydrate_session_from_db(db_sess.id, persist=False, session_model=db_sess)
            if info:
                hydrated = True

    if hydrated:
        save_session_data()


def get_dirty_count(session_info):
    """Helper to safely retrieve dirty count from a session."""
    ensure_session_structure(session_info)
    return session_info.get('dirty_count', 0)


def normalize_loaded_sessions():
    for _session_info in session_data.values():
        ensure_session_structure(_session_info)


def reset_storage_for_testing():
    """Reset all persistent stores to defaults to keep pytest runs isolated."""
    global session_data, delete_requests, global_csv_data, global_teacher_data, student_lookup

    session_data = {}
    delete_requests = []
    global_csv_data = {}
    global_teacher_data = {}
    student_lookup = {}

    reset_user_store()
    update_student_lookup()
    try:
        db_session.query(SessionDeleteRequest).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    _refresh_delete_requests_cache()


print("Initializing persistent storage (database-backed)...")
# Initialize empty in-memory caches
session_data = {}
delete_requests = []
global_csv_data = {}
global_teacher_data = {}

# Build student lookup from database
update_student_lookup()

# Load delete requests cache
_refresh_delete_requests_cache()

# Ensure default superadmin exists
default_user = ensure_default_superadmin()

# Backfill session data from database
#backfill_session_data_from_db()
normalize_loaded_sessions()

print(f"Initialization complete. Session count: {len(session_data)}, Users: {len(list_all_users())}")


__all__ = [
    'backfill_session_data_from_db',
    'delete_requests',
    'ensure_session_structure',
    'get_session_entry',
    'get_dirty_count',
    'get_student_lookup_for_school',
    'global_csv_data',
    'global_teacher_data',
    'hydrate_session_from_db',
    'normalize_loaded_sessions',
    'reset_storage_for_testing',
    'save_all_data',
    'save_delete_requests',
    'save_global_csv_data',
    'save_global_teacher_data',
    'save_session_data',
    'session_data',
    'student_lookup',
    'sync_students_table_from_csv_rows',
    'sync_teacher_table_from_list',
    'update_student_lookup',
]
