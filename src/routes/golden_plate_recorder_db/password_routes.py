"""Password changes and administrator resets using the existing account hierarchy."""
from flask import jsonify, request, session

from . import recorder_bp
from .db import User, db_session
from .passwords import hash_password, verify_password
from .security import get_current_user, password_session_token
from .users import get_user_by_id, serialize_user_model, update_user_credentials

DEFAULT_RESET_PASSWORD = '114514'


def _can_reset_password(actor, target):
    if actor['id'] == target.id:
        return False  # Own password changes use the self-service endpoint.
    if actor['role'] == 'inter_school':
        return True
    return (
        actor['role'] == 'superadmin'
        and actor['school_id'] == target.school_id
        and target.role in {'user', 'admin'}
    )


def _password_input(actor, *, allow_default=False):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({'error': 'Password details are required'}), 400)
    reset_to_default = data.get('reset_to_default', False)
    if not isinstance(reset_to_default, bool):
        return None, (jsonify({'error': 'Invalid password reset option'}), 400)
    if reset_to_default and not allow_default:
        return None, (jsonify({'error': 'Default resets apply only to other accounts'}), 400)
    if allow_default and reset_to_default:
        # The server selects the fixed default; a supplied new_password is ignored.
        data['new_password'] = DEFAULT_RESET_PASSWORD
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    if not isinstance(current_password, str) or not current_password:
        return None, (jsonify({'error': 'Your current password is required'}), 400)
    if (
        not isinstance(new_password, str)
        or not new_password.strip()
        or not 6 <= len(new_password) <= 256
    ):
        return None, (jsonify({'error': 'New password must be between 6 and 256 characters'}), 400)
    if len(current_password) > 4096 or not verify_password(
        get_user_by_id(actor['id']).password_hash, current_password,
    ):
        return None, (jsonify({'error': 'Your current password is incorrect'}), 403)
    return data, None


def _save_password(target, new_password):
    # Always hash user input, even if it happens to resemble a stored hash.
    update_user_credentials(target, password=hash_password(new_password), password_is_hash=True)


@recorder_bp.route('/auth/change-password', methods=['POST'])
def change_own_password():
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Please log in to change your password'}), 401
    data, error = _password_input(actor)
    if error:
        return error
    target = get_user_by_id(actor['id'])
    if verify_password(target.password_hash, data['new_password']):
        return jsonify({'error': 'Choose a password different from your current password'}), 400
    try:
        _save_password(target, data['new_password'])
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to save the password. Please try again.'}), 500
    # Keep this session signed in; all other sessions have the previous token.
    session['password_token'] = password_session_token(target)
    return jsonify({'status': 'success', 'message': 'Your password has been changed.'}), 200


@recorder_bp.route('/auth/password-accounts', methods=['GET'])
def password_accounts():
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Please log in to manage passwords'}), 401
    if actor['role'] not in {'superadmin', 'inter_school'}:
        return jsonify({'error': 'Password reset access required'}), 403
    query = db_session.query(User).order_by(User.username.asc())
    if actor['role'] == 'superadmin':
        query = query.filter(User.school_id == actor['school_id'])
    accounts = [serialize_user_model(user) for user in query.all() if _can_reset_password(actor, user)]
    return jsonify({'users': accounts}), 200


@recorder_bp.route('/auth/reset-password', methods=['POST'])
def reset_account_password():
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Please log in to manage passwords'}), 401
    if actor['role'] not in {'superadmin', 'inter_school'}:
        return jsonify({'error': 'Password reset access required'}), 403
    data, error = _password_input(actor, allow_default=True)
    if error:
        return error
    user_id = data.get('user_id')
    if not isinstance(user_id, str) or not user_id:
        return jsonify({'error': 'Choose an account to reset'}), 400
    target = get_user_by_id(user_id)
    if not target or not _can_reset_password(actor, target):
        return jsonify({'error': 'Account not found or outside your password reset permissions'}), 404
    try:
        _save_password(target, data['new_password'])
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to reset the password. Please try again.'}), 500
    return jsonify({'status': 'success', 'message': f'Password reset for @{target.username}.'}), 200
