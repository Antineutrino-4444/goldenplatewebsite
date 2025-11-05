from datetime import datetime

from flask import jsonify, request, session
from sqlalchemy import func

from . import recorder_bp, storage
from .db import Teacher, db_session
from .security import get_current_user, require_admin, require_auth
from .storage import save_global_teacher_data, sync_teacher_table_from_list


@recorder_bp.route('/teachers/upload', methods=['POST'])
def upload_teachers():
    """Upload teacher list (admin/super admin only)."""
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    school_id = current_user['school_id']

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
        storage.global_teacher_data[school_id] = {
            'teachers': teachers,
            'uploaded_by': user_id,
            'uploaded_at': datetime.now().isoformat()
        }

        save_global_teacher_data()

        try:
            teacher_sync = sync_teacher_table_from_list(teachers, school_id=school_id)
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

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    school_id = current_user['school_id']

    teachers = (
        db_session.query(Teacher)
        .filter(Teacher.school_id == school_id)
        .order_by(func.lower(Teacher.display_name), func.lower(Teacher.name))
        .all()
    )

    if not teachers:
        return jsonify({
            'status': 'no_data',
            'names': []
        }), 200

    teacher_list = []
    for teacher in teachers:
        display_name = str(teacher.display_name or teacher.name or '').strip()
        name_value = str(teacher.name or '').strip()
        teacher_list.append({
            'name': name_value,
            'display_name': display_name or name_value
        })

    return jsonify({
        'status': 'success',
        'names': teacher_list
    }), 200


@recorder_bp.route('/teachers/preview', methods=['GET'])
def preview_teachers():
    """Preview the current teacher list (admin/super admin only)."""
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    school_id = current_user['school_id']

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    base_query = db_session.query(Teacher).filter(Teacher.school_id == school_id)
    total_records = base_query.count()

    if total_records == 0:
        return jsonify({
            'status': 'no_data',
            'message': 'No teacher records found in database'
        }), 200

    start_idx = (page - 1) * per_page

    teachers = (
        base_query
        .order_by(func.lower(Teacher.display_name), func.lower(Teacher.name))
        .offset(start_idx)
        .limit(per_page)
        .all()
    )

    paginated_teachers = [{
        'name': str(teacher.name or '').strip(),
        'display_name': str(teacher.display_name or teacher.name or '').strip()
    } for teacher in teachers]

    teacher_data = storage.global_teacher_data.get(school_id, {})

    return jsonify({
        'status': 'success',
        'data': paginated_teachers,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_records': total_records,
            'total_pages': (total_records + per_page - 1) // per_page,
            'has_next': (start_idx + per_page) < total_records,
            'has_prev': page > 1
        },
        'metadata': {
            'uploaded_by': teacher_data.get('uploaded_by', 'unknown') if teacher_data else 'unknown',
            'uploaded_at': teacher_data.get('uploaded_at', 'unknown') if teacher_data else 'unknown'
        }
    }), 200


__all__ = []
