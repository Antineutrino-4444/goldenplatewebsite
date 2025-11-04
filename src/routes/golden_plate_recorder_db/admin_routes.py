from flask import jsonify, request, session

from . import recorder_bp
from .db import Session as SessionModel, SessionDeleteRequest, db_session as db, _now_utc
from .domain import serialize_draw_info
from .security import get_current_user, require_admin, require_auth
from .storage import (
    delete_requests,
    ensure_session_structure,
    get_dirty_count,
    get_session_entry,
    save_delete_requests,
    session_data,
)
from .session_routes import _delete_session_with_dependencies
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
        if target_username == session.get('username'):
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

    refreshed_requests = save_delete_requests()
    pending_requests = [req for req in refreshed_requests if req.get('status') == 'pending']
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
    current_school_id = get_current_user()['school_id']
    for user in list_all_users(school_id=current_school_id):
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

    issuer = get_user_by_username(session.get('username'))
    if not issuer:
        return jsonify({'error': 'Unable to locate issuing user'}), 500

    invite = create_invite_code_record(issuer, issuer, role='user', school_id=issuer.school_id)
    return jsonify({'status': 'success', 'invite_code': invite.code}), 201


@recorder_bp.route('/admin/sessions', methods=['GET'])
def admin_get_all_sessions():
    """Admin: Get all sessions from all users."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    current_school_id = get_current_user()['school_id']
    db_sessions = (
        db.query(SessionModel)
        .filter(SessionModel.school_id == current_school_id)
        .order_by(SessionModel.created_at.desc())
        .all()
    )

    all_sessions = []
    for db_sess in db_sessions:
        json_data = session_data.get(db_sess.id, {})
        ensure_session_structure(json_data)
        total_records = db_sess.total_records or 0
        all_sessions.append({
            'session_id': db_sess.id,
            'session_name': db_sess.session_name,
            'owner': json_data.get('owner', db_sess.created_by),
            'created_at': db_sess.created_at.isoformat() if db_sess.created_at else json_data.get('created_at', 'unknown'),
            'total_records': total_records,
            'clean_count': db_sess.clean_number or 0,
            'dirty_count': (db_sess.dirty_number or 0) + (db_sess.red_number or 0),
            'red_count': db_sess.red_number or 0,
            'faculty_clean_count': db_sess.faculty_number or 0
        })

    return jsonify({'sessions': all_sessions}), 200


@recorder_bp.route('/admin/sessions/<session_id>', methods=['DELETE'])
def admin_delete_session(session_id):
    """Admin: Delete any session."""
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403

    current_user = get_current_user()
    db_sess = db.query(SessionModel).filter_by(id=session_id, school_id=current_user['school_id']).first()
    if not db_sess:
        return jsonify({'error': 'Session not found'}), 404

    session_name = _delete_session_with_dependencies(db_sess)

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

    current_user = get_current_user()
    request_model = (
        db.query(SessionDeleteRequest)
        .filter_by(id=request_id, school_id=current_user['school_id'])
        .first()
    )
    if not request_model:
        return jsonify({'error': 'Delete request not found'}), 404

    if request_model.status != 'pending':
        return jsonify({'error': 'Request is not pending'}), 400

    session_id = request_model.session_id
    db_sess = db.query(SessionModel).filter_by(id=session_id, school_id=current_user['school_id']).first()
    if not db_sess:
        request_model.status = 'completed'
        request_model.reviewed_by = current_user['id'] if current_user else None
        request_model.reviewed_at = _now_utc()
        request_model.rejection_reason = None
        try:
            db.commit()
        except Exception:
            db.rollback()
            return jsonify({'error': 'Failed to update delete request'}), 500
        save_delete_requests()
        return jsonify({'message': 'Session no longer exists, request marked as completed'}), 200

    request_model.status = 'approved'
    request_model.reviewed_by = current_user['id'] if current_user else None
    request_model.reviewed_at = _now_utc()
    request_model.rejection_reason = None

    session_name = db_sess.session_name
    try:
        _delete_session_with_dependencies(db_sess)
    except Exception:
        db.rollback()
        return jsonify({'error': 'Failed to delete session'}), 500

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

    request_model = db.query(SessionDeleteRequest).filter_by(id=request_id).first()
    if not request_model:
        return jsonify({'error': 'Delete request not found'}), 404

    if request_model.status != 'pending':
        return jsonify({'error': 'Request is not pending'}), 400

    current_user = get_current_user()
    request_model.status = 'rejected'
    request_model.reviewed_by = current_user['id'] if current_user else None
    request_model.reviewed_at = _now_utc()
    request_model.rejection_reason = rejection_reason

    try:
        db.commit()
    except Exception:
        db.rollback()
        return jsonify({'error': 'Failed to update delete request'}), 500

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

    # Get sessions from database with cached counts
    db_sessions = db.query(SessionModel).order_by(SessionModel.created_at.desc()).all()
    
    sessions_overview = []
    for db_sess in db_sessions:
        # Get draw_info from JSON storage for backward compatibility
        json_data = session_data.get(db_sess.id, {})
        draw_info = serialize_draw_info(json_data.get('draw_info', {}))
        
        sessions_overview.append({
            'session_id': db_sess.id,
            'session_name': db_sess.session_name,
            'owner': db_sess.created_by,
            'total_records': db_sess.total_records or 0,
            'created_at': db_sess.created_at.isoformat() if db_sess.created_at else None,
            'faculty_clean_count': db_sess.faculty_number or 0,
            'is_discarded': db_sess.status == 'discarded',
            'draw_info': draw_info
        })

    return jsonify({
        'users': users,
        'sessions': sessions_overview
    }), 200


__all__ = []
