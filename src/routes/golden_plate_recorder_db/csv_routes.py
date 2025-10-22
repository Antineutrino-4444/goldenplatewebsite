import csv
import io
from datetime import datetime

from flask import jsonify, request, session
from sqlalchemy import func

from . import recorder_bp, storage
from .db import Student, db_session
from .security import require_admin, require_auth
from .storage import save_global_csv_data, sync_students_table_from_csv_rows
from .utils import make_student_key


@recorder_bp.route('/csv/upload', methods=['POST'])
def upload_csv():
    """Upload CSV file (requires admin or super admin)."""
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
        storage.global_csv_data = {
            'data': rows,
            'columns': csv_reader.fieldnames,
            'uploaded_by': user_id,
            'uploaded_at': datetime.now().isoformat()
        }
        save_global_csv_data()

        try:
            sync_result = sync_students_table_from_csv_rows(rows)
            print(f"Student roster sync complete: {sync_result}")
        except Exception as exc:
            print(f"Error syncing students table: {exc}")
            return jsonify({'error': 'Student roster could not be stored in the database'}), 500

        return jsonify({
            'status': 'success',
            'rows_count': len(rows),
            'uploaded_by': user_id,
            'students_processed': sync_result['processed'],
            'students_created': sync_result['created'],
            'students_updated': sync_result['updated']
        }), 200

    except Exception as exc:
        return jsonify({'error': f'Error processing CSV: {str(exc)}'}), 400


@recorder_bp.route('/csv/preview', methods=['GET'])
def preview_csv():
    """Preview the current student database (admin/super admin only)."""
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    base_query = db_session.query(Student)
    total_records = base_query.count()

    if total_records == 0:
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
        'House': str(student.house or '').strip(),
        'Clan': str(student.clan or '').strip()
    } for student in students]

    csv_data = storage.global_csv_data

    return jsonify({
        'status': 'success',
        'data': sanitized_rows,
        'columns': ['Preferred', 'Last', 'Grade', 'Advisor', 'House', 'Clan'],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_records': total_records,
            'total_pages': (total_records + per_page - 1) // per_page,
            'has_next': (start_idx + per_page) < total_records,
            'has_prev': page > 1
        },
        'metadata': {
            'uploaded_by': csv_data.get('uploaded_by', 'unknown') if csv_data else 'unknown',
            'uploaded_at': csv_data.get('uploaded_at', 'unknown') if csv_data else 'unknown'
        }
    }), 200


@recorder_bp.route('/csv/student-names', methods=['GET'])
def get_student_names():
    """Get student names for dropdown suggestions."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    students = (
        db_session.query(Student)
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
