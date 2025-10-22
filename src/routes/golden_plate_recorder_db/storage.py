import json
import os
import uuid
from datetime import datetime

from .db import KeyValueStore, Student, Teacher, db_session
from .users import (
    DEFAULT_SUPERADMIN,
    ensure_default_superadmin,
    list_all_users,
    migrate_legacy_invite_codes,
    migrate_legacy_users,
    reset_user_store,
)
from .utils import extract_student_id_from_key, make_student_key, normalize_name

# Persistent storage keys used in the key-value store
SESSIONS_FILE = 'sessions'
USERS_FILE = 'users'
DELETE_REQUESTS_FILE = 'delete_requests'
INVITE_CODES_FILE = 'invite_codes'
GLOBAL_CSV_FILE = 'global_csv_data'
TEACHER_LIST_FILE = 'teacher_list'

# Student lookup cache built from the global CSV data for fast eligibility checks
student_lookup = {}

# Global in-memory state hydrated from the persistent store
session_data = {}
delete_requests = []
global_csv_data = {}
global_teacher_data = {}


def load_data_from_file(store_key, default_data):
    """Load JSON data from the database, falling back to a default."""
    try:
        entry = db_session.query(KeyValueStore).filter_by(key=store_key).first()
        if entry:
            try:
                data = json.loads(entry.value)
                if (isinstance(data, (dict, list)) and not data) and default_data:
                    return default_data
                return data
            except json.JSONDecodeError:
                print(f"Corrupted data for key {store_key}, resetting to default")
        serialized = json.dumps(default_data, indent=2)
        if entry:
            entry.value = serialized
        else:
            db_session.add(KeyValueStore(key=store_key, value=serialized))
        db_session.commit()
    except Exception as exc:
        db_session.rollback()
        print(f"Error loading {store_key}: {exc}")
        return default_data
    return default_data


def save_data_to_file(store_key, data):
    """Persist JSON data to the database-backed key-value store."""
    try:
        serialized = json.dumps(data, indent=2)
        entry = db_session.query(KeyValueStore).filter_by(key=store_key).first()
        if entry:
            entry.value = serialized
        else:
            db_session.add(KeyValueStore(key=store_key, value=serialized))
        db_session.commit()
        print(f"Successfully saved data to {store_key}")
        return True
    except Exception as exc:
        db_session.rollback()
        print(f"Error saving {store_key}: {exc}")
        return False


def sync_students_table_from_csv_rows(rows):
    """Persist uploaded student roster into the students table."""
    result = {'processed': 0, 'created': 0, 'updated': 0}
    if not isinstance(rows, list) or not rows:
        return result

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
    existing_students = db_session.query(Student).filter(Student.student_identifier.in_(identifiers)).all()
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
        except Exception:
            db_session.rollback()
            raise

    return result


def sync_teacher_table_from_list(teachers):
    """Persist uploaded teacher roster into the teachers table."""
    result = {'processed': 0, 'created': 0, 'updated': 0}
    if not isinstance(teachers, list) or not teachers:
        return result

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
    existing_teachers = db_session.query(Teacher).filter(Teacher.name.in_(names)).all()
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
    global student_lookup
    student_lookup = {}
    data = []
    if isinstance(global_csv_data, dict):
        data = global_csv_data.get('data') or []
    if not isinstance(data, list):
        data = []
    for row in data:
        preferred = normalize_name(row.get('Preferred', ''))
        last = normalize_name(row.get('Last', ''))
        student_id = normalize_name(row.get('Student ID', ''))
        key = make_student_key(preferred, last, student_id)
        if not key:
            continue
        student_lookup[key] = {
            'preferred_name': preferred,
            'last_name': last,
            'grade': normalize_name(row.get('Grade', '')),
            'advisor': normalize_name(row.get('Advisor', '')),
            'house': normalize_name(row.get('House', '')),
            'clan': normalize_name(row.get('Clan', '')),
            'student_id': student_id,
            'key': key
        }


def save_all_data():
    """Save all data to the database-backed store."""
    try:
        save_data_to_file(SESSIONS_FILE, session_data)
        save_data_to_file(DELETE_REQUESTS_FILE, delete_requests)
        save_data_to_file(GLOBAL_CSV_FILE, global_csv_data)
        print("All data saved successfully")
        return True
    except Exception as e:
        print(f"Error saving all data: {e}")
        return False


def save_session_data():
    """Save session data to the database-backed store."""
    return save_data_to_file(SESSIONS_FILE, session_data)


def save_delete_requests():
    """Save delete requests to the database-backed store."""
    return save_data_to_file(DELETE_REQUESTS_FILE, delete_requests)


def save_global_csv_data():
    """Save global CSV data to the database-backed store."""
    result = save_data_to_file(GLOBAL_CSV_FILE, global_csv_data)
    if result:
        update_student_lookup()
    return result


def save_global_teacher_data():
    """Save global teacher data to the database-backed store."""
    return save_data_to_file(TEACHER_LIST_FILE, global_teacher_data)


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

    save_data_to_file(SESSIONS_FILE, session_data)
    save_data_to_file(DELETE_REQUESTS_FILE, delete_requests)
    save_data_to_file(GLOBAL_CSV_FILE, global_csv_data)
    save_data_to_file(TEACHER_LIST_FILE, global_teacher_data)
    reset_user_store()
    update_student_lookup()


print("Initializing persistent storage (database-backed)...")
session_data = load_data_from_file(SESSIONS_FILE, {})
delete_requests = load_data_from_file(DELETE_REQUESTS_FILE, [])
legacy_invites = load_data_from_file(INVITE_CODES_FILE, {})

global_csv_data = load_data_from_file(GLOBAL_CSV_FILE, {})
update_student_lookup()

global_teacher_data = load_data_from_file(TEACHER_LIST_FILE, {})

legacy_users = load_data_from_file(USERS_FILE, {
    DEFAULT_SUPERADMIN['username']: {
        'password': DEFAULT_SUPERADMIN['password'],
        'role': DEFAULT_SUPERADMIN['role'],
        'name': DEFAULT_SUPERADMIN['display_name'],
        'status': DEFAULT_SUPERADMIN['status'],
    }
})

default_user = ensure_default_superadmin()
migrate_legacy_users(legacy_users)
migrate_legacy_invite_codes(legacy_invites, default_user)

print("Saving initial data to ensure tables are seeded...")
save_data_to_file(SESSIONS_FILE, session_data)
save_data_to_file(DELETE_REQUESTS_FILE, delete_requests)
save_data_to_file(GLOBAL_CSV_FILE, global_csv_data)
save_data_to_file(TEACHER_LIST_FILE, global_teacher_data)

normalize_loaded_sessions()

print(f"Initialization complete. Session count: {len(session_data)}, Users: {len(list_all_users())}")


__all__ = [
    'DELETE_REQUESTS_FILE',
    'GLOBAL_CSV_FILE',
    'INVITE_CODES_FILE',
    'SESSIONS_FILE',
    'TEACHER_LIST_FILE',
    'delete_requests',
    'ensure_session_structure',
    'get_dirty_count',
    'global_csv_data',
    'global_teacher_data',
    'load_data_from_file',
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
