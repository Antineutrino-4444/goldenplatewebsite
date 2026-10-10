import csv
import io
from datetime import datetime

from flask import jsonify, request, session
from sqlalchemy import func

from . import recorder_bp, storage
from .db import School, Student, db_session
from .security import get_current_user, require_admin, require_auth
from .storage import save_global_csv_data, sync_students_table_from_csv_rows
from .utils import make_student_key, normalize_house


def _roster_metadata(school_id):
    school = db_session.get(School, school_id)
    return {
        'filename': school.roster_filename if school else None,
        'uploaded_by': school.roster_uploaded_by or 'unknown' if school else 'unknown',
        'uploaded_at': school.roster_uploaded_at.isoformat() if school and school.roster_uploaded_at else None,
    }


@recorder_bp.route('/csv/status', methods=['GET'])
def roster_status():
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401
    school_id = get_current_user()['school_id']
    count = db_session.query(Student).filter_by(school_id=school_id, is_active=1).count()
    return jsonify({'loaded': count > 0, 'rows_count': count, **_roster_metadata(school_id)})


@recorder_bp.route('/csv/upload', methods=['POST'])
def upload_csv():
    """Upload CSV file (requires admin or super admin)."""
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400

    try:
        content = file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(content))

        rows = list(csv_reader)
        if not rows:
            return jsonify({'error': 'CSV file is empty'}), 400

        required_columns = ['Student ID', 'Last', 'Preferred', 'Grade', 'Advisor', 'House', 'Clan']
        if not all(col in csv_reader.fieldnames for col in required_columns):
            columns = ', '.join(required_columns)
            return jsonify({'error': f'CSV must contain columns: {columns}'}), 400

        user_id = session['user_id']
        school_id = current_user['school_id']
        try:
            filename = file.filename.replace('\\', '/').rsplit('/', 1)[-1]
            sync_result = sync_students_table_from_csv_rows(rows, school_id=school_id, filename=filename, uploaded_by=current_user['username'])
            print(f"Student roster sync complete: {sync_result}")
        except Exception as exc:
            print(f"Error syncing students table: {exc}")
            return jsonify({'error': 'Student roster could not be stored in the database'}), 500

        if not sync_result['processed']:
            return jsonify({'error': 'CSV must contain students with an ID, preferred name, and last name'}), 400
        storage.global_csv_data[school_id] = {
            'data': rows,
            'columns': csv_reader.fieldnames,
            'uploaded_by': user_id,
            'uploaded_at': datetime.now().isoformat()
        }
        save_global_csv_data()

        return jsonify({
            'status': 'success',
            'rows_count': sync_result['processed'],
            'uploaded_by': user_id,
            'students_processed': sync_result['processed'],
            'students_created': sync_result['created'],
            'students_updated': sync_result['updated'],
            'students_deactivated': sync_result['deactivated'],
            'filename': filename
        }), 200

    except Exception as exc:
        return jsonify({'error': f'Error processing CSV: {str(exc)}'}), 400


@recorder_bp.route('/csv/preview', methods=['GET'])
def preview_csv():
    """Preview the current student database (admin/super admin only)."""
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    school_id = current_user['school_id']

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    base_query = db_session.query(Student).filter(Student.school_id == school_id, Student.is_active == 1)
    search = request.args.get('search', '').strip().lower()
    if search:
        base_query = base_query.filter(
            func.lower(Student.preferred_name + ' ' + Student.last_name).contains(search, autoescape=True)
        )
    total_records = base_query.count()

    if total_records == 0 and not search:
        return jsonify({
            'status': 'no_data',
            'message': 'No student records found in database'
        }), 200

    start_idx = (page - 1) * per_page

    students = (
        base_query
        .order_by(func.lower(Student.preferred_name), func.lower(Student.last_name))
        .offset(start_idx)
        .limit(per_page)
        .all()
    )

    sanitized_rows = [{
        'Preferred': str(student.preferred_name or '').strip(),
        'Last': str(student.last_name or '').strip(),
        'Grade': str(student.grade or '').strip(),
        'Advisor': str(student.advisor or '').strip(),
        'House': normalize_house(student.house),
        'Clan': str(student.clan or '').strip()
    } for student in students]

    return jsonify({
        'status': 'success',
        'data': sanitized_rows,
        'columns': ['Preferred', 'Last', 'Grade', 'Advisor', 'House', 'Clan'],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_records': total_records,
            'total_pages': max(1, (total_records + per_page - 1) // per_page),
            'has_next': (start_idx + per_page) < total_records,
            'has_prev': page > 1
        },
        'metadata': _roster_metadata(school_id)
    }), 200


@recorder_bp.route('/csv/student-names', methods=['GET'])
def get_student_names():
    """Get student names for dropdown suggestions."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    school_id = current_user['school_id']

    students = (
        db_session.query(Student)
        .filter(Student.school_id == school_id, Student.is_active == 1)
        .order_by(func.lower(Student.preferred_name), func.lower(Student.last_name))
        .all()
    )

    if not students:
        return jsonify({
            'status': 'no_data',
            'names': []
        }), 200

    names = []
    for student in students:
        preferred = str(student.preferred_name or '').strip()
        last = str(student.last_name or '').strip()
        student_id = str(student.student_identifier or '').strip()
        key = make_student_key(preferred, last, student_id)
        display_name = f"{preferred} {last}".strip()

        names.append({
            'display_name': display_name or preferred or last,
            'preferred': preferred,
            'preferred_name': preferred,
            'last': last,
            'last_name': last,
            'student_id': student_id,
            'key': key
        })

    return jsonify({
        'status': 'success',
        'names': names
    }), 200


__all__ = []
