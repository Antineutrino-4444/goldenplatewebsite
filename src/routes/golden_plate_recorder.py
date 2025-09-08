from flask import Blueprint, request, jsonify, session, render_template
from datetime import datetime
import uuid
import csv
import io
import os
import json

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
GLOBAL_CSV_FILE = os.path.join(DATA_DIR, "global_csv.json")

print(f"Persistent storage directory: {DATA_DIR}")

def load_data_from_file(file_path, default_data):
    """Load data from file or return default if file doesn't exist"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                print(f"Successfully loaded data from {file_path}")
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
global_csv_data = load_data_from_file(GLOBAL_CSV_FILE, None)
delete_requests = load_data_from_file(DELETE_REQUESTS_FILE, [])

# Initialize users database with default users if file doesn't exist
default_users = {
    'antineutrino': {'password': 'b-decay', 'role': 'superadmin', 'name': 'Super Administrator', 'status': 'active'}
}
users_db = load_data_from_file(USERS_FILE, default_users)

# Save initial data to ensure files are created
print("Saving initial data...")
save_data_to_file(SESSIONS_FILE, session_data)
save_data_to_file(USERS_FILE, users_db)
save_data_to_file(DELETE_REQUESTS_FILE, delete_requests)
if global_csv_data is not None:
    save_data_to_file(GLOBAL_CSV_FILE, global_csv_data)

print(f"Initialization complete. Session count: {len(session_data)}, Users: {len(users_db)}")

def save_all_data():
    """Save all data to files"""
    try:
        save_data_to_file(SESSIONS_FILE, session_data)
        save_data_to_file(USERS_FILE, users_db)
        save_data_to_file(DELETE_REQUESTS_FILE, delete_requests)
        if global_csv_data is not None:
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

def save_global_csv():
    """Save global CSV data to file"""
    if global_csv_data is not None:
        return save_data_to_file(GLOBAL_CSV_FILE, global_csv_data)
    return True

def get_current_user():
    """Get current logged in user"""
    if 'user_id' in session:
        return users_db.get(session['user_id'])
    return None

def require_auth():
    """Check if user is authenticated"""
    return 'user_id' in session and session['user_id'] in users_db

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
        
        # Load user's CSV data if exists
        user_csv_file = f"user_csv_{username}.json"
        if os.path.exists(user_csv_file):
            import json
            with open(user_csv_file, 'r') as f:
                global global_csv_data
                global_csv_data = json.load(f)
        
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
    # Save user's CSV data before logout
    if 'user_id' in session and global_csv_data:
        user_csv_file = f"user_csv_{session['user_id']}.json"
        import json
        with open(user_csv_file, 'w') as f:
            json.dump(global_csv_data, f)
    
    session.pop('user_id', None)
    session.pop('session_id', None)
    return jsonify({'status': 'success', 'message': 'Logged out successfully'}), 200

@recorder_bp.route('/auth/signup', methods=['POST'])
def signup():
    """User signup"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    
    # Validation
    if not username or not password or not name:
        return jsonify({'error': 'Username, password, and name are required'}), 400
    
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters long'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400
    
    if username in users_db:
        return jsonify({'error': 'Username already exists'}), 409
    
    # Create new user
    users_db[username] = {
        'password': password,
        'role': 'user',
        'name': name,
        'status': 'active'
    }
    
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
    """Request session deletion (for normal users)"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    current_user = get_current_user()
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'Session ID is required'}), 400
    
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    # Check if user owns the session
    if session_data[session_id]['owner'] != session['user_id']:
        return jsonify({'error': 'You can only request deletion of your own sessions'}), 403
    
    # If user is admin or super admin, delete immediately
    if current_user['role'] in ['admin', 'superadmin']:
        del session_data[session_id]
        save_session_data()
        return jsonify({
            'status': 'success',
            'message': 'Session deleted successfully'
        }), 200
    
    # For normal users, add to delete requests
    delete_request = {
        'id': str(uuid.uuid4()),
        'session_id': session_id,
        'session_name': session_data[session_id]['name'],
        'requester': session['user_id'],
        'requester_name': current_user['name'],
        'requested_at': datetime.now().isoformat()
    }
    
    delete_requests.append(delete_request)
    
    # Save delete requests to file
    save_delete_requests()
    
    return jsonify({
        'status': 'success',
        'message': 'Delete request submitted. An administrator will review your request.'
    }), 200

@recorder_bp.route('/admin/delete-requests', methods=['GET'])
def get_delete_requests():
    """Get pending delete requests (admin/super admin only)"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    return jsonify({
        'status': 'success',
        'requests': delete_requests
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

@recorder_bp.route('/admin/sessions', methods=['GET'])
def admin_get_all_sessions():
    """Admin: Get all sessions from all users"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    all_sessions = []
    for session_id, data in session_data.items():
        total_records = len(data['clean_records']) + len(data['dirty_records']) + len(data['red_records'])
        all_sessions.append({
            'session_id': session_id,
            'session_name': data['session_name'],
            'owner': data.get('owner', 'unknown'),
            'created_at': data.get('created_at', 'unknown'),
            'total_records': total_records,
            'clean_count': len(data['clean_records']),
            'dirty_count': len(data['dirty_records']),
            'red_count': len(data['red_records'])
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
    
    data = request.get_json() or {}
    custom_name = data.get('session_name', '').strip()
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Generate session name
    if custom_name:
        session_name = custom_name
    else:
        now = datetime.now()
        session_name = f"Golden_Plate_{now.strftime('%B_%d_%Y')}"
    
    # Create session data with owner information
    session_data[session_id] = {
        'session_name': session_name,
        'owner': session['user_id'],
        'created_at': datetime.now().isoformat(),
        'clean_records': [],
        'dirty_records': [],
        'red_records': [],
        'scan_history': []
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
    """List all sessions (shared among all users)"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    user_sessions = []
    for session_id, data in session_data.items():
        # All users can see all sessions
        total_records = len(data['clean_records']) + len(data['dirty_records']) + len(data['red_records'])
        clean_count = len(data['clean_records'])
        dirty_count = len(data['dirty_records']) + len(data['red_records'])  # Combine dirty + very dirty
        
        # Calculate percentages
        clean_percentage = (clean_count / total_records * 100) if total_records > 0 else 0
        dirty_percentage = (dirty_count / total_records * 100) if total_records > 0 else 0
        
        user_sessions.append({
            'session_id': session_id,
            'session_name': data['session_name'],
            'total_records': total_records,
            'clean_count': clean_count,
            'dirty_count': dirty_count,
            'clean_percentage': round(clean_percentage, 1),
            'dirty_percentage': round(dirty_percentage, 1)
        })
    
    return jsonify({
        'sessions': user_sessions,
        'has_global_csv': global_csv_data is not None
    }), 200

@recorder_bp.route('/session/switch/<session_id>', methods=['POST'])
def switch_session(session_id):
    """Switch to a different session (all sessions are shared)"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    # All users can access any session
    session['session_id'] = session_id
    
    return jsonify({
        'session_id': session_id,
        'session_name': session_data[session_id]['session_name']
    }), 200

@recorder_bp.route('/session/delete/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session or request deletion"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    user = get_current_user()
    
    # Check if trying to delete the current active session
    current_session_id = session.get('session_id')
    if session_id == current_session_id:
        return jsonify({'error': 'Cannot delete the currently active session. Switch to another session first.'}), 400
    
    # Admins and super admins can delete directly
    if user['role'] in ['admin', 'superadmin']:
        session_name = session_data[session_id]['session_name']
        del session_data[session_id]
        save_session_data()
        
        return jsonify({
            'status': 'success',
            'message': f'Session "{session_name}" deleted successfully by {user["role"]}',
            'deleted_session_id': session_id
        }), 200
    
    # Regular users send delete requests
    else:
        session_name = session_data[session_id]['session_name']
        
        # Check if request already exists
        existing_request = next((req for req in delete_requests if req['session_id'] == session_id and req['status'] == 'pending'), None)
        if existing_request:
            return jsonify({'error': 'Delete request already pending for this session'}), 400
        
        # Create delete request
        delete_request = {
            'id': str(uuid.uuid4()),
            'session_id': session_id,
            'session_name': session_name,
            'requested_by': session['user_id'],
            'requested_by_name': user['name'],
            'requested_at': datetime.now().isoformat(),
            'status': 'pending',
            'reason': 'User requested deletion'
        }
        
        delete_requests.append(delete_request)
        save_delete_requests()
        
        return jsonify({
            'status': 'request_sent',
            'message': f'Delete request sent for session "{session_name}". Awaiting admin approval.',
            'request_id': delete_request['id']
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

@recorder_bp.route('/admin/delete-requests/<request_id>/reject', methods=['POST'])
def reject_delete_request(request_id):
    """Reject a delete request (admin/superadmin only)"""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json() or {}
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

# Global CSV data storage
global_csv_data = None

@recorder_bp.route('/csv/upload', methods=['POST'])
def upload_csv():
    """Upload CSV file (requires authentication)"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    global global_csv_data
    
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
        required_columns = ['Last', 'First', 'Student ID']
        if not all(col in csv_reader.fieldnames for col in required_columns):
            return jsonify({'error': f'CSV must contain columns: {", ".join(required_columns)}'}), 400
        
        # Store globally (applies to all sessions)
        global_csv_data = {
            'data': rows,
            'columns': csv_reader.fieldnames,
            'uploaded_by': session['user_id'],
            'uploaded_at': datetime.now().isoformat()
        }
        
        # Save global CSV data to file
        save_global_csv()
        
        return jsonify({
            'status': 'success',
            'rows_count': len(rows),
            'columns': csv_reader.fieldnames,
            'uploaded_by': session['user_id']
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error processing CSV: {str(e)}'}), 400

@recorder_bp.route('/csv/preview', methods=['GET'])
def preview_csv():
    """Preview the current student database"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    global global_csv_data
    
    if not global_csv_data:
        return jsonify({
            'status': 'no_data',
            'message': 'No student database uploaded yet'
        }), 200
    
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    # Calculate pagination
    total_records = len(global_csv_data['data'])
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Get paginated data
    paginated_data = global_csv_data['data'][start_idx:end_idx]
    
    return jsonify({
        'status': 'success',
        'data': paginated_data,
        'columns': global_csv_data['columns'],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_records': total_records,
            'total_pages': (total_records + per_page - 1) // per_page,
            'has_next': end_idx < total_records,
            'has_prev': page > 1
        },
        'metadata': {
            'uploaded_by': global_csv_data.get('uploaded_by', 'unknown'),
            'uploaded_at': global_csv_data.get('uploaded_at', 'unknown')
        }
    }), 200

@recorder_bp.route('/record/<category>', methods=['POST'])
def record_student(category):
    """Record a student in a category"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400
    
    if category not in ['clean', 'dirty', 'red']:
        return jsonify({'error': 'Invalid category'}), 400
    
    data = request.get_json()
    input_value = data.get('input_value', '').strip()
    
    if not input_value:
        return jsonify({'error': 'Student ID or Name is required'}), 400
    
    session_id = session['session_id']
    session_info = session_data[session_id]
    
    # Determine if input is ID or name
    student_record = None
    is_manual_entry = False
    student_id = None
    first_name = ""
    last_name = ""
    
    # First, try to find by Student ID in CSV
    if global_csv_data and global_csv_data['data']:
        for row in global_csv_data['data']:
            if str(row.get('Student ID', '')).strip() == input_value:
                student_record = row
                student_id = input_value
                first_name = row.get('First', '')
                last_name = row.get('Last', '')
                break
    
    # If not found by ID, try to find by name
    if not student_record and global_csv_data and global_csv_data['data']:
        # Parse input as "First Last"
        name_parts = input_value.split()
        if len(name_parts) >= 2:
            input_first = name_parts[0].lower()
            input_last = ' '.join(name_parts[1:]).lower()
            
            for row in global_csv_data['data']:
                csv_first = str(row.get('First', '')).strip().lower()
                csv_last = str(row.get('Last', '')).strip().lower()
                
                if csv_first == input_first and csv_last == input_last:
                    student_record = row
                    student_id = str(row.get('Student ID', ''))
                    first_name = row.get('First', '')
                    last_name = row.get('Last', '')
                    break
    
    # If still not found, create manual entry
    if not student_record:
        is_manual_entry = True
        student_id = "Manual Input"
        
        # Parse name from input
        name_parts = input_value.split()
        if len(name_parts) >= 2:
            first_name = name_parts[0].capitalize()
            last_name = ' '.join(name_parts[1:]).capitalize()
        elif len(name_parts) == 1:
            first_name = name_parts[0].capitalize()
            last_name = ""
        else:
            first_name = input_value.capitalize()
            last_name = ""
    
    # Check for duplicate entries in current session
    all_records = session_info['clean_records'] + session_info['dirty_records'] + session_info['red_records']
    
    # For manual entries, check by name; for CSV entries, check by student_id
    if is_manual_entry:
        duplicate_check = any(
            record.get('first_name', '').lower() == first_name.lower() and 
            record.get('last_name', '').lower() == last_name.lower() and
            record.get('student_id') == "Manual Input"
            for record in all_records
        )
    else:
        duplicate_check = any(record.get('student_id') == student_id for record in all_records)
    
    if duplicate_check:
        existing_category = None
        for cat in ['clean', 'dirty', 'red']:
            if is_manual_entry:
                if any(
                    record.get('first_name', '').lower() == first_name.lower() and 
                    record.get('last_name', '').lower() == last_name.lower() and
                    record.get('student_id') == "Manual Input"
                    for record in session_info[f'{cat}_records']
                ):
                    existing_category = cat
                    break
            else:
                if any(record.get('student_id') == student_id for record in session_info[f'{cat}_records']):
                    existing_category = cat
                    break
        
        return jsonify({
            'error': 'duplicate',
            'message': f'Student already recorded as {existing_category.upper()} in this session'
        }), 409
    
    # Create record
    record = {
        'student_id': student_id,
        'first_name': first_name,
        'last_name': last_name,
        'category': category,
        'timestamp': datetime.now().isoformat(),
        'recorded_by': session['user_id'],
        'is_manual_entry': is_manual_entry
    }
    
    # Add to appropriate category
    session_info[f'{category}_records'].append(record)
    session_info['scan_history'].append(record)
    
    # Save session data to file
    save_session_data()
    
    return jsonify({
        'status': 'success',
        'first_name': first_name,
        'last_name': last_name,
        'student_id': student_id,
        'category': category,
        'is_manual_entry': is_manual_entry,
        'recorded_by': session['user_id']
    }), 200

@recorder_bp.route('/session/status', methods=['GET'])
def get_session_status():
    """Get current session status with percentage calculations"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    data = session_data[session_id]
    
    clean_count = len(data['clean_records'])
    dirty_count = len(data['dirty_records'])
    red_count = len(data['red_records'])
    combined_dirty_count = dirty_count + red_count  # Combine dirty + very dirty
    total_recorded = clean_count + dirty_count + red_count
    
    # Calculate percentages
    clean_percentage = (clean_count / total_recorded * 100) if total_recorded > 0 else 0
    dirty_percentage = (combined_dirty_count / total_recorded * 100) if total_recorded > 0 else 0
    
    return jsonify({
        'session_id': session_id,
        'session_name': data['session_name'],
        'clean_count': clean_count,
        'dirty_count': dirty_count,
        'red_count': red_count,
        'combined_dirty_count': combined_dirty_count,
        'total_recorded': total_recorded,
        'clean_percentage': round(clean_percentage, 1),
        'dirty_percentage': round(dirty_percentage, 1),
        'scan_history_count': len(data['scan_history'])
    }), 200

@recorder_bp.route('/session/history', methods=['GET'])
def get_session_history():
    """Get scan history for current session"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    data = session_data[session_id]
    
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
    
    # Create CSV content with three columns
    output = io.StringIO()
    
    # Write header
    output.write("CLEAN,DIRTY,RED\n")
    
    # Get all records for each category
    clean_names = [f"{record['first_name']} {record['last_name']}" for record in data['clean_records']]
    dirty_names = [f"{record['first_name']} {record['last_name']}" for record in data['dirty_records']]
    red_names = [f"{record['first_name']} {record['last_name']}" for record in data['red_records']]
    
    # Find the maximum number of records to determine how many rows we need
    max_records = max(len(clean_names), len(dirty_names), len(red_names))
    
    # Write data rows
    for i in range(max_records):
        clean_name = clean_names[i] if i < len(clean_names) else ""
        dirty_name = dirty_names[i] if i < len(dirty_names) else ""
        red_name = red_names[i] if i < len(red_names) else ""
        
        output.write(f'"{clean_name}","{dirty_name}","{red_name}"\n')
    
    csv_content = output.getvalue()
    output.close()
    
    from flask import Response
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{data["session_name"]}_records.csv"'}
    )


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
        total_records = len(session_info['clean_records']) + len(session_info['dirty_records']) + len(session_info['red_records'])
        sessions.append({
            'session_id': session_id,
            'session_name': session_info['session_name'],
            'owner': session_info['owner'],
            'total_records': total_records,
            'created_at': session_info['created_at']
        })
    
    return jsonify({
        'users': users,
        'sessions': sessions
    }), 200


@recorder_bp.route('/session/scan-history', methods=['GET'])
def get_scan_history():
    """Get scan history for current session"""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    if 'session_id' not in session or session['session_id'] not in session_data:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    data = session_data[session_id]
    
    # Format scan history for display
    formatted_history = []
    for record in data['scan_history']:
        formatted_history.append({
            'timestamp': record['timestamp'],
            'name': f"{record['first_name']} {record['last_name']}".strip(),
            'student_id': record['student_id'],
            'category': record['category'].upper(),
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

