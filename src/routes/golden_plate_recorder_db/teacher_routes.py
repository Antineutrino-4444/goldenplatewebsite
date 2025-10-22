from datetime import datetime

from flask import jsonify, request, session

from . import recorder_bp, storage
from .security import require_admin, require_auth
from .storage import save_global_teacher_data, sync_teacher_table_from_list


@recorder_bp.route('/teachers/upload', methods=['POST'])
def upload_teachers():
    """Upload teacher list (admin/super admin only)."""
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
        content = file.read().decode('utf-8-sig')
        lines = content.strip().split('\n')

        teachers = []
        for line in lines:
            teacher_name = line.strip().strip('"').strip("'")
            if teacher_name:
                teachers.append({
                    'name': teacher_name,
                    'display_name': teacher_name
                })

        if not teachers:
            return jsonify({'error': 'No valid teacher names found in file'}), 400

        user_id = session['user_id']
        storage.global_teacher_data = {
            'teachers': teachers,
            'uploaded_by': user_id,
            'uploaded_at': datetime.now().isoformat()
        }

        save_global_teacher_data()

        try:
            teacher_sync = sync_teacher_table_from_list(teachers)
            print(f"Teacher roster sync complete: {teacher_sync}")
        except Exception as exc:
            print(f"Error syncing teachers table: {exc}")
            return jsonify({'error': 'Teacher roster could not be stored in the database'}), 500

        return jsonify({
            'status': 'success',
            'count': len(teachers),
            'uploaded_by': user_id,
            'teachers_processed': teacher_sync['processed'],
            'teachers_created': teacher_sync['created'],
            'teachers_updated': teacher_sync['updated']
        }), 200

    except Exception as exc:
        return jsonify({'error': f'Error processing file: {str(exc)}'}), 400


@recorder_bp.route('/teachers/list', methods=['GET'])
def get_teacher_names():
    """Get teacher names for dropdown suggestions."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    teacher_data = storage.global_teacher_data
    if not teacher_data or 'teachers' not in teacher_data:
        return jsonify({
            'status': 'no_data',
            'names': []
        }), 200

    teachers = sorted(teacher_data['teachers'], key=lambda x: x['display_name'].lower())

    return jsonify({
        'status': 'success',
        'names': teachers
    }), 200


@recorder_bp.route('/teachers/preview', methods=['GET'])
def preview_teachers():
    """Preview the current teacher list (admin/super admin only)."""
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403

    teacher_data = storage.global_teacher_data

    if not teacher_data:
        return jsonify({
            'status': 'no_data',
            'message': 'No teacher list uploaded yet'
        }), 200

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    teachers = teacher_data.get('teachers', [])

    total_records = len(teachers)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

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


__all__ = []
