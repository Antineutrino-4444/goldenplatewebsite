from datetime import datetime

from flask import jsonify, request, session

from . import recorder_bp
from .domain import serialize_draw_info
from .security import get_current_user, require_admin, require_auth
from .storage import (
    delete_requests,
    ensure_session_structure,
    get_dirty_count,
    save_delete_requests,
    save_session_data,
    session_data,
)
from .users import (
    create_invite_code_record,
    get_user_by_username,
    list_all_users,
    update_user_credentials,
)


@recorder_bp.route('/admin/manage-account-status', methods=['POST'])
def manage_account_status():
    """Manage account status (enable/disable users)."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    current_user = get_current_user()
    data = request.get_json() or {}
    target_username = data.get('username')
    new_status = data.get('status')

    if not target_username or not new_status:
        return jsonify({'error': 'Username and status are required'}), 400

    target_user_model = get_user_by_username(target_username)
    if not target_user_model:
        return jsonify({'error': 'User not found'}), 404

    target_role = target_user_model.role

    if current_user['role'] == 'superadmin':
        if target_username == session['user_id']:
            return jsonify({'error': 'Cannot modify your own account status'}), 403
    elif current_user['role'] == 'admin':
        if target_role in ['superadmin', 'admin']:
            return jsonify({'error': 'Insufficient permissions to modify this account'}), 403
    else:
        return jsonify({'error': 'Insufficient permissions'}), 403

    try:
        update_user_credentials(target_user_model, status=new_status)
    except Exception:
        return jsonify({'error': 'Failed to update user status'}), 500

    return jsonify({
        'status': 'success',
        'message': f'Account {target_username} has been {new_status}'
    }), 200


@recorder_bp.route('/admin/delete-requests', methods=['GET'])
def get_delete_requests():
    """Get pending delete requests (admin/super admin only)."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    pending_requests = [req for req in delete_requests if req.get('status') == 'pending']
    return jsonify({
        'status': 'success',
        'requests': pending_requests
    }), 200


@recorder_bp.route('/admin/users', methods=['GET'])
def admin_get_users():
    """Admin: Get all users."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    users_list = []
    for user in list_all_users():
        users_list.append({
            'username': user['username'],
            'name': user['name'],
            'role': user['role']
        })

    return jsonify({'users': users_list}), 200


@recorder_bp.route('/admin/invite', methods=['POST'])
def admin_create_invite():
    """Admin: Generate a one-time invite code."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    issuer = get_user_by_username(session.get('user_id'))
    if not issuer:
        return jsonify({'error': 'Unable to locate issuing user'}), 500

    invite = create_invite_code_record(issuer, issuer, role='user')
    return jsonify({'status': 'success', 'invite_code': invite.code}), 201


@recorder_bp.route('/admin/sessions', methods=['GET'])
def admin_get_all_sessions():
    """Admin: Get all sessions from all users."""
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
    """Admin: Delete any session."""
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


@recorder_bp.route('/admin/delete-requests/<request_id>/approve', methods=['POST'])
def approve_delete_request(request_id):
    """Approve a delete request (admin/superadmin only)."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    request_obj = next((req for req in delete_requests if req['id'] == request_id), None)
    if not request_obj:
        return jsonify({'error': 'Delete request not found'}), 404

    if request_obj['status'] != 'pending':
        return jsonify({'error': 'Request is not pending'}), 400

    session_id = request_obj['session_id']

    if session_id not in session_data:
        request_obj['status'] = 'completed'
        request_obj['approved_by'] = session['user_id']
        request_obj['approved_at'] = datetime.now().isoformat()
        save_delete_requests()
        return jsonify({'message': 'Session no longer exists, request marked as completed'}), 200

    session_name = session_data[session_id]['session_name']
    del session_data[session_id]
    save_session_data()
    if session.get('session_id') == session_id:
        session.pop('session_id', None)

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
    """Reject a delete request (admin/superadmin only)."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json(silent=True) or {}
    rejection_reason = data.get('reason', 'No reason provided')

    request_obj = next((req for req in delete_requests if req['id'] == request_id), None)
    if not request_obj:
        return jsonify({'error': 'Delete request not found'}), 404

    if request_obj['status'] != 'pending':
        return jsonify({'error': 'Request is not pending'}), 400

    request_obj['status'] = 'rejected'
    request_obj['rejected_by'] = session['user_id']
    request_obj['rejected_at'] = datetime.now().isoformat()
    request_obj['rejection_reason'] = rejection_reason
    save_delete_requests()

    return jsonify({
        'status': 'success',
        'message': 'Delete request rejected',
        'request_id': request_id
    }), 200


@recorder_bp.route('/admin/overview', methods=['GET'])
def admin_overview():
    """Get admin overview data."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    users = []
    for user in list_all_users():
        users.append({
            'username': user['username'],
            'name': user['name'],
            'role': user['role']
        })

    sessions_overview = []
    for session_id, session_info in session_data.items():
        ensure_session_structure(session_info)
        total_records = len(session_info['clean_records']) + get_dirty_count(session_info) + len(session_info['red_records'])
        sessions_overview.append({
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
        'sessions': sessions_overview
    }), 200


__all__ = []
