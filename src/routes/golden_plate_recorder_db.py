from flask import Blueprint, request, jsonify, session
from datetime import datetime
import uuid
import csv
import io
import os
import json
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

recorder_bp = Blueprint('recorder', __name__)

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///data/golden_plate_recorder.db')
engine = create_engine(DATABASE_URL)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password = Column(String(120), nullable=False)
    role = Column(String(20), nullable=False, default='user')
    name = Column(String(120), nullable=False)
    status = Column(String(20), nullable=False, default='active')
    created_at = Column(DateTime, default=datetime.utcnow)

class Session(Base):
    __tablename__ = 'sessions'
    
    id = Column(String(36), primary_key=True)
    name = Column(String(200), nullable=False)
    user_id = Column(String(80), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    records = Column(Text)  # JSON string of records
class DeleteRequest(Base):
    __tablename__ = 'delete_requests'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(36), nullable=False)
    session_name = Column(String(200), nullable=False)
    requester = Column(String(80), nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize default users if they don't exist
def init_default_users():
    existing_users = db_session.query(User).count()
    if existing_users == 0:
        default_users = [
            User(
                username='antineutrino',
                password='b-decay',
                role='superadmin',
                name='Super Administrator',
                status='active'
            )
        ]
        for user in default_users:
            db_session.add(user)
        db_session.commit()
        print("Default users created")

# Initialize on import
init_default_users()

def get_current_user():
    """Get current logged in user"""
    if 'user_id' in session:
        return db_session.query(User).filter_by(username=session['user_id']).first()
    return None

def require_auth():
    """Check if user is authenticated"""
    return 'user_id' in session and db_session.query(User).filter_by(username=session['user_id']).first() is not None

def require_admin():
    """Check if user is admin or super admin"""
    user = get_current_user()
    return user and user.role in ['admin', 'superadmin']

def require_superadmin():
    """Check if user is super admin"""
    user = get_current_user()
    return user and user.role == 'superadmin'

@recorder_bp.route('/auth/login', methods=['POST'])
def login():
    """User login"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    user = db_session.query(User).filter_by(username=username, password=password).first()
    if user:
        # Check account status
        if user.status != 'active':
            return jsonify({'success': False, 'message': 'Account is disabled. Contact administrator.'}), 403
        
        session['user_id'] = username
        
        return jsonify({
            'success': True, 
            'user': {
                'username': user.username,
                'name': user.name,
                'role': user.role
            }
        })
    
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@recorder_bp.route('/auth/logout', methods=['POST'])
def logout():
    """User logout"""
    if 'user_id' in session:
        session.clear()

    return jsonify({'success': True})

@recorder_bp.route('/auth/signup', methods=['POST'])
def signup():
    """User registration"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    
    if not username or not password or not name:
        return jsonify({'success': False, 'message': 'All fields are required'}), 400
    
    # Check if user already exists
    existing_user = db_session.query(User).filter_by(username=username).first()
    if existing_user:
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    
    # Create new user
    new_user = User(username=username, password=password, name=name, role='user', status='active')
    db_session.add(new_user)
    db_session.commit()
    
    return jsonify({'success': True, 'message': 'Account created successfully'})

@recorder_bp.route('/sessions/create', methods=['POST'])
def create_session():
    """Create a new session"""
    if not require_auth():
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    data = request.get_json()
    session_name = data.get('name', '').strip()
    
    if not session_name:
        # Generate default name
        now = datetime.now()
        session_name = f"Golden_Plate_{now.strftime('%B_%d_%Y')}"
    
    session_id = str(uuid.uuid4())
    user_id = session['user_id']
    
    # Create session in database
    new_session = Session(
        id=session_id,
        name=session_name,
        user_id=user_id,
        records=json.dumps({'clean': [], 'dirty': [], 'red': []})
    )
    db_session.add(new_session)
    db_session.commit()
    
    # Set as current session
    session['current_session'] = session_id
    
    return jsonify({
        'success': True,
        'session': {
            'id': session_id,
            'name': session_name,
            'records': {'clean': [], 'dirty': [], 'red': []}
        }
    })

@recorder_bp.route('/sessions/list', methods=['GET'])
def list_sessions():
    """List user's sessions"""
    if not require_auth():
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    user_id = session['user_id']
    user = get_current_user()
    
    if user.role in ['admin', 'superadmin']:
        # Admins can see all sessions
        sessions = db_session.query(Session).all()
    else:
        # Regular users see only their sessions
        sessions = db_session.query(Session).filter_by(user_id=user_id).all()
    
    session_list = []
    for sess in sessions:
        records = json.loads(sess.records)
        total_records = len(records['clean']) + len(records['dirty']) + len(records['red'])
        session_list.append({
            'id': sess.id,
            'name': sess.name,
            'user_id': sess.user_id,
            'created_at': sess.created_at.isoformat(),
            'total_records': total_records
        })
    
    return jsonify({'success': True, 'sessions': session_list})

@recorder_bp.route('/sessions/switch', methods=['POST'])
def switch_session():
    """Switch to a different session"""
    if not require_auth():
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    data = request.get_json()
    session_id = data.get('session_id')
    
    # Get session from database
    sess = db_session.query(Session).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'success': False, 'message': 'Session not found'}), 404
    
    user = get_current_user()
    # Check permissions
    if user.role not in ['admin', 'superadmin'] and sess.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    session['current_session'] = session_id
    records = json.loads(sess.records)
    
    return jsonify({
        'success': True,
        'session': {
            'id': sess.id,
            'name': sess.name,
            'records': records
        }
    })

@recorder_bp.route('/sessions/delete', methods=['POST'])
def delete_session():
    """Delete a session directly"""
    if not require_auth():
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    data = request.get_json()
    session_id = data.get('session_id')
    
    sess = db_session.query(Session).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'success': False, 'message': 'Session not found'}), 404
    
    # Get current user
    current_user = get_current_user()
    
    # Permission check: users can only delete their own sessions, admins and super admins can delete any session
    if current_user.role == 'user' and sess.user_id != current_user.username:
        return jsonify({'success': False, 'message': 'You can only delete sessions that you created'}), 403
    
    # Delete the session
    db_session.delete(sess)
    db_session.commit()
    
    # Clear current session if it was deleted
    if session.get('current_session') == session_id:
        session.pop('current_session', None)
    
    return jsonify({'success': True, 'message': 'Session deleted successfully'})

@recorder_bp.route('/csv/upload', methods=['POST'])
def upload_csv():
    """Upload CSV file"""
    if not require_auth():
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    try:
        # Read and parse CSV
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)

        required_columns = ['Student ID', 'Last', 'Preferred', 'Grade', 'Advisor', 'House', 'Clan']
        if not all(col in csv_reader.fieldnames for col in required_columns):
            return jsonify({'success': False, 'message': f'CSV must contain columns: {", ".join(required_columns)}'}), 400

        csv_data = []
        for row in csv_reader:
            student_id = str(row.get('Student ID', '') or '').strip()
            if not student_id:
                continue

            csv_data.append({
                'student_id': student_id,
                'last': str(row.get('Last', '') or '').strip(),
                'preferred': str(row.get('Preferred', '') or '').strip(),
                'grade': str(row.get('Grade', '') or '').strip(),
                'advisor': str(row.get('Advisor', '') or '').strip(),
                'house': str(row.get('House', '') or '').strip(),
                'clan': str(row.get('Clan', '') or '').strip()
            })

        if not csv_data:
            return jsonify({'success': False, 'message': 'No valid data found in CSV'}), 400

        # Store in session for immediate use
        session['global_csv_data'] = csv_data
        
        return jsonify({
            'success': True,
            'message': f'{len(csv_data)} students loaded successfully',
            'count': len(csv_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing CSV: {str(e)}'}), 400

@recorder_bp.route('/record', methods=['POST'])
def record_student():
    """Record a student in a category"""
    if not require_auth():
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    if 'current_session' not in session:
        return jsonify({'success': False, 'message': 'No active session'}), 400
    
    data = request.get_json()
    input_value = data.get('input', '').strip()
    category = data.get('category', '').lower()
    
    if not input_value or category not in ['clean', 'dirty', 'red']:
        return jsonify({'success': False, 'message': 'Invalid input or category'}), 400
    
    # Get current session
    session_id = session['current_session']
    sess = db_session.query(Session).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'success': False, 'message': 'Session not found'}), 404
    
    records = json.loads(sess.records)
    csv_data = session.get('global_csv_data', [])

    # Determine display name from input
    student_found = None
    display_name = input_value
    preferred_name = ""
    last_name = ""
    grade = ""
    advisor = ""
    house = ""
    clan = ""
    is_manual_entry = False

    if csv_data:
        # Search by ID first
        for student in csv_data:
            if student.get('student_id') == input_value:
                student_found = student
                break

        # If not found by ID, try by name
        if not student_found:
            input_lower = input_value.lower()
            for student in csv_data:
                preferred = str(student.get('preferred', '') or '').strip()
                last = str(student.get('last', '') or '').strip()
                full_name = f"{preferred} {last}".strip().lower()
                if full_name == input_lower:
                    student_found = student
                    break

    if student_found:
        preferred_name = str(student_found.get('preferred', '') or '').strip()
        last_name = str(student_found.get('last', '') or '').strip()
        grade = str(student_found.get('grade', '') or '').strip()
        advisor = str(student_found.get('advisor', '') or '').strip()
        house = str(student_found.get('house', '') or '').strip()
        clan = str(student_found.get('clan', '') or '').strip()
        display_name = f"{preferred_name} {last_name}".strip() or input_value
    else:
        is_manual_entry = True
        name_parts = input_value.split()
        if len(name_parts) >= 2:
            preferred_name = name_parts[0].capitalize()
            last_name = ' '.join(name_parts[1:]).capitalize()
        elif len(name_parts) == 1:
            preferred_name = name_parts[0].capitalize()
            last_name = ''
        else:
            preferred_name = input_value.capitalize()
            last_name = ''
        display_name = f"{preferred_name} {last_name}".strip() or input_value.capitalize()

    # Check for duplicates by name
    for cat_records in records.values():
        for record in cat_records:
            if record.get('name', '').lower() == display_name.lower():
                return jsonify({'success': False, 'message': 'Student already recorded in this session'}), 400

    # Create record
    record = {
        'name': display_name,
        'preferred': preferred_name,
        'last': last_name,
        'grade': grade,
        'advisor': advisor,
        'house': house,
        'clan': clan,
        'is_manual_entry': is_manual_entry,
        'timestamp': datetime.now().isoformat(),
        'recorded_by': session['user_id'],
        'category': category
    }
    message = f"{display_name} recorded as {category.upper()}"

    # Add to records
    records[category].append(record)
    
    # Save to database
    sess.records = json.dumps(records)
    db_session.commit()
    
    return jsonify({
        'success': True,
        'message': message,
        'record': record,
        'records': records
    })

@recorder_bp.route('/export', methods=['GET'])
def export_csv():
    """Export session records as CSV"""
    if not require_auth():
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    if 'current_session' not in session:
        return jsonify({'success': False, 'message': 'No active session'}), 400
    
    session_id = session['current_session']
    sess = db_session.query(Session).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'success': False, 'message': 'Session not found'}), 404
    
    records = json.loads(sess.records)
    
    # Create CSV content with three columns
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['CLEAN', 'DIRTY', 'RED'])
    
    # Get max length for padding
    max_length = max(len(records['clean']), len(records['dirty']), len(records['red']))
    
    # Write data rows
    for i in range(max_length):
        row = []
        for category in ['clean', 'dirty', 'red']:
            if i < len(records[category]):
                row.append(records[category][i]['name'])
            else:
                row.append('')
        writer.writerow(row)
    
    csv_content = output.getvalue()
    output.close()

    return jsonify({
        'success': True,
        'csv_content': csv_content,
        'filename': f"{sess.name}_records.csv"
    })


@recorder_bp.route('/export/detailed', methods=['GET'])
def export_detailed_csv():
    """Export detailed session records without student IDs"""
    if not require_auth():
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

    if 'current_session' not in session:
        return jsonify({'success': False, 'message': 'No active session'}), 400

    session_id = session['current_session']
    sess = db_session.query(Session).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'success': False, 'message': 'Session not found'}), 404

    records = json.loads(sess.records)

    detailed_rows = []
    for category, category_records in records.items():
        for record in category_records:
            preferred = str(record.get('preferred') or '').strip()
            last = str(record.get('last') or '').strip()
            if (not preferred or not last) and record.get('name'):
                name = str(record.get('name') or '').strip()
                if name:
                    parts = name.split()
                    if not preferred and parts:
                        preferred = ' '.join(parts[:-1]) if len(parts) > 1 else parts[0]
                    if not last and len(parts) > 1:
                        last = parts[-1]

            detailed_rows.append({
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

    detailed_rows.sort(key=lambda x: x['Recorded At'] or '', reverse=True)

    output = io.StringIO()
    writer = csv.writer(output)
    header = ['Category', 'Last', 'Preferred', 'Grade', 'Advisor', 'House', 'Clan', 'Recorded At', 'Recorded By', 'Manual Entry']
    writer.writerow(header)
    for row in detailed_rows:
        writer.writerow([row[column] for column in header])

    csv_content = output.getvalue()
    output.close()

    return jsonify({
        'success': True,
        'csv_content': csv_content,
        'filename': f"{sess.name}_detailed_records.csv"
    })


@recorder_bp.route('/scan-history', methods=['GET'])
def get_scan_history():
    """Get scan history for current session"""
    if not require_auth():
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    if 'current_session' not in session:
        return jsonify({'success': True, 'history': []})
    
    session_id = session['current_session']
    sess = db_session.query(Session).filter_by(id=session_id).first()
    if not sess:
        return jsonify({'success': True, 'history': []})
    
    records = json.loads(sess.records)
    
    # Combine all records and sort by timestamp
    all_records = []
    for category, category_records in records.items():
        all_records.extend(category_records)
    
    # Sort by timestamp (newest first)
    all_records.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({'success': True, 'history': all_records})

@recorder_bp.route('/admin/overview', methods=['GET'])
def admin_overview():
    """Get admin overview data"""
    if not require_admin():
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    # Get statistics
    total_users = db_session.query(User).count()
    total_sessions = db_session.query(Session).count()
    pending_requests = db_session.query(DeleteRequest).count()
    
    # Get recent sessions
    recent_sessions = db_session.query(Session).order_by(Session.created_at.desc()).limit(10).all()
    sessions_data = []
    for sess in recent_sessions:
        records = json.loads(sess.records)
        total_records = len(records['clean']) + len(records['dirty']) + len(records['red'])
        sessions_data.append({
            'id': sess.id,
            'name': sess.name,
            'user_id': sess.user_id,
            'created_at': sess.created_at.isoformat(),
            'total_records': total_records
        })
    
    return jsonify({
        'success': True,
        'overview': {
            'total_users': total_users,
            'total_sessions': total_sessions,
            'pending_requests': pending_requests,
            'recent_sessions': sessions_data
        }
    })

# Cleanup function to close database connections
@recorder_bp.teardown_app_request
def shutdown_session(exception=None):
    db_session.remove()

