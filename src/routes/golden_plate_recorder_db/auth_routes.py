from flask import jsonify, request, session

from . import recorder_bp
from .db import _now_utc, db_session
from .security import get_current_user, is_guest, require_auth
from .users import (
    create_user_record,
    get_invite_code_record,
    get_user_by_username,
    mark_invite_code_used,
)


@recorder_bp.route('/auth/login', methods=['POST'])
def login():
    """User login."""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    user = get_user_by_username(username)
    if not user or user.password_hash != password:
        return jsonify({'error': 'Invalid username or password'}), 401

    if user.status != 'active':
        return jsonify({'error': 'Account is disabled. Please contact an administrator.'}), 403

    session['user_id'] = username
    user.last_login_at = _now_utc()
    user.updated_at = _now_utc()
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to update login information'}), 500

    return jsonify({
        'status': 'success',
        'user': {
            'username': username,
            'name': user.display_name,
            'role': user.role
        }
    }), 200


@recorder_bp.route('/auth/logout', methods=['POST'])
def logout():
    """User logout."""
    session.pop('user_id', None)
    session.pop('session_id', None)
    session.pop('guest_access', None)
    return jsonify({'status': 'success', 'message': 'Logged out successfully'}), 200


@recorder_bp.route('/auth/guest', methods=['POST'])
def guest_login():
    """Guest login - allows viewing sessions without signup."""
    session['guest_access'] = True
    return jsonify({
        'status': 'success',
        'user': {
            'username': 'guest',
            'name': 'Guest User',
            'role': 'guest'
        }
    }), 200


@recorder_bp.route('/auth/signup', methods=['POST'])
def signup():
    """User signup."""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    invite_code = data.get('invite_code', '').strip()

    if not username or not password or not name or not invite_code:
        return jsonify({'error': 'Username, password, name, and invite code are required'}), 400

    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters long'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400

    if get_user_by_username(username):
        return jsonify({'error': 'Username already exists'}), 409

    invite = get_invite_code_record(invite_code)
    if not invite or invite.status != 'unused':
        return jsonify({'error': 'Invalid invite code'}), 403

    if invite.expires_at and invite.expires_at < _now_utc():
        return jsonify({'error': 'Invite code has expired'}), 403

    try:
        new_user = create_user_record(
            username,
            password,
            name,
            role=invite.role or 'user',
            status='active'
        )
    except Exception:
        return jsonify({'error': 'Could not create user'}), 500

    try:
        mark_invite_code_used(invite, new_user)
    except Exception:
        user_to_delete = get_user_by_username(username)
        if user_to_delete:
            try:
                db_session.delete(user_to_delete)
                db_session.commit()
            except Exception:
                db_session.rollback()
        return jsonify({'error': 'Could not update invite code'}), 500

    return jsonify({
        'status': 'success',
        'message': 'Account created successfully'
    }), 201


@recorder_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status."""
    if require_auth():
        user = get_current_user()
        return jsonify({
            'authenticated': True,
            'user': {
                'username': session['user_id'],
                'name': user['name'],
                'role': user['role']
            }
        }), 200
    if is_guest():
        return jsonify({
            'authenticated': True,
            'user': {
                'username': 'guest',
                'name': 'Guest User',
                'role': 'guest'
            }
        }), 200
    return jsonify({'authenticated': False}), 200


__all__ = []