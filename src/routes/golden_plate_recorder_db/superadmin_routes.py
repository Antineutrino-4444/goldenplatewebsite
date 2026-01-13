import os

from flask import jsonify, request, session

from . import recorder_bp
from .db import AccountCreationRequest, _now_utc, db_session
from .security import get_current_user, require_superadmin
from .storage import save_session_data, session_data
from .users import create_user_record, get_user_by_username, serialize_school, update_user_credentials


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


def serialize_account_request(request_obj):
    """Serialize an AccountCreationRequest for JSON response."""
    if not request_obj:
        return None
    school = getattr(request_obj, 'school', None)
    return {
        'id': request_obj.id,
        'school_id': request_obj.school_id,
        'school': serialize_school(school) if school else None,
        'username': request_obj.username,
        'display_name': request_obj.display_name,
        'status': request_obj.status,
        'requested_at': request_obj.requested_at.isoformat() if request_obj.requested_at else None,
        'reviewed_by': request_obj.reviewed_by,
        'reviewed_at': request_obj.reviewed_at.isoformat() if request_obj.reviewed_at else None,
        'rejection_reason': request_obj.rejection_reason,
    }


@recorder_bp.route('/superadmin/account-requests', methods=['GET'])
def list_account_requests():
    """List all pending account creation requests for the superadmin's school."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    current_user = get_current_user()
    school_id = current_user['school_id']

    try:
        requests_list = db_session.query(AccountCreationRequest).filter(
            AccountCreationRequest.school_id == school_id
        ).order_by(AccountCreationRequest.requested_at.desc()).all()

        return jsonify({
            'status': 'success',
            'requests': [serialize_account_request(req) for req in requests_list]
        }), 200
    except Exception:
        return jsonify({'error': 'Failed to load account requests'}), 500


@recorder_bp.route('/superadmin/account-requests/pending', methods=['GET'])
def list_pending_account_requests():
    """List only pending account creation requests for the superadmin's school."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    current_user = get_current_user()
    school_id = current_user['school_id']

    try:
        requests_list = db_session.query(AccountCreationRequest).filter(
            AccountCreationRequest.school_id == school_id,
            AccountCreationRequest.status == 'pending'
        ).order_by(AccountCreationRequest.requested_at.desc()).all()

        return jsonify({
            'status': 'success',
            'requests': [serialize_account_request(req) for req in requests_list],
            'count': len(requests_list)
        }), 200
    except Exception:
        return jsonify({'error': 'Failed to load pending account requests'}), 500


@recorder_bp.route('/superadmin/account-requests/<request_id>/approve', methods=['POST'])
def approve_account_request(request_id):
    """Approve an account creation request and create the user account."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    current_user = get_current_user()
    school_id = current_user['school_id']

    account_request = db_session.query(AccountCreationRequest).filter(
        AccountCreationRequest.id == request_id,
        AccountCreationRequest.school_id == school_id
    ).first()

    if not account_request:
        return jsonify({'error': 'Account request not found'}), 404

    if account_request.status != 'pending':
        return jsonify({'error': f'Account request has already been {account_request.status}'}), 400

    # Check if username still doesn't exist
    if get_user_by_username(account_request.username, school_id=school_id):
        account_request.status = 'rejected'
        account_request.rejection_reason = 'Username was taken while request was pending'
        account_request.reviewed_by = session.get('user_uuid')
        account_request.reviewed_at = _now_utc()
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
        return jsonify({'error': 'Username already exists. Request has been rejected.'}), 409

    try:
        # Create the new user account
        new_user = create_user_record(
            account_request.username,
            account_request.password_hash,
            account_request.display_name,
            role='user',
            status='active',
            school_id=school_id,
        )

        # Update the request status
        account_request.status = 'approved'
        account_request.reviewed_by = session.get('user_uuid')
        account_request.reviewed_at = _now_utc()
        db_session.commit()

        return jsonify({
            'status': 'success',
            'message': f'Account for {account_request.username} created successfully',
            'user': {
                'id': new_user.id,
                'username': new_user.username,
                'display_name': new_user.display_name,
            }
        }), 200
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Failed to create user account'}), 500


@recorder_bp.route('/superadmin/account-requests/<request_id>/reject', methods=['POST'])
def reject_account_request(request_id):
    """Reject an account creation request."""
    if not require_superadmin():
        return jsonify({'error': 'Super admin access required'}), 403

    current_user = get_current_user()
    school_id = current_user['school_id']

    data = request.get_json(silent=True) or {}
    reason = data.get('reason', '').strip()

    account_request = db_session.query(AccountCreationRequest).filter(
        AccountCreationRequest.id == request_id,
        AccountCreationRequest.school_id == school_id
    ).first()

    if not account_request:
        return jsonify({'error': 'Account request not found'}), 404

    if account_request.status != 'pending':
        return jsonify({'error': f'Account request has already been {account_request.status}'}), 400

    try:
        account_request.status = 'rejected'
        account_request.rejection_reason = reason or None
        account_request.reviewed_by = session.get('user_uuid')
        account_request.reviewed_at = _now_utc()
        db_session.commit()

        return jsonify({
            'status': 'success',
            'message': f'Account request for {account_request.username} has been rejected'
        }), 200
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Failed to reject account request'}), 500


__all__ = []
