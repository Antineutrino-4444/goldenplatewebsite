from flask import Blueprint, request, jsonify, session, render_template
from datetime import datetime
import uuid
import csv
import io
import os
import json
import random

recorder_bp = Blueprint('recorder', __name__)

# Data storage directory - use absolute path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "persistent_data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Created persistent data directory: {DATA_DIR}")

# File paths for persistent storage
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
DELETE_REQUESTS_FILE = os.path.join(DATA_DIR, "delete_requests.json")
INVITE_CODES_FILE = os.path.join(DATA_DIR, "invite_codes.json")
GLOBAL_CSV_FILE = os.path.join(DATA_DIR, "global_csv_data.json")
TEACHER_LIST_FILE = os.path.join(DATA_DIR, "teacher_list.json")

print(f"Persistent storage directory: {DATA_DIR}")

# Student lookup cache built from the global CSV data for fast eligibility checks
student_lookup = {}

secure_random = random.SystemRandom()

def normalize_name(value):
    return str(value or '').strip()

def make_student_key(preferred_name, last_name):
    preferred_norm = normalize_name(preferred_name).lower()
    last_norm = normalize_name(last_name).lower()
    if not preferred_norm and not last_norm:
        return None
    return f"{preferred_norm}|{last_norm}"

def split_student_key(key):
    if not key:
        return '', ''
    parts = key.split('|', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], ''

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
        key = make_student_key(preferred, last)
        if not key:
            continue
        student_lookup[key] = {
            'preferred_name': preferred,
            'last_name': last,
            'grade': normalize_name(row.get('Grade', '')),
            'advisor': normalize_name(row.get('Advisor', '')),
            'house': normalize_name(row.get('House', '')),
            'clan': normalize_name(row.get('Clan', '')),
            'student_id': normalize_name(row.get('Student ID', ''))
        }

def load_data_from_file(file_path, default_data):
    """Load data from file or return default if file doesn't exist"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                print(f"Successfully loaded data from {file_path}")
                if (isinstance(data, (dict, list)) and not data) and default_data:
                    print(f"{file_path} is empty. Loading default data.")
                    return default_data
                return data
        else:
            print(f"File {file_path} doesn't exist, using default data")
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
    return default_data

def save_data_to_file(file_path, data):
    """Save data to file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write to temporary file first, then rename for atomic operation
        temp_file = file_path + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Atomic rename
        os.rename(temp_file, file_path)
        print(f"Successfully saved data to {file_path}")
        return True
    except Exception as e:
        print(f"Error saving {file_path}: {e}")
        # Clean up temp file if it exists
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        return False

# Initialize persistent storage
print("Initializing persistent storage...")
session_data = load_data_from_file(SESSIONS_FILE, {})
delete_requests = load_data_from_file(DELETE_REQUESTS_FILE, [])
invite_codes_db = load_data_from_file(INVITE_CODES_FILE, {})

# Global CSV storage (admin/super admin can upload, all users can use)
global_csv_data = load_data_from_file(GLOBAL_CSV_FILE, {})
update_student_lookup()

# Global teacher list storage (admin/super admin can upload, all users can use)
global_teacher_data = load_data_from_file(TEACHER_LIST_FILE, {})

# Initialize users database with default super admin if file doesn't exist
default_users = {
    'antineutrino': {
        'password': 'b-decay',
        'role': 'superadmin',
        'name': 'Lead Admin',
        'status': 'active'
    }
}
users_db = load_data_from_file(USERS_FILE, default_users)

# Save initial data to ensure files are created
print("Saving initial data...")
save_data_to_file(SESSIONS_FILE, session_data)
save_data_to_file(USERS_FILE, users_db)
save_data_to_file(DELETE_REQUESTS_FILE, delete_requests)
save_data_to_file(INVITE_CODES_FILE, invite_codes_db)
save_data_to_file(GLOBAL_CSV_FILE, global_csv_data)
save_data_to_file(TEACHER_LIST_FILE, global_teacher_data)

print(f"Initialization complete. Session count: {len(session_data)}, Users: {len(users_db)}")


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


# Normalize any existing sessions loaded from disk
for session_id, _session_info in session_data.items():
    ensure_session_structure(_session_info)

def save_all_data():
    """Save all data to files"""
    try:
        save_data_to_file(SESSIONS_FILE, session_data)
        save_data_to_file(USERS_FILE, users_db)
        save_data_to_file(DELETE_REQUESTS_FILE, delete_requests)
        save_data_to_file(INVITE_CODES_FILE, invite_codes_db)
        save_data_to_file(GLOBAL_CSV_FILE, global_csv_data)
        print("All data saved successfully")
        return True
    except Exception as e:
        print(f"Error saving all data: {e}")
        return False

def save_session_data():
    """Save session data to file"""
    return save_data_to_file(SESSIONS_FILE, session_data)

def save_users_db():
    """Save users database to file"""
    return save_data_to_file(USERS_FILE, users_db)

def save_delete_requests():
    """Save delete requests to file"""
    return save_data_to_file(DELETE_REQUESTS_FILE, delete_requests)

def save_invite_codes_db():
    """Save invite codes database to file"""
    return save_data_to_file(INVITE_CODES_FILE, invite_codes_db)

def save_global_csv_data():
    """Save global CSV data to file"""
    return save_data_to_file(GLOBAL_CSV_FILE, global_csv_data)

def save_global_teacher_data():
    """Save global teacher data to file"""
    return save_data_to_file(TEACHER_LIST_FILE, global_teacher_data)

def format_display_name(profile):
    preferred = normalize_name(profile.get('preferred_name') or profile.get('first_name', ''))
    last = normalize_name(profile.get('last_name'))
    if preferred and last:
        return f"{preferred} {last}"
    return preferred or last

def build_profile_from_record(record):
    preferred = normalize_name(record.get('preferred_name') or record.get('first_name'))
    last = normalize_name(record.get('last_name'))
    profile = {
        'preferred_name': preferred,
        'last_name': last,
        'grade': normalize_name(record.get('grade')),
        'advisor': normalize_name(record.get('advisor')),
        'house': normalize_name(record.get('house')),
        'clan': normalize_name(record.get('clan')),
        'student_id': normalize_name(record.get('student_id'))
    }
    key = make_student_key(preferred, last)
    profile['key'] = key
    if key and key in student_lookup:
        lookup = student_lookup[key]
        for field in ['preferred_name', 'last_name', 'grade', 'advisor', 'house', 'clan', 'student_id']:
            if not profile.get(field):
                profile[field] = lookup.get(field, '')
    profile['display_name'] = format_display_name(profile)
    return profile

def is_student_profile_eligible(profile):
    key = profile.get('key')
    if not key:
        return False
    if student_lookup:
        return key in student_lookup
    return True

def safe_parse_datetime(value):
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except Exception:
            return datetime.min

def compute_ticket_rollups():
    generated_at = datetime.now().isoformat()
    ordered = sorted(
        session_data.items(),
        key=lambda item: (safe_parse_datetime(item[1].get('created_at')), item[0])
    )
    summaries = {}
    current_tickets = {}
    student_profiles = {}
    for session_id, info in ordered:
        ensure_session_structure(info)
        if info.get('is_discarded'):
            summaries[session_id] = {
                'session_id': session_id,
                'session_name': info.get('session_name', ''),
                'created_at': info.get('created_at'),
                'is_discarded': True,
                'tickets_snapshot': {},
                'profiles': {},
                'total_tickets': 0.0,
                'candidates': [],
                'top_candidates': [],
                'eligible_count': 0,
                'excluded_records': 0,
                'generated_at': generated_at
            }
            continue
        pre_session_keys = set(current_tickets.keys())
        present_keys = set()
        excluded_records = 0
        for record in info.get('clean_records', []):
            profile = build_profile_from_record(record)
            key = profile.get('key')
            if not key or not is_student_profile_eligible(profile):
                excluded_records += 1
                continue
            present_keys.add(key)
            student_profiles[key] = profile
            current_tickets[key] = current_tickets.get(key, 0.0) + 1.0
        for record in info.get('red_records', []):
            profile = build_profile_from_record(record)
            key = profile.get('key')
            if not key or not is_student_profile_eligible(profile):
                excluded_records += 1
                continue
            present_keys.add(key)
            student_profiles[key] = profile
            current_tickets[key] = 0.0
        for key in pre_session_keys:
            if key not in present_keys:
                value = current_tickets.get(key, 0.0)
                if value > 0:
                    current_tickets[key] = value / 2.0
        snapshot = {k: float(v) for k, v in current_tickets.items() if v > 0}
        total_tickets = sum(snapshot.values())
        profiles_snapshot = {k: student_profiles.get(k, {}).copy() for k in snapshot}
        candidates = []
        for key, value in sorted(snapshot.items(), key=lambda item: (-item[1], item[0])):
            profile = profiles_snapshot.get(key, {})
            display_name = profile.get('display_name') or format_display_name(profile)
            candidate = {
                'key': key,
                'tickets': value,
                'preferred_name': profile.get('preferred_name', ''),
                'last_name': profile.get('last_name', ''),
                'display_name': display_name,
                'grade': profile.get('grade', ''),
                'advisor': profile.get('advisor', ''),
                'house': profile.get('house', ''),
                'clan': profile.get('clan', ''),
                'student_id': profile.get('student_id', ''),
                'probability': (value / total_tickets * 100.0) if total_tickets > 0 else 0.0
            }
            candidates.append(candidate)
        summaries[session_id] = {
            'session_id': session_id,
            'session_name': info.get('session_name', ''),
            'created_at': info.get('created_at'),
            'is_discarded': False,
            'tickets_snapshot': snapshot,
            'profiles': profiles_snapshot,
            'total_tickets': total_tickets,
            'candidates': candidates,
            'top_candidates': candidates[:3],
            'eligible_count': len(candidates),
            'excluded_records': excluded_records,
            'generated_at': generated_at
        }
        draw_info = info.get('draw_info', {})
        winner = draw_info.get('winner')
        if winner and draw_info.get('finalized'):
            winner_key = winner.get('key')
            if winner_key:
                current_tickets[winner_key] = 0.0
    return summaries

def get_ticket_summary_for_session(session_id):
    summaries = compute_ticket_rollups()
    return summaries.get(session_id), summaries

def serialize_draw_info(draw_info):
    if not isinstance(draw_info, dict):
        return {
            'winner': None,
            'winner_timestamp': None,
            'selected_by': None,
            'method': None,
            'finalized': False,
            'finalized_at': None,
            'finalized_by': None,
            'override': False,
            'tickets_at_selection': None,
            'probability_at_selection': None,
            'eligible_pool_size': None,
            'history': []
        }
    result = {
        'winner_timestamp': draw_info.get('winner_timestamp'),
        'selected_by': draw_info.get('selected_by'),
        'method': draw_info.get('method'),
        'finalized': draw_info.get('finalized', False),
        'finalized_at': draw_info.get('finalized_at'),
        'finalized_by': draw_info.get('finalized_by'),
        'override': draw_info.get('override', False),
        'tickets_at_selection': draw_info.get('tickets_at_selection'),
        'probability_at_selection': draw_info.get('probability_at_selection'),
        'eligible_pool_size': draw_info.get('eligible_pool_size'),
        'history': list(draw_info.get('history', []))
    }
    winner = draw_info.get('winner')
    if isinstance(winner, dict):
        result['winner'] = {
            'key': winner.get('key'),
            'display_name': winner.get('display_name') or format_display_name(winner),
            'preferred_name': winner.get('preferred_name'),
            'last_name': winner.get('last_name'),
            'grade': winner.get('grade'),
            'advisor': winner.get('advisor'),
            'house': winner.get('house'),
            'clan': winner.get('clan'),
            'student_id': winner.get('student_id'),
            'tickets': winner.get('tickets'),
            'probability': winner.get('probability')
        }
    else:
        result['winner'] = None
    return result

def get_current_user():
    """Get current logged in user"""
    if 'user_id' in session:
        return users_db.get(session['user_id'])
    return None

def require_auth():
    """Check if user is authenticated"""
    return 'user_id' in session and session['user_id'] in users_db

def require_auth_or_guest():
    """Check if user is authenticated or is a guest"""
    return require_auth() or session.get('guest_access', False)

def is_guest():
    """Check if current user is a guest"""
    return session.get('guest_access', False) and 'user_id' not in session

def require_admin():
    """Check if user is admin or super admin"""
    user = get_current_user()
    return user and user['role'] in ['admin', 'superadmin']

def require_superadmin():
    """Check if user is super admin"""
    user = get_current_user()
    return user and user['role'] == 'superadmin'

@recorder_bp.route('/auth/login', methods=['POST'])
def login():
    """User login"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if username in users_db and users_db[username]['password'] == password:
        user = users_db[username]
        
        # Check account status
        if user.get('status', 'active') != 'active':
            return jsonify({'error': 'Account is disabled. Please contact an administrator.'}), 403
        
        session['user_id'] = username

        return jsonify({
            'status': 'success',
            'user': {
                'username': username,
                'name': user['name'],
                'role': user['role']
            }
        }), 200
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

@recorder_bp.route('/auth/logout', methods=['POST'])
def logout():
    """User logout"""
    user_id = session.pop('user_id', None)
    session.pop('session_id', None)
    session.pop('guest_access', None)
    return jsonify({'status': 'success', 'message': 'Logged out successfully'}), 200

@recorder_bp.route('/auth/guest', methods=['POST'])
def guest_login():
    """Guest login - allows viewing sessions without signup"""
    session['guest_access'] = True
    return jsonify({
        'status': 'success',
        'user': {
            'username': 'guest',
            'name': 'Guest User',
            'role': 'guest'
        }
    }), 200

@recorder_bp.route('/auth/signup', methods=['POST'])
def signup():
    """User signup"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    invite_code = data.get('invite_code', '').strip()
    
    # Validation
    if not username or not password or not name or not invite_code:
        return jsonify({'error': 'Username, password, name, and invite code are required'}), 400
    
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters long'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400
    
    if username in users_db:
        return jsonify({'error': 'Username already exists'}), 409

    # Validate invite code
    code_data = invite_codes_db.get(invite_code)
    if not code_data or code_data.get('used'):
        return jsonify({'error': 'Invalid invite code'}), 403

    # Create new user with role from invite code (default to 'user')
    users_db[username] = {
        'password': password,
        'role': code_data.get('role', 'user'),
        'name': name,
        'status': 'active'
    }

    # Mark invite code as used
    code_data['used'] = True
    save_invite_codes_db()

    # Save users database to file
    save_users_db()
    
    return jsonify({
        'status': 'success',
        'message': 'Account created successfully'
    }), 201

@recorder_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    if require_auth():
        user = get_current_user()
        return jsonify({
            'authenticated': True,
            'user': {
                'username': session['user_id'],
                'name': user['name'],
                'role': user['role']
            }
        }), 200
    elif is_guest():
        return jsonify({
            'authenticated': True,
            'user': {
                'username': 'guest',
                'name': 'Guest User',
                'role': 'guest'
            }
        }), 200
    else:
        return jsonify({'authenticated': False}), 200

@recorder_bp.route('/admin/manage-account-status', methods=['POST'])
def manage_account_status():
    """Manage account status (enable/disable users)"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    current_user = get_current_user()
    data = request.get_json()
    target_username = data.get('username')
    new_status = data.get('status')  # 'active' or 'disabled'
    
    if not target_username or not new_status:
        return jsonify({'error': 'Username and status are required'}), 400
    
    if target_username not in users_db:
        return jsonify({'error': 'User not found'}), 404
    
    target_user = users_db[target_username]
    
    # Permission checks
    if current_user['role'] == 'superadmin':
        # Super admin can manage everyone except themselves
        if target_username == session['user_id']:
            return jsonify({'error': 'Cannot modify your own account status'}), 403
    elif current_user['role'] == 'admin':
        # Admin can manage users but not super admins or other admins
        if target_user['role'] in ['superadmin', 'admin']:
            return jsonify({'error': 'Insufficient permissions to modify this account'}), 403
    else:
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    # Update status
    users_db[target_username]['status'] = new_status
    save_users_db()
    
    return jsonify({
        'status': 'success',
        'message': f'Account {target_username} has been {new_status}'
    }), 200

@recorder_bp.route('/session/request-delete', methods=['POST'])
def request_delete_session():
    """Submit a delete request for a session"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'Session ID is required'}), 400
    
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    # Get current user
    current_user = get_current_user()

    # Users can request deletion for any session; admins and superadmins delete immediately

    # Admins and super admins delete immediately
    if current_user['role'] in ['admin', 'superadmin']:
        session_name = session_data[session_id]['session_name']
        del session_data[session_id]
        save_session_data()
        if session.get('session_id') == session_id:
            session.pop('session_id', None)
        return jsonify({
            'status': 'success',
            'message': f'Session "{session_name}" deleted successfully',
            'deleted_session_id': session_id
        }), 200

    # Prevent multiple delete requests for the same session
    existing = next((req for req in delete_requests
                     if req['session_id'] == session_id and req['status'] == 'pending'), None)
    if existing:
        return jsonify({'error': 'Delete request already submitted for this session'}), 400

    session_info = session_data[session_id]
    ensure_session_structure(session_info)
    session_name = session_info['session_name']

    # Collect session statistics
    clean_count = len(session_info.get('clean_records', []))
    dirty_count = get_dirty_count(session_info)
    red_count = len(session_info.get('red_records', []))
    faculty_clean_count = len(session_info.get('faculty_clean_records', []))
    total_records = clean_count + dirty_count + red_count

    # Create delete request
    request_obj = {
        'id': str(uuid.uuid4()),
        'session_id': session_id,
        'session_name': session_name,
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
        'message': f'Delete request submitted for "{session_name}"',
        'request': request_obj
    }), 200

@recorder_bp.route('/admin/delete-requests', methods=['GET'])
def get_delete_requests():
    """Get pending delete requests (admin/super admin only)"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    pending_requests = [req for req in delete_requests if req.get('status') == 'pending']
    return jsonify({
        'status': 'success',
        'requests': pending_requests
    }), 200

@recorder_bp.route('/admin/users', methods=['GET'])
def admin_get_users():
    """Admin: Get all users"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    users_list = []
    for username, user_data in users_db.items():
        users_list.append({
            'username': username,
            'name': user_data['name'],
            'role': user_data['role']
        })
    
    return jsonify({'users': users_list}), 200

@recorder_bp.route('/admin/invite', methods=['POST'])
def admin_create_invite():
    """Admin: Generate a one-time invite code"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    code = str(uuid.uuid4())
    invite_codes_db[code] = {
        'issued_by': session.get('user_id'),
        'used': False,
        'role': 'user'
    }
    save_invite_codes_db()
    return jsonify({'status': 'success', 'invite_code': code}), 201

@recorder_bp.route('/admin/sessions', methods=['GET'])
def admin_get_all_sessions():
    """Admin: Get all sessions from all users"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    all_sessions = []
    for session_id, data in session_data.items():
        ensure_session_structure(data)
        total_records = len(data['clean_records']) + get_dirty_count(data) + len(data['red_records'])
        all_sessions.append({
            'session_id': session_id,
            'session_name': data['session_name'],
            'owner': data.get('owner', 'unknown'),
            'created_at': data.get('created_at', 'unknown'),
            'total_records': total_records,
            'clean_count': len(data['clean_records']),
            'dirty_count': get_dirty_count(data),
            'red_count': len(data['red_records']),
            'faculty_clean_count': len(data.get('faculty_clean_records', []))
        })
    
    return jsonify({'sessions': all_sessions}), 200

@recorder_bp.route('/admin/sessions/<session_id>', methods=['DELETE'])
def admin_delete_session(session_id):
    """Admin: Delete any session"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_name = session_data[session_id]['session_name']
    del session_data[session_id]
    save_session_data()
    if session.get('session_id') == session_id:
        session.pop('session_id', None)
    
    return jsonify({
        'status': 'success',
        'message': f'Session "{session_name}" deleted successfully by admin',
        'deleted_session_id': session_id
    }), 200

@recorder_bp.route('/session/create', methods=['POST'])
def create_session():
    """Create a new session"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json(silent=True) or {}
    custom_name = data.get('session_name', '').strip()
    is_public = data.get('is_public', True)

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Existing session names
    existing_names = {d['session_name'] for d in session_data.values()}

    # Generate session name
    if custom_name:
        if custom_name in existing_names:
            return jsonify({'error': 'Session name already exists'}), 400
        session_name = custom_name
    else:
        now = datetime.now()
        base_name = f"Golden_Plate_{now.strftime('%B_%d_%Y')}"
        session_name = base_name
        counter = 1
        while session_name in existing_names:
            session_name = f"{base_name}_{counter}"
            counter += 1
    
    # Create session data with owner information
    session_data[session_id] = {
        'session_name': session_name,
        'owner': session['user_id'],
        'created_at': datetime.now().isoformat(),
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
    
    # Save session data to file
    save_session_data()
    
    # Set as current session
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
    
    user_sessions = []
    for session_id, data in session_data.items():
        ensure_session_structure(data)
        if is_guest() and not data.get('is_public', True):
            continue
        total_records = len(data['clean_records']) + get_dirty_count(data) + len(data['red_records'])
        clean_count = len(data['clean_records'])
        dirty_count = get_dirty_count(data) + len(data['red_records'])  # Combine dirty + very dirty
        faculty_clean_count = len(data.get('faculty_clean_records', []))

        # Calculate percentages - both clean and faculty clean count as "clean" for ratio
        combined_clean_count = clean_count + faculty_clean_count
        total_for_ratio = total_records + faculty_clean_count  # Include faculty in total for ratio calculation
        clean_percentage = (combined_clean_count / total_for_ratio * 100) if total_for_ratio > 0 else 0
        dirty_percentage = (dirty_count / total_for_ratio * 100) if total_for_ratio > 0 else 0

        pending = any(req['session_id'] == session_id and req['status'] == 'pending'
                       for req in delete_requests)
        user_sessions.append({
            'session_id': session_id,
            'session_name': data['session_name'],
            'owner': data.get('owner', 'unknown'),
            'total_records': total_records,
            'clean_count': clean_count,
            'dirty_count': dirty_count,
            'faculty_clean_count': faculty_clean_count,
            'clean_percentage': round(clean_percentage, 1),
            'dirty_percentage': round(dirty_percentage, 1),
            'is_public': data.get('is_public', True),
            'delete_requested': pending,
            'is_discarded': data.get('is_discarded', False),
            'draw_info': serialize_draw_info(data.get('draw_info', {}))
        })
    
    return jsonify({
        'sessions': user_sessions,
        'has_global_csv': bool(global_csv_data.get('data'))
    }), 200

@recorder_bp.route('/session/switch/<session_id>', methods=['POST'])
def switch_session(session_id):
    """Switch to a different session. Guests may only access public sessions."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401
    
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    if is_guest() and not session_data[session_id].get('is_public', True):
        return jsonify({'error': 'Access denied'}), 403

    session['session_id'] = session_id
    
    return jsonify({
        'session_id': session_id,
        'session_name': session_data[session_id]['session_name']
    }), 200

@recorder_bp.route('/session/delete/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session directly"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    # Get current user
    current_user = get_current_user()
    session_owner = session_data[session_id].get('owner')
    
    # Permission check: users can only delete their own sessions, admins and super admins can delete any session
    if current_user['role'] == 'user' and session_owner != session['user_id']:
        return jsonify({'error': 'You can only delete sessions that you created'}), 403
    
    session_name = session_data[session_id]['session_name']
    del session_data[session_id]
    save_session_data()
    if session.get('session_id') == session_id:
        session.pop('session_id', None)
    
    return jsonify({
        'status': 'success',
        'message': f'Session "{session_name}" deleted successfully',
        'deleted_session_id': session_id
    }), 200

@recorder_bp.route('/admin/delete-requests/<request_id>/approve', methods=['POST'])
def approve_delete_request(request_id):
    """Approve a delete request (admin/superadmin only)"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    # Find the request
    request_obj = next((req for req in delete_requests if req['id'] == request_id), None)
    if not request_obj:
        return jsonify({'error': 'Delete request not found'}), 404
    
    if request_obj['status'] != 'pending':
        return jsonify({'error': 'Request is not pending'}), 400
    
    session_id = request_obj['session_id']
    
    # Check if session still exists
    if session_id not in session_data:
        # Mark request as completed since session no longer exists
        request_obj['status'] = 'completed'
        request_obj['approved_by'] = session['user_id']
        request_obj['approved_at'] = datetime.now().isoformat()
        save_delete_requests()
        return jsonify({'message': 'Session no longer exists, request marked as completed'}), 200
    
    # Delete the session
    session_name = session_data[session_id]['session_name']
    del session_data[session_id]
    save_session_data()
    if session.get('session_id') == session_id:
        session.pop('session_id', None)
    
    # Update request status
    request_obj['status'] = 'approved'
    request_obj['approved_by'] = session['user_id']
    request_obj['approved_at'] = datetime.now().isoformat()
    save_delete_requests()
    
    return jsonify({
        'status': 'success',
        'message': f'Session "{session_name}" deleted successfully',
        'deleted_session_id': session_id
    }), 200

@recorder_bp.route('/admin/approve-delete', methods=['POST'])
def approve_delete_request_api():
    data = request.get_json(silent=True) or {}
    request_id = data.get('request_id')
    if not request_id:
        return jsonify({'error': 'Request ID is required'}), 400
    return approve_delete_request(request_id)

@recorder_bp.route('/admin/delete-requests/<request_id>/reject', methods=['POST'])
def reject_delete_request(request_id):
    """Reject a delete request (admin/superadmin only)"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json(silent=True) or {}
    rejection_reason = data.get('reason', 'No reason provided')
    
    # Find the request
    request_obj = next((req for req in delete_requests if req['id'] == request_id), None)
    if not request_obj:
        return jsonify({'error': 'Delete request not found'}), 404
    
    if request_obj['status'] != 'pending':
        return jsonify({'error': 'Request is not pending'}), 400
    
    # Update request status
    request_obj['status'] = 'rejected'
    request_obj['rejected_by'] = session['user_id']
    request_obj['rejected_at'] = datetime.now().isoformat()
    request_obj['rejection_reason'] = rejection_reason
    save_delete_requests()
    
    return jsonify({
        'status': 'success',
        'message': f'Delete request rejected',
        'request_id': request_id
    }), 200

@recorder_bp.route('/csv/upload', methods=['POST'])
def upload_csv():
    """Upload CSV file (requires admin or super admin)"""
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    try:
        # Read CSV content
        content = file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(content))
        
        # Convert to list and validate structure
        rows = list(csv_reader)
        if not rows:
            return jsonify({'error': 'CSV file is empty'}), 400
        
        # Check for required columns
        required_columns = ['Student ID', 'Last', 'Preferred', 'Grade', 'Advisor', 'House', 'Clan']
        if not all(col in csv_reader.fieldnames for col in required_columns):
            return jsonify({'error': f'CSV must contain columns: {", ".join(required_columns)}'}), 400
        
        # Store globally (accessible to all users)
        user_id = session['user_id']
        global global_csv_data
        global_csv_data = {
            'data': rows,
            'columns': csv_reader.fieldnames,
            'uploaded_by': user_id,
            'uploaded_at': datetime.now().isoformat()
        }
        update_student_lookup()
        
        # Save to persistent storage
        save_global_csv_data()

        return jsonify({
            'status': 'success',
            'rows_count': len(rows),
            'uploaded_by': user_id
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error processing CSV: {str(e)}'}), 400

@recorder_bp.route('/csv/preview', methods=['GET'])
def preview_csv():
    """Preview the current student database (admin/super admin only)"""
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403
    
    csv_data = global_csv_data

    if not csv_data:
        return jsonify({
            'status': 'no_data',
            'message': 'No student database uploaded yet'
        }), 200
    
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    # Calculate pagination
    total_records = len(csv_data['data'])
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Get paginated data
    paginated_rows = csv_data['data'][start_idx:end_idx]
    sanitized_rows = [{
        'Preferred': str(row.get('Preferred', '') or '').strip(),
        'Last': str(row.get('Last', '') or '').strip(),
        'Grade': str(row.get('Grade', '') or '').strip(),
        'Advisor': str(row.get('Advisor', '') or '').strip(),
        'House': str(row.get('House', '') or '').strip(),
        'Clan': str(row.get('Clan', '') or '').strip()
    } for row in paginated_rows]

    return jsonify({
        'status': 'success',
        'data': sanitized_rows,
        'columns': ['Preferred', 'Last', 'Grade', 'Advisor', 'House', 'Clan'],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_records': total_records,
            'total_pages': (total_records + per_page - 1) // per_page,
            'has_next': end_idx < total_records,
            'has_prev': page > 1
        },
        'metadata': {
            'uploaded_by': csv_data.get('uploaded_by', 'unknown'),
            'uploaded_at': csv_data.get('uploaded_at', 'unknown')
        }
    }), 200

@recorder_bp.route('/csv/student-names', methods=['GET'])
def get_student_names():
    """Get student names for dropdown suggestions"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    csv_data = global_csv_data
    if not csv_data or 'data' not in csv_data:
        return jsonify({
            'status': 'no_data',
            'names': []
        }), 200
    
    # Extract names from CSV data
    names = []
    for row in csv_data['data']:
        preferred = str(row.get('Preferred', '') or '').strip()
        last = str(row.get('Last', '') or '').strip()
        
        if preferred and last:
            full_name = f"{preferred} {last}"
            names.append({
                'display_name': full_name,
                'preferred': preferred,
                'last': last,
                'student_id': str(row.get('Student ID', '') or '').strip()
            })
        elif preferred:
            names.append({
                'display_name': preferred,
                'preferred': preferred,
                'last': '',
                'student_id': str(row.get('Student ID', '') or '').strip()
            })
    
    # Sort names alphabetically
    names.sort(key=lambda x: x['display_name'].lower())
    
    return jsonify({
        'status': 'success',
        'names': names
    }), 200

@recorder_bp.route('/teachers/upload', methods=['POST'])
def upload_teachers():
    """Upload teacher list (admin/super admin only)"""
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith(('.csv', '.txt')):
        return jsonify({'error': 'File must be a CSV or TXT file'}), 400
    
    try:
        # Read file content
        content = file.read().decode('utf-8-sig')  # Handle BOM if present
        lines = content.strip().split('\n')
        
        teachers = []
        for line in lines:
            # Remove quotes and whitespace
            teacher_name = line.strip().strip('"').strip("'")
            if teacher_name:  # Skip empty lines
                teachers.append({
                    'name': teacher_name,
                    'display_name': teacher_name
                })
        
        if not teachers:
            return jsonify({'error': 'No valid teacher names found in file'}), 400
        
        # Store globally (accessible to all users)
        user_id = session['user_id']
        global global_teacher_data
        global_teacher_data = {
            'teachers': teachers,
            'uploaded_by': user_id,
            'uploaded_at': datetime.now().isoformat()
        }
        
        # Save to persistent storage
        save_global_teacher_data()

        return jsonify({
            'status': 'success',
            'count': len(teachers),
            'uploaded_by': user_id
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 400

@recorder_bp.route('/teachers/list', methods=['GET'])
def get_teacher_names():
    """Get teacher names for dropdown suggestions"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    teacher_data = global_teacher_data
    if not teacher_data or 'teachers' not in teacher_data:
        return jsonify({
            'status': 'no_data',
            'names': []
        }), 200
    
    # Sort names alphabetically
    teachers = sorted(teacher_data['teachers'], key=lambda x: x['display_name'].lower())
    
    return jsonify({
        'status': 'success',
        'names': teachers
    }), 200

@recorder_bp.route('/teachers/preview', methods=['GET'])
def preview_teachers():
    """Preview the current teacher list (admin/super admin only)"""
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403
    
    teacher_data = global_teacher_data

    if not teacher_data:
        return jsonify({
            'status': 'no_data',
            'message': 'No teacher list uploaded yet'
        }), 200
    
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    teachers = teacher_data.get('teachers', [])
    
    # Calculate pagination
    total_records = len(teachers)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Get paginated data
    paginated_teachers = teachers[start_idx:end_idx]

    return jsonify({
        'status': 'success',
        'data': paginated_teachers,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_records': total_records,
            'total_pages': (total_records + per_page - 1) // per_page,
            'has_next': end_idx < total_records,
            'has_prev': page > 1
        },
        'metadata': {
            'uploaded_by': teacher_data.get('uploaded_by', 'unknown'),
            'uploaded_at': teacher_data.get('uploaded_at', 'unknown')
        }
    }), 200

@recorder_bp.route('/record/<category>', methods=['POST'])
def record_student(category):
    """Record a student in a category"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400

    if category not in ['clean', 'dirty', 'red', 'faculty']:
        return jsonify({'error': 'Invalid category'}), 400

    data = request.get_json(silent=True) or {}
    input_value = data.get('input_value', '').strip()

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
        return jsonify({
            'status': 'success',
            'preferred_name': preferred_name,
            'first_name': preferred_name,
            'last_name': last_name,
            'category': 'faculty',
            'is_manual_entry': True,
            'recorded_by': session['user_id']
        }), 200

    # Remaining categories rely on student database lookup (clean, red)
    if not input_value:
        return jsonify({'error': 'Student ID or Name is required'}), 400

    csv_data = global_csv_data

    # Determine if input is ID or name
    student_record = None
    is_manual_entry = False
    preferred_name = ""
    last_name = ""
    grade = ""
    advisor = ""
    house = ""
    clan = ""
    student_id = ""

    if csv_data and csv_data['data']:
        for row in csv_data['data']:
            if str(row.get('Student ID', '')).strip() == input_value:
                student_record = row
                break

    if not student_record and csv_data and csv_data['data']:
        name_parts = input_value.split()
        if len(name_parts) >= 2:
            input_first = name_parts[0].lower()
            input_last = ' '.join(name_parts[1:]).lower()

            for row in csv_data['data']:
                csv_first = str(row.get('Preferred', '')).strip().lower()
                csv_last = str(row.get('Last', '')).strip().lower()

                if csv_first == input_first and csv_last == input_last:
                    student_record = row
                    break

    if not student_record:
        is_manual_entry = True
        name_parts = input_value.split()
        if len(name_parts) >= 2:
            preferred_name = name_parts[0].capitalize()
            last_name = ' '.join(name_parts[1:]).capitalize()
        elif len(name_parts) == 1:
            preferred_name = name_parts[0].capitalize()
            last_name = ""
        else:
            preferred_name = input_value.capitalize()
            last_name = ""
    else:
        preferred_name = str(student_record.get('Preferred', '') or '').strip()
        last_name = str(student_record.get('Last', '') or '').strip()
        grade = str(student_record.get('Grade', '') or '').strip()
        advisor = str(student_record.get('Advisor', '') or '').strip()
        house = str(student_record.get('House', '') or '').strip()
        clan = str(student_record.get('Clan', '') or '').strip()
        student_id = str(student_record.get('Student ID', '') or '').strip()

    if not student_id and student_record:
        student_id = str(student_record.get('Student ID', '') or '').strip()

    preferred_name = preferred_name or ""
    last_name = last_name or ""
    grade = grade or ""
    advisor = advisor or ""
    house = house or ""
    clan = clan or ""
    student_id = student_id or ""

    student_records = session_info['clean_records'] + session_info['red_records']

    def normalize_field(value):
        return str(value or '').strip().lower()

    target_student_id = normalize_field(student_id)
    target_preferred = normalize_field(preferred_name)
    target_last = normalize_field(last_name)
    target_grade = normalize_field(grade)
    target_advisor = normalize_field(advisor)
    target_house = normalize_field(house)
    target_clan = normalize_field(clan)

    def is_duplicate(existing_record):
        existing_student_id = normalize_field(existing_record.get('student_id'))

        if target_student_id and existing_student_id:
            return existing_student_id == target_student_id

        if target_student_id and not existing_student_id:
            return False

        if not target_student_id and existing_student_id:
            return False

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

    if duplicate_check:
        existing_category = None
        for cat in ['clean', 'red']:
            if any(
                is_duplicate(record)
                for record in session_info[f'{cat}_records']
            ):
                existing_category = cat
                break

        return jsonify({
            'error': 'duplicate',
            'message': f'Student already recorded as {existing_category.upper()} in this session'
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
        'category': category,
        'timestamp': datetime.now().isoformat(),
        'recorded_by': session['user_id'],
        'is_manual_entry': is_manual_entry
    }

    session_info[f'{category}_records'].append(record)
    session_info['scan_history'].append(record)
    save_session_data()

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
        'category': category,
        'is_manual_entry': is_manual_entry,
        'recorded_by': session['user_id']
    }), 200

@recorder_bp.route('/session/status', methods=['GET'])
def get_session_status():
    """Get current session status with percentage calculations"""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401
    
    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    data = session_data[session_id]
    if is_guest() and not data.get('is_public', True):
        return jsonify({'error': 'Access denied'}), 403
    
    ensure_session_structure(data)
    clean_count = len(data['clean_records'])
    dirty_count = get_dirty_count(data)
    red_count = len(data['red_records'])
    combined_dirty_count = dirty_count + red_count  # Combine dirty + very dirty
    faculty_clean_count = len(data.get('faculty_clean_records', []))
    total_recorded = clean_count + dirty_count + red_count
    
    # Calculate percentages - both clean and faculty clean count as "clean" for ratio
    combined_clean_count = clean_count + faculty_clean_count
    total_for_ratio = total_recorded + faculty_clean_count  # Include faculty in total for ratio calculation
    clean_percentage = (combined_clean_count / total_for_ratio * 100) if total_for_ratio > 0 else 0
    dirty_percentage = (combined_dirty_count / total_for_ratio * 100) if total_for_ratio > 0 else 0
    
    return jsonify({
        'session_id': session_id,
        'session_name': data['session_name'],
        'clean_count': clean_count,
        'dirty_count': dirty_count,
        'red_count': red_count,
        'combined_dirty_count': combined_dirty_count,
        'faculty_clean_count': faculty_clean_count,
        'total_recorded': total_recorded,
        'clean_percentage': round(clean_percentage, 1),
        'dirty_percentage': round(dirty_percentage, 1),
        'scan_history_count': len(data['scan_history']),
        'is_discarded': data.get('is_discarded', False),
        'draw_info': serialize_draw_info(data.get('draw_info', {}))
    }), 200

@recorder_bp.route('/session/history', methods=['GET'])
def get_session_history():
    """Get scan history for current session"""
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

@recorder_bp.route('/export/csv', methods=['GET'])
def export_csv():
    """Export session records as CSV"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    data = session_data[session_id]
    
    ensure_session_structure(data)

    # Create CSV content with four columns
    output = io.StringIO()

    # Write header
    output.write("CLEAN,DIRTY,RED,FACULTY CLEAN\n")

    # Helper to format names using preferred name when available
    def format_name(record):
        preferred = (record.get('preferred_name') or record.get('first_name', '') or '').strip()
        last = (record.get('last_name') or '').strip()
        full_name = f"{preferred} {last}".strip()
        return full_name

    # Get all records for each category
    clean_names = [format_name(record) for record in data['clean_records']]
    red_names = [format_name(record) for record in data['red_records']]
    faculty_names = [format_name(record) for record in data.get('faculty_clean_records', [])]
    dirty_count = get_dirty_count(data)

    # Find the maximum number of records to determine how many rows we need
    max_records = max(
        len(clean_names),
        len(red_names),
        len(faculty_names),
        1 if dirty_count > 0 else 0
    )

    # Write data rows
    for i in range(max_records):
        clean_name = clean_names[i] if i < len(clean_names) else ""
        red_name = red_names[i] if i < len(red_names) else ""
        faculty_name = faculty_names[i] if i < len(faculty_names) else ""
        dirty_value = str(dirty_count) if i == 0 and dirty_count > 0 else ""

        output.write(f'"{clean_name}","{dirty_value}","{red_name}","{faculty_name}"\n')
    
    csv_content = output.getvalue()
    output.close()
    
    from flask import Response
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{data["session_name"]}_records.csv"'}
    )


@recorder_bp.route('/export/csv/detailed', methods=['GET'])
def export_detailed_csv():
    """Export detailed session records without student IDs"""
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

    from flask import Response
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{data["session_name"]}_detailed_records.csv"'}
    )



@recorder_bp.route('/session/<session_id>/draw/summary', methods=['GET'])
def get_draw_summary(session_id):
    """Return draw summary for a session."""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    if is_guest() and not session_info.get('is_public', True):
        return jsonify({'error': 'Access denied'}), 403

    ensure_session_structure(session_info)
    summary, _ = get_ticket_summary_for_session(session_id)
    if not summary:
        summary = {
            'session_id': session_id,
            'session_name': session_info.get('session_name', ''),
            'created_at': session_info.get('created_at'),
            'is_discarded': session_info.get('is_discarded', False),
            'tickets_snapshot': {},
            'total_tickets': 0.0,
            'candidates': [],
            'top_candidates': [],
            'eligible_count': 0,
            'excluded_records': 0,
            'generated_at': datetime.now().isoformat()
        }

    response = {
        'session_id': session_id,
        'session_name': session_info.get('session_name', ''),
        'created_at': session_info.get('created_at'),
        'is_discarded': session_info.get('is_discarded', False),
        'total_tickets': summary.get('total_tickets', 0.0),
        'eligible_count': summary.get('eligible_count', 0),
        'excluded_records': summary.get('excluded_records', 0),
        'top_candidates': summary.get('top_candidates', []),
        'candidates': summary.get('candidates', []),
        'ticket_snapshot': summary.get('tickets_snapshot', {}),
        'generated_at': summary.get('generated_at', datetime.now().isoformat()),
        'draw_info': serialize_draw_info(session_info.get('draw_info', {}))
    }
    return jsonify(response), 200


@recorder_bp.route('/session/<session_id>/draw/start', methods=['POST'])
def start_draw(session_id):
    """Start a weighted random draw for a session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    ensure_session_structure(session_info)

    if session_info.get('is_discarded'):
        return jsonify({'error': 'Session is discarded from draw calculations'}), 400

    student_records_count = len(session_info.get('clean_records', [])) + len(session_info.get('red_records', []))
    if student_records_count <= 0:
        return jsonify({'error': 'No student records available for this session'}), 400

    summary, _ = get_ticket_summary_for_session(session_id)
    if not summary or summary.get('total_tickets', 0.0) <= 0:
        return jsonify({'error': 'No eligible tickets available for drawing'}), 400

    tickets_snapshot = summary.get('tickets_snapshot') or {}
    total_tickets = summary.get('total_tickets', 0.0)
    profiles = summary.get('profiles') or {}

    cumulative = 0.0
    target = secure_random.random() * total_tickets
    chosen_key = None
    for key, value in tickets_snapshot.items():
        cumulative += value
        if target <= cumulative:
            chosen_key = key
            break
    if chosen_key is None and tickets_snapshot:
        chosen_key = next(iter(tickets_snapshot))

    if chosen_key is None:
        return jsonify({'error': 'Unable to determine a winner'}), 400

    profile = profiles.get(chosen_key, {}).copy()
    if not profile:
        preferred, last = split_student_key(chosen_key)
        profile = {
            'preferred_name': preferred.title(),
            'last_name': last.title(),
            'grade': '',
            'advisor': '',
            'house': '',
            'clan': '',
            'student_id': ''
        }
    display_name = profile.get('display_name') or format_display_name(profile)
    winner_tickets = tickets_snapshot.get(chosen_key, 0.0)
    probability = (winner_tickets / total_tickets * 100.0) if total_tickets > 0 else 0.0

    winner_data = {
        'key': chosen_key,
        'preferred_name': profile.get('preferred_name', ''),
        'last_name': profile.get('last_name', ''),
        'display_name': display_name,
        'grade': profile.get('grade', ''),
        'advisor': profile.get('advisor', ''),
        'house': profile.get('house', ''),
        'clan': profile.get('clan', ''),
        'student_id': profile.get('student_id', ''),
        'tickets': winner_tickets,
        'probability': probability
    }

    timestamp = datetime.now().isoformat()
    draw_info = session_info['draw_info']
    draw_info['winner'] = winner_data
    draw_info['winner_timestamp'] = timestamp
    draw_info['selected_by'] = session.get('user_id')
    draw_info['method'] = 'random'
    draw_info['finalized'] = False
    draw_info['finalized_at'] = None
    draw_info['finalized_by'] = None
    draw_info['override'] = False
    draw_info['tickets_at_selection'] = total_tickets
    draw_info['probability_at_selection'] = probability
    draw_info['eligible_pool_size'] = summary.get('eligible_count', 0)

    history_entry = {
        'action': 'random_draw',
        'performed_by': session.get('user_id'),
        'timestamp': timestamp,
        'winner_key': chosen_key,
        'winner_display_name': display_name,
        'total_tickets': total_tickets,
        'winner_tickets': winner_tickets,
        'probability': probability
    }
    draw_info['history'].append(history_entry)

    save_session_data()

    updated_summary, _ = get_ticket_summary_for_session(session_id)
    return jsonify({
        'status': 'success',
        'winner': winner_data,
        'draw_info': serialize_draw_info(draw_info),
        'summary': updated_summary
    }), 200


@recorder_bp.route('/session/<session_id>/draw/finalize', methods=['POST'])
def finalize_draw(session_id):
    """Finalize the current draw winner for a session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    ensure_session_structure(session_info)
    draw_info = session_info.get('draw_info', {})
    winner = draw_info.get('winner')
    if not winner:
        return jsonify({'error': 'No winner to finalize'}), 400

    if not draw_info.get('finalized'):
        timestamp = datetime.now().isoformat()
        draw_info['finalized'] = True
        draw_info['finalized_at'] = timestamp
        draw_info['finalized_by'] = session.get('user_id')
        draw_info['history'].append({
            'action': 'finalized',
            'performed_by': session.get('user_id'),
            'timestamp': timestamp,
            'winner_key': winner.get('key'),
            'winner_display_name': winner.get('display_name')
        })
        save_session_data()

    updated_summary, _ = get_ticket_summary_for_session(session_id)
    return jsonify({
        'status': 'success',
        'finalized': True,
        'draw_info': serialize_draw_info(draw_info),
        'summary': updated_summary
    }), 200


@recorder_bp.route('/session/<session_id>/draw/reset', methods=['POST'])
def reset_draw(session_id):
    """Reset the draw for a session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    ensure_session_structure(session_info)
    draw_info = session_info.get('draw_info', {})
    winner = draw_info.get('winner')

    if not winner:
        return jsonify({'error': 'No draw to reset'}), 400

    if draw_info.get('finalized') and not require_superadmin():
        return jsonify({'error': 'Only super admins can reset a finalized draw'}), 403

    timestamp = datetime.now().isoformat()
    draw_info['history'].append({
        'action': 'reset',
        'performed_by': session.get('user_id'),
        'timestamp': timestamp,
        'previous_winner_key': winner.get('key'),
        'previous_winner_display_name': winner.get('display_name')
    })

    draw_info['winner'] = None
    draw_info['winner_timestamp'] = None
    draw_info['selected_by'] = None
    draw_info['method'] = None
    draw_info['finalized'] = False
    draw_info['finalized_at'] = None
    draw_info['finalized_by'] = None
    draw_info['override'] = False
    draw_info['tickets_at_selection'] = None
    draw_info['probability_at_selection'] = None
    draw_info['eligible_pool_size'] = None

    save_session_data()

    updated_summary, _ = get_ticket_summary_for_session(session_id)
    return jsonify({
        'status': 'success',
        'reset': True,
        'draw_info': serialize_draw_info(draw_info),
        'summary': updated_summary
    }), 200


@recorder_bp.route('/session/<session_id>/draw/override', methods=['POST'])
def override_draw(session_id):
    """Allow a super admin to override the draw winner."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    ensure_session_structure(session_info)

    if session_info.get('is_discarded'):
        return jsonify({'error': 'Session is discarded from draw calculations'}), 400

    student_records_count = len(session_info.get('clean_records', [])) + len(session_info.get('red_records', []))
    if student_records_count <= 0:
        return jsonify({'error': 'No student records available for this session'}), 400

    data = request.get_json(silent=True) or {}
    summary, _ = get_ticket_summary_for_session(session_id)
    if not summary:
        return jsonify({'error': 'Unable to load draw summary for this session'}), 400

    candidates = summary.get('candidates') or []
    tickets_snapshot = summary.get('tickets_snapshot') or {}
    profiles = summary.get('profiles') or {}

    all_profiles = {}
    for key, profile in profiles.items():
        if isinstance(profile, dict):
            copied = profile.copy()
            copied.setdefault('key', key)
            copied.setdefault('display_name', format_display_name(copied))
            all_profiles[key] = copied

    for record in session_info.get('clean_records', []):
        profile = build_profile_from_record(record)
        key = profile.get('key')
        if key and key not in all_profiles:
            all_profiles[key] = profile

    for record in session_info.get('red_records', []):
        profile = build_profile_from_record(record)
        key = profile.get('key')
        if key and key not in all_profiles:
            all_profiles[key] = profile

    for key, info in student_lookup.items():
        if key not in all_profiles:
            profile = info.copy()
            profile['key'] = key
            profile['display_name'] = format_display_name(profile)
            all_profiles[key] = profile

    override_key = data.get('student_key')
    student_id = str(data.get('student_id', '')).strip()
    input_value = str(data.get('input_value', '')).strip()
    preferred = data.get('preferred_name')
    last = data.get('last_name')

    if not override_key and student_id:
        normalized_id = student_id.lower()
        match = next(
            (
                profile
                for profile in all_profiles.values()
                if str(profile.get('student_id', '')).strip().lower() == normalized_id
            ),
            None
        )
        if match:
            override_key = match.get('key')

    if not override_key and input_value:
        normalized_input = input_value.lower()
        match = next(
            (
                profile
                for profile in all_profiles.values()
                if (profile.get('display_name') or '').lower() == normalized_input
            ),
            None
        )
        if not match and input_value.isdigit():
            match = next(
                (
                    profile
                    for profile in all_profiles.values()
                    if str(profile.get('student_id', '')).strip() == input_value
                ),
                None
            )
        if match:
            override_key = match.get('key')

    if not override_key and preferred and last:
        override_key = make_student_key(preferred, last)

    if not override_key:
        return jsonify({'error': 'Unable to determine the override candidate from the provided input'}), 400

    if override_key not in all_profiles:
        return jsonify({'error': 'Specified student was not found in the uploaded CSV'}), 400

    profile = all_profiles.get(override_key, {}).copy()
    if not profile:
        preferred, last = split_student_key(override_key)
        profile = {
            'preferred_name': preferred.title(),
            'last_name': last.title(),
            'grade': '',
            'advisor': '',
            'house': '',
            'clan': '',
            'student_id': ''
        }
    display_name = profile.get('display_name') or format_display_name(profile)
    winner_tickets = tickets_snapshot.get(override_key, 0.0)
    total_tickets = summary.get('total_tickets', 0.0)
    probability = (winner_tickets / total_tickets * 100.0) if total_tickets > 0 else 0.0

    winner_data = {
        'key': override_key,
        'preferred_name': profile.get('preferred_name', ''),
        'last_name': profile.get('last_name', ''),
        'display_name': display_name,
        'grade': profile.get('grade', ''),
        'advisor': profile.get('advisor', ''),
        'house': profile.get('house', ''),
        'clan': profile.get('clan', ''),
        'student_id': profile.get('student_id', ''),
        'tickets': winner_tickets,
        'probability': probability
    }

    timestamp = datetime.now().isoformat()
    draw_info = session_info['draw_info']
    draw_info['winner'] = winner_data
    draw_info['winner_timestamp'] = timestamp
    draw_info['selected_by'] = session.get('user_id')
    draw_info['method'] = 'random'
    draw_info['finalized'] = True
    draw_info['finalized_at'] = timestamp
    draw_info['finalized_by'] = session.get('user_id')
    draw_info['override'] = True
    draw_info['tickets_at_selection'] = summary.get('total_tickets', 0.0)
    draw_info['probability_at_selection'] = probability
    draw_info['eligible_pool_size'] = summary.get('eligible_count', 0)

    draw_info['history'].append({
        'action': 'override',
        'performed_by': session.get('user_id'),
        'timestamp': timestamp,
        'winner_key': override_key,
        'winner_display_name': display_name,
        'winner_tickets': winner_tickets,
        'probability': probability
    })

    save_session_data()

    updated_summary, _ = get_ticket_summary_for_session(session_id)
    return jsonify({
        'status': 'success',
        'override': True,
        'winner': winner_data,
        'draw_info': serialize_draw_info(draw_info),
        'summary': updated_summary
    }), 200


@recorder_bp.route('/session/<session_id>/draw/discard', methods=['POST'])
def toggle_discard(session_id):
    """Toggle whether a session is included in ticket calculations."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404

    session_info = session_data[session_id]
    ensure_session_structure(session_info)

    data = request.get_json(silent=True) or {}
    discard = bool(data.get('discarded'))

    timestamp = datetime.now().isoformat()
    message = 'Session state unchanged'
    if session_info.get('is_discarded') != discard:
        session_info['is_discarded'] = discard
        metadata = session_info.get('discard_metadata')
        if not isinstance(metadata, dict):
            metadata = {}
        if discard:
            metadata['discarded_by'] = session.get('user_id')
            metadata['discarded_at'] = timestamp
            message = 'Session discarded from draw calculations'
        else:
            metadata['restored_by'] = session.get('user_id')
            metadata['restored_at'] = timestamp
            message = 'Session reinstated for draw calculations'
        session_info['discard_metadata'] = metadata
        session_info['draw_info']['history'].append({
            'action': 'session_discarded' if discard else 'session_restored',
            'performed_by': session.get('user_id'),
            'timestamp': timestamp
        })
        save_session_data()

    summary, _ = get_ticket_summary_for_session(session_id)
    return jsonify({
        'status': 'success',
        'discarded': session_info.get('is_discarded', False),
        'message': message,
        'draw_info': serialize_draw_info(session_info.get('draw_info', {})),
        'summary': summary,
        'discard_metadata': session_info.get('discard_metadata', {})
    }), 200


@recorder_bp.route('/admin/overview', methods=['GET'])
def admin_overview():
    """Get admin overview data"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    # Get all users
    users = []
    for username, user_data in users_db.items():
        users.append({
            'username': username,
            'name': user_data['name'],
            'role': user_data['role']
        })
    
    # Get all sessions
    sessions = []
    for session_id, session_info in session_data.items():
        ensure_session_structure(session_info)
        total_records = len(session_info['clean_records']) + get_dirty_count(session_info) + len(session_info['red_records'])
        sessions.append({
            'session_id': session_id,
            'session_name': session_info['session_name'],
            'owner': session_info['owner'],
            'total_records': total_records,
            'created_at': session_info['created_at'],
            'faculty_clean_count': len(session_info.get('faculty_clean_records', [])),
            'is_discarded': session_info.get('is_discarded', False),
            'draw_info': serialize_draw_info(session_info.get('draw_info', {}))
        })
    
    return jsonify({
        'users': users,
        'sessions': sessions
    }), 200


@recorder_bp.route('/session/scan-history', methods=['GET'])
def get_scan_history():
    """Get scan history for current session"""
    if not require_auth_or_guest():
        return jsonify({'error': 'Authentication or guest access required'}), 401
    
    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400

    session_id = session['session_id']
    data = session_data[session_id]
    ensure_session_structure(data)

    # Format scan history for display
    formatted_history = []
    for record in data['scan_history']:
        name = (record.get('display_name') or '').strip()
        if not name:
            preferred = (record.get('preferred_name') or record.get('first_name', '') or '').strip()
            last = (record.get('last_name') or '').strip()
            name = f"{preferred} {last}".strip()

        category = record.get('category', '').lower()
        if not name:
            if category == 'dirty':
                name = 'Dirty Plate'
            elif category == 'faculty':
                name = 'Faculty Clean Plate'

        formatted_history.append({
            'timestamp': record.get('timestamp'),
            'name': name,
            'category': category.upper(),
            'is_manual_entry': record.get('is_manual_entry', False)
        })
    
    # Sort by timestamp (most recent first)
    formatted_history.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({
        'scan_history': formatted_history
    }), 200


@recorder_bp.route('/superadmin/change-role', methods=['POST'])
def change_user_role():
    """Change user role (super admin only)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    current_user = users_db.get(session['user_id'])
    if not current_user or current_user['role'] != 'superadmin':
        return jsonify({'error': 'Super admin access required'}), 403
    
    data = request.get_json()
    target_username = data.get('username')
    new_role = data.get('role')
    
    if not target_username or not new_role:
        return jsonify({'error': 'Username and role are required'}), 400
    
    if new_role not in ['user', 'admin', 'superadmin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    # Cannot change own role
    if target_username == session['user_id']:
        return jsonify({'error': 'Cannot change your own role'}), 400
    
    if target_username not in users_db:
        return jsonify({'error': 'User not found'}), 404
    
    users_db[target_username]['role'] = new_role
    save_users_db()
    
    return jsonify({
        'status': 'success',
        'message': f'User role changed to {new_role} successfully'
    }), 200

@recorder_bp.route('/superadmin/delete-account', methods=['POST'])
def delete_user_account():
    """Delete user account (super admin only)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    current_user = users_db.get(session['user_id'])
    if not current_user or current_user['role'] != 'superadmin':
        return jsonify({'error': 'Super admin access required'}), 403
    
    data = request.get_json()
    target_username = data.get('username')
    
    if not target_username:
        return jsonify({'error': 'Username is required'}), 400
    
    # Cannot delete own account
    if target_username == session['user_id']:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    if target_username not in users_db:
        return jsonify({'error': 'User not found'}), 404
    
    # Delete user account
    del users_db[target_username]
    save_users_db()
    
    # Clean up user's CSV data file
    user_csv_file = f"user_csv_{target_username}.json"
    if os.path.exists(user_csv_file):
        os.remove(user_csv_file)
    
    # Remove user's sessions
    sessions_to_remove = []
    for session_id, session_info in session_data.items():
        if session_info.get('owner') == target_username:
            sessions_to_remove.append(session_id)
    
    for session_id in sessions_to_remove:
        del session_data[session_id]
    save_session_data()
    
    return jsonify({
        'status': 'success',
        'message': 'User account deleted successfully'
    }), 200

