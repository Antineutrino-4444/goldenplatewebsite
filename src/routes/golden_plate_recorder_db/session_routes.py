import csv
import io
import re
import uuid
from datetime import datetime

from flask import Response, jsonify, request, session
from sqlalchemy import func

from . import recorder_bp
from .db import Session as SessionModel, SessionDrawEvent, SessionRecord, Student, _now_utc, db_session
from .domain import serialize_draw_info
from .security import get_current_user, is_guest, require_admin, require_auth, require_auth_or_guest
from .storage import (
    delete_requests,
    ensure_session_structure,
    get_dirty_count,
    save_delete_requests,
    save_session_data,
    session_data,
    student_lookup,
    update_student_lookup,
)
from .utils import (
    extract_student_id_from_key,
    format_display_name,
    make_student_key,
    normalize_name,
    split_student_key,
)


def _delete_session_with_dependencies(db_sess):
    """Remove a session and any dependent draw and record rows."""
    session_id = db_sess.id
    session_name = db_sess.session_name

    # Explicitly delete dependents because SQLite foreign key cascades
    # are easy to disable accidentally and we do not want orphan rows.
    db_session.query(SessionRecord).filter_by(session_id=session_id).delete(synchronize_session=False)
    db_session.query(SessionDrawEvent).filter_by(session_id=session_id).delete(synchronize_session=False)

    db_session.delete(db_sess)
    db_session.commit()

    if session_id in session_data:
        del session_data[session_id]
        save_session_data()

    if session.get('session_id') == session_id:
        session.pop('session_id', None)

    return session_name


@recorder_bp.route('/session/request-delete', methods=['POST'])
def request_delete_session():
    """Submit a delete request for a session."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json() or {}
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({'error': 'Session ID is required'}), 400

    db_sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    current_user = get_current_user()

    if current_user['role'] in ['admin', 'superadmin']:
        session_name = _delete_session_with_dependencies(db_sess)

        return jsonify({
            'status': 'success',
            'message': f'Session "{session_name}" deleted successfully',
            'deleted_session_id': session_id
        }), 200

    existing = next((req for req in delete_requests
                     if req['session_id'] == session_id and req['status'] == 'pending'), None)
    if existing:
        return jsonify({'error': 'Delete request already submitted for this session'}), 400

    # Use cached counts from session table
    clean_count = db_sess.clean_number or 0
    dirty_count = db_sess.dirty_number or 0
    red_count = db_sess.red_number or 0
    faculty_clean_count = db_sess.faculty_number or 0
    total_records = db_sess.total_records or 0

    request_obj = {
        'id': str(uuid.uuid4()),
        'session_id': session_id,
        'session_name': db_sess.session_name,
        'requester': session['user_id'],
        'requester_name': current_user['name'],
        'requested_at': datetime.now().isoformat(),
        'status': 'pending',
        'total_records': total_records,
        'clean_records': clean_count,
        'dirty_records': dirty_count,
        'red_records': red_count,
        'faculty_clean_records': faculty_clean_count,
    }

    delete_requests.append(request_obj)
    save_delete_requests()

    return jsonify({
        'status': 'success',
        'message': f'Delete request submitted for "{db_sess.session_name}"',
        'request': request_obj
    }), 200


@recorder_bp.route('/session/create', methods=['POST'])
def create_session():
    """Create a new session."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    custom_name = data.get('session_name', '').strip()
    is_public = data.get('is_public', True)

    session_id = str(uuid.uuid4())

    if custom_name:
        existing = db_session.query(SessionModel).filter_by(session_name=custom_name).first()
        if existing:
            return jsonify({'error': 'Session name already exists'}), 400
        session_name = custom_name
    else:
        now = datetime.now()
        base_name = f"Golden_Plate_{now.strftime('%B_%d_%Y')}"
        session_name = base_name
        counter = 1
        while db_session.query(SessionModel).filter_by(session_name=session_name).first():
            session_name = f"{base_name}_{counter}"
            counter += 1

    new_session = SessionModel(
        id=session_id,
        session_name=session_name,
        created_by=session['user_id'],
        is_public=1 if is_public else 0,
        status='active',
        clean_number=0,
        dirty_number=0,
        red_number=0,
        faculty_number=0,
        total_records=0,
        total_clean=0,
        total_dirty=0
    )

    db_session.add(new_session)
    db_session.commit()

    # Keep backward compatibility with JSON storage for draw_info and other features
    session_data[session_id] = {
        'session_name': session_name,
        'owner': session['user_id'],
        'created_at': new_session.created_at.isoformat(),
        'clean_records': [],
        'dirty_count': 0,
        'red_records': [],
        'faculty_clean_records': [],
        'scan_history': [],
        'is_public': is_public,
        'draw_info': {
            'winner': None,
            'winner_timestamp': None,
            'selected_by': None,
            'method': None,
            'finalized': False,
            'finalized_at': None,
            'finalized_by': None,
            'history': [],
            'override': False,
            'tickets_at_selection': None,
            'probability_at_selection': None,
            'eligible_pool_size': None
        },
        'is_discarded': False,
        'discard_metadata': {}
    }

    save_session_data()
    session['session_id'] = session_id

    return jsonify({
        'session_id': session_id,
        'session_name': session_name,
        'owner': session['user_id']
    }), 200


@recorder_bp.route('/session/list', methods=['GET'])
def list_sessions():
    """List sessions. Guests only see public ones."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    query = db_session.query(SessionModel)
    
    # Filter out non-public sessions for guests
    if is_guest():
        query = query.filter(SessionModel.is_public == 1)
    
    db_sessions = query.order_by(SessionModel.created_at.desc()).all()

    user_sessions = []
    for db_sess in db_sessions:
        # Use cached counts from session table
        clean_count = db_sess.clean_number or 0
        dirty_count = db_sess.dirty_number or 0
        red_count = db_sess.red_number or 0
        faculty_clean_count = db_sess.faculty_number or 0

        total_records = clean_count + dirty_count + red_count + faculty_clean_count
        combined_clean_count = clean_count + faculty_clean_count
        total_for_ratio = total_records

        clean_percentage = (combined_clean_count / total_for_ratio * 100) if total_for_ratio > 0 else 0
        dirty_percentage = ((dirty_count + red_count) / total_for_ratio * 100) if total_for_ratio > 0 else 0

        # Get draw_info from JSON storage for backward compatibility
        json_data = session_data.get(db_sess.id, {})
        draw_info = serialize_draw_info(json_data.get('draw_info', {}))
        
        pending = any(req['session_id'] == db_sess.id and req['status'] == 'pending'
                       for req in delete_requests)
        
        user_sessions.append({
            'session_id': db_sess.id,
            'session_name': db_sess.session_name,
            'owner': db_sess.created_by,
            'total_records': total_records,
            'clean_count': clean_count,
            'dirty_count': dirty_count + red_count,
            'faculty_clean_count': faculty_clean_count,
            'clean_percentage': round(clean_percentage, 1),
            'dirty_percentage': round(dirty_percentage, 1),
            'is_public': bool(db_sess.is_public),
            'delete_requested': pending,
            'is_discarded': db_sess.status == 'discarded',
            'draw_info': draw_info
        })

    return jsonify({
        'sessions': user_sessions,
        'has_global_csv': db_session.query(Student.id).first() is not None
    }), 200


@recorder_bp.route('/session/switch/<session_id>', methods=['POST'])
def switch_session(session_id):
    """Switch to a different session. Guests may only access public sessions."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    db_sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    if is_guest() and not db_sess.is_public:
        return jsonify({'error': 'Access denied'}), 403

    session['session_id'] = session_id

    return jsonify({
        'session_id': session_id,
        'session_name': db_sess.session_name
    }), 200


@recorder_bp.route('/session/delete/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session directly."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    db_sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    current_user = get_current_user()

    if current_user['role'] == 'user' and db_sess.created_by != session['user_id']:
        return jsonify({'error': 'You can only delete sessions that you created'}), 403

    session_name = _delete_session_with_dependencies(db_sess)

    return jsonify({
        'status': 'success',
        'message': f'Session "{session_name}" deleted successfully',
        'deleted_session_id': session_id
    }), 200


@recorder_bp.route('/session/status', methods=['GET'])
def get_session_status():
    """Get current session status with percentage calculations."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    db_sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    if is_guest() and not db_sess.is_public:
        return jsonify({'error': 'Access denied'}), 403

    # Use cached counts from session table
    clean_count = db_sess.clean_number or 0
    dirty_count = db_sess.dirty_number or 0
    red_count = db_sess.red_number or 0
    faculty_clean_count = db_sess.faculty_number or 0
    
    combined_dirty_count = dirty_count + red_count
    combined_clean_count = clean_count + faculty_clean_count
    total_recorded = combined_clean_count + combined_dirty_count

    clean_percentage = (combined_clean_count / total_recorded * 100) if total_recorded > 0 else 0
    dirty_percentage = (combined_dirty_count / total_recorded * 100) if total_recorded > 0 else 0

    # Get scan history count and draw_info from JSON storage for backward compatibility
    json_data = session_data.get(session_id, {})
    ensure_session_structure(json_data)
    scan_history_count = len(json_data.get('scan_history', []))
    draw_info = serialize_draw_info(json_data.get('draw_info', {}))

    return jsonify({
        'session_id': session_id,
        'session_name': db_sess.session_name,
        'clean_count': clean_count,
        'dirty_count': dirty_count,
        'red_count': red_count,
        'combined_dirty_count': combined_dirty_count,
        'faculty_clean_count': faculty_clean_count,
        'total_recorded': total_recorded,
        'clean_percentage': round(clean_percentage, 1),
        'dirty_percentage': round(dirty_percentage, 1),
        'scan_history_count': scan_history_count,
        'is_discarded': db_sess.status == 'discarded',
        'draw_info': draw_info
    }), 200


@recorder_bp.route('/session/history', methods=['GET'])
def get_session_history():
    """Get scan history for current session."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400

    session_id = session['session_id']
    data = session_data[session_id]
    if is_guest() and not data.get('is_public', True):
        return jsonify({'error': 'Access denied'}), 403

    return jsonify({
        'scan_history': data['scan_history']
    }), 200


@recorder_bp.route('/session/scan-history', methods=['GET'])
def get_scan_history():
    """Get scan history for current session (formatted) from session_records table."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400

    session_id = session['session_id']
    
    # Verify session exists
    db_sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404
    
    # Check guest access
    if is_guest() and not db_sess.is_public:
        return jsonify({'error': 'Access denied'}), 403

    # Get all records from session_records table
    records = (
        db_session.query(SessionRecord, Student)
        .outerjoin(Student, SessionRecord.student_id == Student.id)
        .filter(SessionRecord.session_id == session_id)
        .order_by(SessionRecord.recorded_at.desc())
        .all()
    )

    formatted_history = []
    dirty_count = 0
    
    for session_record, student in records:
        category = session_record.category.lower()
        
        # Build the name - prioritize names stored in session_record
        name = ''
        if session_record.preferred_name or session_record.last_name:
            # Use names directly from session_record (for faculty and manual entries)
            preferred = (session_record.preferred_name or '').strip()
            last = (session_record.last_name or '').strip()
            name = f"{preferred} {last}".strip()
        elif student:
            # Fall back to student record if available
            preferred = (student.preferred_name or '').strip()
            last = (student.last_name or '').strip()
            name = f"{preferred} {last}".strip()
        
        # Handle special categories
        if category == 'dirty':
            dirty_count += 1
            name = f'Dirty Plate #{dirty_count}'
        elif not name and category == 'faculty':
            name = 'Faculty Clean Plate'
        elif not name:
            name = 'Unknown'

        formatted_history.append({
            'timestamp': session_record.recorded_at.isoformat() if session_record.recorded_at else '',
            'name': name,
            'category': category.upper(),
            'is_manual_entry': bool(session_record.is_manual_entry)
        })

    return jsonify({
        'scan_history': formatted_history
    }), 200


@recorder_bp.route('/record/<category>', methods=['POST'])
def record_student(category):
    """Record a student in a category."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400

    if category not in ['clean', 'dirty', 'red', 'faculty']:
        return jsonify({'error': 'Invalid category'}), 400

    data = request.get_json(silent=True) or {}
    input_value = str(data.get('input_value', '') or '').strip()
    provided_student_id = normalize_name(data.get('student_id'))
    provided_key_raw = str(data.get('student_key') or '').strip()
    provided_key = provided_key_raw.lower() if provided_key_raw else ''
    provided_preferred = normalize_name(data.get('preferred_name') or data.get('preferred'))
    provided_last = normalize_name(data.get('last_name') or data.get('last'))

    session_id = session['session_id']
    session_info = session_data[session_id]
    ensure_session_structure(session_info)

    if category == 'dirty':
        new_count = session_info.get('dirty_count', 0) + 1
        session_info['dirty_count'] = new_count
        record = {
            'category': 'dirty',
            'timestamp': datetime.now().isoformat(),
            'recorded_by': session['user_id'],
            'display_name': f"Dirty Plate #{new_count}"
        }
        session_info['scan_history'].append(record)
        save_session_data()
        
        # Save to database
        dedupe_key = f"dirty_{new_count}_{datetime.now().isoformat()}"
        db_record = SessionRecord(
            session_id=session_id,
            category='dirty',
            recorded_by=session['user_id'],
            is_manual_entry=0,
            dedupe_key=dedupe_key
        )
        db_session.add(db_record)
        
        # Update session counts
        db_sess = db_session.query(SessionModel).filter_by(id=session_id).first()
        if db_sess:
            db_sess.dirty_number = (db_sess.dirty_number or 0) + 1
            db_sess.total_dirty = (db_sess.total_dirty or 0) + 1
            db_sess.total_records = (db_sess.total_records or 0) + 1
            db_sess.updated_at = datetime.now()
        
        db_session.commit()
        
        return jsonify({
            'status': 'success',
            'category': 'dirty',
            'dirty_count': new_count
        }), 200

    if category == 'faculty':
        if not input_value:
            return jsonify({'error': 'Faculty name is required'}), 400

        name_parts = input_value.split()
        preferred_name = ""
        last_name = ""
        if len(name_parts) >= 2:
            preferred_name = name_parts[0].strip().title()
            last_name = ' '.join(name_parts[1:]).strip().title()
        elif len(name_parts) == 1:
            preferred_name = name_parts[0].strip().title()
            last_name = ""
        else:
            return jsonify({'error': 'Faculty name is required'}), 400

        duplicate_check = any(
            (record.get('preferred_name') or record.get('first_name', '')).lower() == preferred_name.lower() and
            record.get('last_name', '').lower() == last_name.lower()
            for record in session_info['faculty_clean_records']
        )
        
        # Also check database for duplicates
        if not duplicate_check:
            dedupe_key_to_check = f"faculty_{preferred_name.lower()}_{last_name.lower()}"
            existing_db_record = db_session.query(SessionRecord).filter_by(
                session_id=session_id,
                dedupe_key=dedupe_key_to_check
            ).first()
            if existing_db_record:
                duplicate_check = True

        if duplicate_check:
            return jsonify({
                'error': 'duplicate',
                'message': 'Faculty member already recorded in this session'
            }), 409

        record = {
            'preferred_name': preferred_name,
            'first_name': preferred_name,
            'last_name': last_name,
            'grade': '',
            'advisor': '',
            'house': '',
            'clan': '',
            'category': 'faculty',
            'timestamp': datetime.now().isoformat(),
            'recorded_by': session['user_id'],
            'is_manual_entry': True
        }
        session_info['faculty_clean_records'].append(record)
        session_info['scan_history'].append(record)
        save_session_data()
        
        # Save to database
        dedupe_key = f"faculty_{preferred_name.lower()}_{last_name.lower()}"
        db_record = SessionRecord(
            session_id=session_id,
            category='faculty',
            grade='',
            house='',
            recorded_by=session['user_id'],
            is_manual_entry=1,
            dedupe_key=dedupe_key,
            preferred_name=preferred_name,
            last_name=last_name
        )
        db_session.add(db_record)
        
        # Update session counts
        db_sess = db_session.query(SessionModel).filter_by(id=session_id).first()
        if db_sess:
            db_sess.faculty_number = (db_sess.faculty_number or 0) + 1
            db_sess.total_clean = (db_sess.total_clean or 0) + 1
            db_sess.total_records = (db_sess.total_records or 0) + 1
            db_sess.updated_at = datetime.now()
        
        db_session.commit()
        
        return jsonify({
            'status': 'success',
            'preferred_name': preferred_name,
            'first_name': preferred_name,
            'last_name': last_name,
            'category': 'faculty',
            'is_manual_entry': True,
            'recorded_by': session['user_id']
        }), 200

    has_reference = bool(
        input_value or
        provided_student_id or
        provided_key or
        (provided_preferred and provided_last)
    )
    if not has_reference:
        return jsonify({'error': 'Student ID or Name is required'}), 400

    student_record = None
    lookup_profile = None
    dataset_match = False

    def build_student_record(student_obj):
        if not student_obj:
            return None
        preferred_val = str(student_obj.preferred_name or '').strip()
        last_val = str(student_obj.last_name or '').strip()
        return {
            'Preferred': preferred_val,
            'Last': last_val,
            'Grade': str(student_obj.grade or '').strip(),
            'Advisor': str(student_obj.advisor or '').strip(),
            'House': str(student_obj.house or '').strip(),
            'Clan': str(student_obj.clan or '').strip(),
            'Student ID': str(student_obj.student_identifier or '').strip()
        }

    candidate_ids = []
    if provided_student_id:
        candidate_ids.append(provided_student_id)
    key_id = extract_student_id_from_key(provided_key) if provided_key else ''
    if key_id:
        candidate_ids.append(key_id)
    if input_value.isdigit():
        candidate_ids.append(input_value)
    else:
        id_match = re.search(r'\b(\d{3,})\b', input_value)
        if id_match:
            candidate_ids.append(id_match.group(1))

    normalized_ids = []
    for candidate_id in candidate_ids:
        norm_id = normalize_name(candidate_id)
        if norm_id and norm_id not in normalized_ids:
            normalized_ids.append(norm_id)

    student_obj = None
    if normalized_ids:
        student_obj = (
            db_session.query(Student)
            .filter(Student.student_identifier.in_(normalized_ids))
            .first()
        )
        if student_obj:
            dataset_match = True

    cleaned_input = input_value
    if cleaned_input:
        cleaned_input = re.sub(r'\([^)]*\)', '', cleaned_input).strip()

    candidate_preferred = provided_preferred
    candidate_last = provided_last

    if (not candidate_preferred or not candidate_last) and provided_key and not provided_key.startswith('id:'):
        key_preferred, key_last = split_student_key(provided_key)
        if key_preferred and not candidate_preferred:
            candidate_preferred = key_preferred
        if key_last and not candidate_last:
            candidate_last = key_last

    if not candidate_preferred or not candidate_last:
        name_parts = cleaned_input.split()
        if len(name_parts) >= 2:
            candidate_preferred = candidate_preferred or name_parts[0]
            candidate_last = candidate_last or ' '.join(name_parts[1:])
        elif len(name_parts) == 1:
            candidate_preferred = candidate_preferred or name_parts[0]
            candidate_last = candidate_last or ''

    if not student_obj and candidate_preferred and candidate_last:
        student_obj = (
            db_session.query(Student)
            .filter(func.lower(Student.preferred_name) == candidate_preferred.lower())
            .filter(func.lower(Student.last_name) == candidate_last.lower())
            .first()
        )
        if student_obj:
            dataset_match = True

    student_record = build_student_record(student_obj)

    if not student_record and provided_key and provided_key in student_lookup:
        lookup_profile = student_lookup.get(provided_key)
        if lookup_profile:
            dataset_match = True

    preferred_name = ''
    last_name = ''
    grade = ''
    advisor = ''
    house = ''
    clan = ''
    student_id = ''

    if student_record:
        preferred_name = str(student_record.get('Preferred', '') or '').strip()
        last_name = str(student_record.get('Last', '') or '').strip()
        grade = str(student_record.get('Grade', '') or '').strip()
        advisor = str(student_record.get('Advisor', '') or '').strip()
        house = str(student_record.get('House', '') or '').strip()
        clan = str(student_record.get('Clan', '') or '').strip()
        student_id = str(student_record.get('Student ID', '') or '').strip()
    elif lookup_profile:
        preferred_name = normalize_name(lookup_profile.get('preferred_name'))
        last_name = normalize_name(lookup_profile.get('last_name'))
        grade = normalize_name(lookup_profile.get('grade'))
        advisor = normalize_name(lookup_profile.get('advisor'))
        house = normalize_name(lookup_profile.get('house'))
        clan = normalize_name(lookup_profile.get('clan'))
        student_id = normalize_name(lookup_profile.get('student_id'))
    else:
        preferred_name = normalize_name(candidate_preferred or (cleaned_input.split()[0] if cleaned_input else input_value))
        if cleaned_input:
            parts = cleaned_input.split()
            if len(parts) >= 2:
                candidate_last = candidate_last or ' '.join(parts[1:])
        last_name = normalize_name(candidate_last)

    if not preferred_name and provided_preferred:
        preferred_name = provided_preferred
    if not last_name and provided_last:
        last_name = provided_last
    if not student_id and provided_student_id:
        student_id = provided_student_id
    if not student_id and provided_key:
        extracted_id = extract_student_id_from_key(provided_key)
        if extracted_id:
            student_id = extracted_id
    if not student_id and normalized_ids:
        student_id = normalized_ids[0]

    preferred_name = preferred_name or ''
    last_name = last_name or ''
    grade = grade or ''
    advisor = advisor or ''
    house = house or ''
    clan = clan or ''
    student_id = student_id or ''

    student_key = make_student_key(preferred_name, last_name, student_id) or provided_key or None
    if student_key:
        student_key = student_key.lower()

    is_manual_entry = not dataset_match

    student_records = session_info['clean_records'] + session_info['red_records']

    def normalize_field(value):
        return str(value or '').strip().lower()

    student_key = student_key or ''

    target_student_id = normalize_field(student_id)
    target_preferred = normalize_field(preferred_name)
    target_last = normalize_field(last_name)
    target_grade = normalize_field(grade)
    target_advisor = normalize_field(advisor)
    target_house = normalize_field(house)
    target_clan = normalize_field(clan)
    target_key = normalize_field(student_key)

    def is_duplicate(existing_record):
        existing_student_id = normalize_field(existing_record.get('student_id'))

        if target_student_id and existing_student_id:
            return existing_student_id == target_student_id

        if target_student_id and not existing_student_id:
            return False

        if not target_student_id and existing_student_id:
            return False

        existing_key = normalize_field(existing_record.get('student_key'))
        if target_key and existing_key:
            return existing_key == target_key

        existing_preferred = normalize_field(existing_record.get('preferred_name') or existing_record.get('first_name'))
        existing_last = normalize_field(existing_record.get('last_name'))
        existing_grade = normalize_field(existing_record.get('grade'))
        existing_advisor = normalize_field(existing_record.get('advisor'))
        existing_house = normalize_field(existing_record.get('house'))
        existing_clan = normalize_field(existing_record.get('clan'))

        return (
            existing_preferred == target_preferred and
            existing_last == target_last and
            existing_grade == target_grade and
            existing_advisor == target_advisor and
            existing_house == target_house and
            existing_clan == target_clan
        )

    duplicate_check = any(
        is_duplicate(record)
        for record in student_records
    )
    
    # Also check database for duplicates
    if not duplicate_check:
        dedupe_key_to_check = student_key or f"{preferred_name.lower()}_{last_name.lower()}_{grade}_{house}"
        existing_db_record = db_session.query(SessionRecord).filter_by(
            session_id=session_id,
            dedupe_key=dedupe_key_to_check
        ).first()
        if existing_db_record:
            duplicate_check = True

    if duplicate_check:
        existing_category = None
        for cat in ['clean', 'red']:
            if any(
                is_duplicate(record)
                for record in session_info[f'{cat}_records']
            ):
                existing_category = cat
                break
        
        # If not found in JSON, check database
        if not existing_category:
            dedupe_key_to_check = student_key or f"{preferred_name.lower()}_{last_name.lower()}_{grade}_{house}"
            db_record = db_session.query(SessionRecord).filter_by(
                session_id=session_id,
                dedupe_key=dedupe_key_to_check
            ).first()
            if db_record:
                existing_category = db_record.category

        return jsonify({
            'error': 'duplicate',
            'message': f'Student already recorded as {existing_category.upper() if existing_category else "UNKNOWN"} in this session'
        }), 409

    record = {
        'preferred_name': preferred_name,
        'first_name': preferred_name,
        'last_name': last_name,
        'grade': grade,
        'advisor': advisor,
        'house': house,
        'clan': clan,
        'student_id': student_id,
        'student_key': student_key,
        'category': category,
        'timestamp': datetime.now().isoformat(),
        'recorded_by': session['user_id'],
        'is_manual_entry': is_manual_entry
    }

    session_info[f'{category}_records'].append(record)
    session_info['scan_history'].append(record)
    save_session_data()

    # Save to database
    # Look up or create student in database
    db_student = None
    lookup_refresh_needed = False
    if student_id:
        db_student = db_session.query(Student).filter_by(student_identifier=student_id).first()
        if not db_student:
            db_student = Student(
                student_identifier=student_id,
                preferred_name=preferred_name,
                last_name=last_name,
                grade=grade,
                advisor=advisor,
                house=house,
                clan=clan
            )
            db_session.add(db_student)
            db_session.flush()  # Get the ID
            lookup_refresh_needed = True
    
    # Create dedupe key from student info
    dedupe_key = student_key or f"{preferred_name.lower()}_{last_name.lower()}_{grade}_{house}"
    
    db_record = SessionRecord(
        session_id=session_id,
        student_id=db_student.id if db_student else None,
        category=category,
        grade=grade,
        house=house,
        recorded_by=session['user_id'],
        is_manual_entry=1 if is_manual_entry else 0,
        dedupe_key=dedupe_key,
        preferred_name=preferred_name,
        last_name=last_name
    )
    db_session.add(db_record)
    db_session.flush()  # Flush to get db_record.id
    
    # Update session counts
    db_sess = db_session.query(SessionModel).filter_by(id=session_id).first()
    if db_sess:
        if category == 'clean':
            db_sess.clean_number = (db_sess.clean_number or 0) + 1
            db_sess.total_clean = (db_sess.total_clean or 0) + 1
            db_sess.total_records = (db_sess.total_records or 0) + 1
        elif category == 'red':
            db_sess.red_number = (db_sess.red_number or 0) + 1
            db_sess.total_dirty = (db_sess.total_dirty or 0) + 1
            db_sess.total_records = (db_sess.total_records or 0) + 1
        db_sess.updated_at = datetime.now()
    
    # Handle ticket events and draft_pool updates
    if db_student and db_student.id:
        from .draw_db import update_tickets_for_record
        update_tickets_for_record(
            session_id=session_id,
            student_id=db_student.id,
            category=category,
            session_record_id=db_record.id,
            user_id=session['user_id']
        )
    
    db_session.commit()
    if lookup_refresh_needed:
        update_student_lookup()

    return jsonify({
        'status': 'success',
        'preferred_name': preferred_name,
        'first_name': preferred_name,
        'last_name': last_name,
        'grade': grade,
        'advisor': advisor,
        'house': house,
        'clan': clan,
        'student_id': student_id,
        'student_key': student_key,
        'category': category,
        'is_manual_entry': is_manual_entry,
        'recorded_by': session['user_id']
    }), 200


@recorder_bp.route('/export/csv', methods=['GET'])
def export_csv():
    """Export session records as CSV."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400

    session_id = session['session_id']
    data = session_data[session_id]

    ensure_session_structure(data)

    output = io.StringIO()
    output.write("CLEAN,DIRTY,RED,FACULTY CLEAN\n")

    def format_name(record):
        preferred = (record.get('preferred_name') or record.get('first_name', '') or '').strip()
        last = (record.get('last_name') or '').strip()
        full_name = f"{preferred} {last}".strip()
        return full_name

    clean_names = [format_name(record) for record in data['clean_records']]
    red_names = [format_name(record) for record in data['red_records']]
    faculty_names = [format_name(record) for record in data.get('faculty_clean_records', [])]
    dirty_count = get_dirty_count(data)

    max_records = max(
        len(clean_names),
        len(red_names),
        len(faculty_names),
        1 if dirty_count > 0 else 0
    )

    for i in range(max_records):
        clean_name = clean_names[i] if i < len(clean_names) else ""
        red_name = red_names[i] if i < len(red_names) else ""
        faculty_name = faculty_names[i] if i < len(faculty_names) else ""
        dirty_value = str(dirty_count) if i == 0 and dirty_count > 0 else ""

        output.write(f'"{clean_name}","{dirty_value}","{red_name}","{faculty_name}"\n')

    csv_content = output.getvalue()
    output.close()

    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{data["session_name"]}_records.csv"'}
    )


@recorder_bp.route('/export/csv/detailed', methods=['GET'])
def export_detailed_csv():
    """Export detailed session records without student IDs."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400

    session_id = session['session_id']
    data = session_data[session_id]

    ensure_session_structure(data)

    detailed_records = []
    for category in ['clean', 'red']:
        for record in data.get(f'{category}_records', []):
            preferred = (record.get('preferred_name') or record.get('first_name', '') or '').strip()
            last = (record.get('last_name') or '').strip()
            detailed_records.append({
                'Category': category.upper(),
                'Last': last,
                'Preferred': preferred,
                'Grade': record.get('grade', ''),
                'Advisor': record.get('advisor', ''),
                'House': record.get('house', ''),
                'Clan': record.get('clan', ''),
                'Recorded At': record.get('timestamp', ''),
                'Recorded By': record.get('recorded_by', ''),
                'Manual Entry': 'Yes' if record.get('is_manual_entry') else 'No'
            })

    dirty_count = get_dirty_count(data)
    if dirty_count > 0:
        detailed_records.append({
            'Category': 'DIRTY',
            'Last': '',
            'Preferred': f'Count: {dirty_count}',
            'Grade': '',
            'Advisor': '',
            'House': '',
            'Clan': '',
            'Recorded At': '',
            'Recorded By': '',
            'Manual Entry': ''
        })

    detailed_records.sort(key=lambda x: x['Recorded At'] or '', reverse=True)

    output = io.StringIO()
    writer = csv.writer(output)
    header = ['Category', 'Last', 'Preferred', 'Grade', 'Advisor', 'House', 'Clan', 'Recorded At', 'Recorded By', 'Manual Entry']
    writer.writerow(header)
    for record in detailed_records:
        writer.writerow([record[column] for column in header])

    csv_content = output.getvalue()
    output.close()

    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{data["session_name"]}_detailed_records.csv"'}
    )


__all__ = []
