from datetime import datetime

from flask import jsonify, request, session
from sqlalchemy import func, or_

from . import recorder_bp, storage
from .db import School, Teacher, db_session
from .security import get_current_user, require_admin, require_auth
from .roster_csv import roster_csv_reader
from .storage import save_global_teacher_data, sync_teacher_table_from_list
from .utils import normalize_name
from .users import readable_user_label


def _teacher_roster_metadata(school_id):
    school = db_session.get(School, school_id)
    return {
        'filename': school.teacher_roster_filename if school else None,
        'uploaded_by': readable_user_label(school.teacher_roster_uploaded_by if school else None, school_id=school_id),
        'uploaded_at': school.teacher_roster_uploaded_at.isoformat() if school and school.teacher_roster_uploaded_at else None,
    }


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
        teachers = []
        if file.filename.lower().endswith('.csv'):
            reader = roster_csv_reader(content, columns=('Last', 'Preferred', 'First'))
            fields = reader.fieldnames or []
            if 'Last' not in fields or not any(name in fields for name in ('Preferred', 'First')):
                return jsonify({'error': 'Teacher CSV must contain Last and either Preferred or First. Columns may be in any order and header capitalization does not matter.'}), 400
            first_column = 'Preferred' if 'Preferred' in fields else 'First'
            for row in reader:
                first = normalize_name(row.get(first_column))
                last = normalize_name(row.get('Last'))
                if first and last:
                    teacher_name = f'{first} {last}'
                    teachers.append({'name': teacher_name, 'display_name': teacher_name})
        else:
            for line in content.splitlines():
                teacher_name = line.strip().strip('"').strip("'")
                if teacher_name:
                    teachers.append({'name': teacher_name, 'display_name': teacher_name})

        if not teachers:
            return jsonify({'error': 'No valid teacher names found. CSV rows need Last and Preferred (or First when the Preferred column is absent).'}), 400

        user_id = session['user_id']
        try:
            filename = file.filename.replace('\\', '/').rsplit('/', 1)[-1]
            teacher_sync = sync_teacher_table_from_list(
                teachers, school_id=school_id, filename=filename, uploaded_by=current_user['username'],
            )
            print(f"Teacher roster sync complete: {teacher_sync}")
        except Exception as exc:
            print(f"Error syncing teachers table: {exc}")
            return jsonify({'error': 'Teacher roster could not be stored in the database'}), 500

        storage.global_teacher_data[school_id] = {
            'teachers': teachers,
            'uploaded_by': user_id,
            'uploaded_at': datetime.now().isoformat(),
        }
        save_global_teacher_data()

        return jsonify({
            'status': 'success',
            'count': teacher_sync['processed'],
            'filename': filename,
            'uploaded_by': user_id,
            'teachers_processed': teacher_sync['processed'],
            'teachers_created': teacher_sync['created'],
            'teachers_updated': teacher_sync['updated'],
            'teachers_removed': teacher_sync['removed'],
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
            'names': [],
            'metadata': _teacher_roster_metadata(school_id),
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
        'names': teacher_list,
        'metadata': _teacher_roster_metadata(school_id),
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
    search = request.args.get('search', '').strip().lower()
    if search:
        base_query = base_query.filter(or_(
            func.lower(Teacher.name).contains(search, autoescape=True),
            func.lower(Teacher.display_name).contains(search, autoescape=True),
        ))
    total_records = base_query.count()

    if total_records == 0 and not search:
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

    return jsonify({
        'status': 'success',
        'data': paginated_teachers,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_records': total_records,
            'total_pages': max(1, (total_records + per_page - 1) // per_page),
            'has_next': (start_idx + per_page) < total_records,
            'has_prev': page > 1
        },
        'metadata': _teacher_roster_metadata(school_id),
    }), 200


__all__ = []
