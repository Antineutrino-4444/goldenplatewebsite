import os

from flask import jsonify, request, session

from . import recorder_bp
from .db import db_session
from .security import get_current_user, require_superadmin
from .storage import save_session_data, session_data
from .users import get_user_by_username, update_user_credentials


@recorder_bp.route('/superadmin/change-role', methods=['POST'])
def change_user_role():
    """Allow super admins to change a user's role."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    current_user = get_current_user()
    current_username = session.get('user_id')
    data = request.get_json(silent=True) or {}
    target_username = data.get('username')
    new_role = data.get('role')

    if not target_username or not new_role:
        return jsonify({'error': 'Username and role are required'}), 400

    if new_role not in ['user', 'admin', 'superadmin']:
        return jsonify({'error': 'Invalid role'}), 400

    if target_username == current_username:
        return jsonify({'error': 'Cannot change your own role'}), 400

    target_user_model = get_user_by_username(target_username, school_id=current_user['school_id'])
    if not target_user_model:
        return jsonify({'error': 'User not found'}), 404

    try:
        update_user_credentials(target_user_model, role=new_role)
    except Exception:
        return jsonify({'error': 'Failed to update user role'}), 500

    return jsonify({'status': 'success', 'message': f'User role changed to {new_role} successfully'}), 200


@recorder_bp.route('/superadmin/delete-account', methods=['POST'])
def delete_user_account():
    """Allow super admins to delete a user account and their data."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    current_user = get_current_user()
    current_username = session.get('user_id')
    data = request.get_json(silent=True) or {}
    target_username = data.get('username')

    if not target_username:
        return jsonify({'error': 'Username is required'}), 400

    if target_username == current_username:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    target_user_model = get_user_by_username(target_username, school_id=current_user['school_id'])
    if not target_user_model:
        return jsonify({'error': 'User not found'}), 404

    try:
        db_session.delete(target_user_model)
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Failed to delete user account'}), 500

    legacy_file = f'user_csv_{target_username}.json'
    if os.path.exists(legacy_file):
        os.remove(legacy_file)

    sessions_to_remove = [
        sid for sid, info in session_data.items()
        if info.get('owner') == target_username and info.get('school_id') == current_user['school_id']
    ]
    for session_id in sessions_to_remove:
        session_data.pop(session_id, None)
    save_session_data()

    return jsonify({'status': 'success', 'message': 'User account deleted successfully'}), 200


__all__ = []
