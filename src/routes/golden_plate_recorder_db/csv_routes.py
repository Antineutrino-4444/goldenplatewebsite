import csv
import io
from datetime import datetime

from flask import jsonify, request, session

from . import recorder_bp, storage
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

    csv_data = storage.global_csv_data

    if not csv_data:
        return jsonify({
            'status': 'no_data',
            'message': 'No student database uploaded yet'
        }), 200

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    total_records = len(csv_data['data'])
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

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
    """Get student names for dropdown suggestions."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    csv_data = storage.global_csv_data
    if not csv_data or 'data' not in csv_data:
        return jsonify({
            'status': 'no_data',
            'names': []
        }), 200

    names = []
    for row in csv_data['data']:
        preferred = str(row.get('Preferred', '') or '').strip()
        last = str(row.get('Last', '') or '').strip()
        student_id = str(row.get('Student ID', '') or '').strip()
        key = make_student_key(preferred, last, student_id)

        if preferred and last:
            full_name = f"{preferred} {last}"
            names.append({
                'display_name': full_name,
                'preferred': preferred,
                'preferred_name': preferred,
                'last': last,
                'last_name': last,
                'student_id': student_id,
                'key': key
            })
        elif preferred:
            names.append({
                'display_name': preferred,
                'preferred': preferred,
                'preferred_name': preferred,
                'last': '',
                'last_name': '',
                'student_id': student_id,
                'key': key
            })

    names.sort(key=lambda x: x['display_name'].lower())

    return jsonify({
        'status': 'success',
        'names': names
    }), 200


__all__ = []
