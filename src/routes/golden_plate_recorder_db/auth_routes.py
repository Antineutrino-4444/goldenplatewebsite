from flask import jsonify, request, session

from . import recorder_bp
from .db import (
    _now_utc,
    db_session,
    get_default_school_id,
    reset_current_school_id,
    set_current_school_id,
)
from .global_db import GlobalUser, School, global_db_session
from .schools import (
    get_directory_entry,
    get_directory_users_by_username,
    locate_school_by_code,
    log_audit_event,
)
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
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    global_user = (
        global_db_session.query(GlobalUser)
        .filter(GlobalUser.username == username)
        .first()
    )
    if global_user and global_user.password_hash == password:
        if global_user.status != 'active':
            return jsonify({'error': 'Account is disabled. Please contact an administrator.'}), 403

        session.clear()
        session['user_id'] = global_user.username
        session['role'] = 'global_admin'
        session['global_admin_id'] = global_user.id
        default_school_id = get_default_school_id()
        session['impersonated_school_id'] = default_school_id
        if default_school_id:
            session['school_id'] = default_school_id
            default_school = global_db_session.query(School).filter(School.id == default_school_id).first()
            session['school_code'] = default_school.code if default_school else None
        global_user.last_login_at = _now_utc()
        global_user.updated_at = _now_utc()
        global_db_session.add(global_user)
        global_db_session.commit()
        log_audit_event(
            school_id=None,
            actor_id=global_user.id,
            actor_scope='global',
            action='login',
            target=global_user.username,
        )
        return jsonify({
            'status': 'success',
            'user': {
                'username': global_user.username,
                'name': global_user.display_name,
                'role': 'global_admin',
            },
        }), 200

    directory_entries = get_directory_users_by_username(username)
    matched_entry = next((entry for entry in directory_entries if entry.password_hash == password), None)
    if not matched_entry:
        return jsonify({'error': 'Invalid username or password'}), 401

    school = global_db_session.query(School).filter(School.id == matched_entry.school_id).first()
    if not school or school.deleted_at is not None:
        return jsonify({'error': 'School account is no longer available'}), 403

    session.clear()
    session['school_id'] = matched_entry.school_id
    session['school_code'] = school.code
    token = set_current_school_id(matched_entry.school_id)
    try:
        user = get_user_by_username(username)
        if not user:
            return jsonify({'error': 'Account not found'}), 404
        if user.password_hash != password:
            return jsonify({'error': 'Invalid username or password'}), 401
        if user.status != 'active':
            return jsonify({'error': 'Account is disabled. Please contact an administrator.'}), 403
        user.last_login_at = _now_utc()
        user.updated_at = _now_utc()
        db_session.commit()
    finally:
        reset_current_school_id(token)

    session['user_id'] = username
    session['role'] = user.role
    log_audit_event(
        school_id=matched_entry.school_id,
        actor_id=user.id,
        actor_scope='school',
        action='login',
        target=username,
    )

    return jsonify({
        'status': 'success',
        'user': {
            'username': username,
            'name': user.display_name,
            'role': user.role,
            'school_code': school.code,
        }
    }), 200


@recorder_bp.route('/auth/logout', methods=['POST'])
def logout():
    """User logout."""
    session_keys = [
        'user_id',
        'session_id',
        'guest_access',
        'guest_school_id',
        'guest_school_code',
        'school_id',
        'school_code',
        'role',
        'global_admin_id',
        'impersonated_school_id',
    ]
    for key in session_keys:
        session.pop(key, None)
    return jsonify({'status': 'success', 'message': 'Logged out successfully'}), 200


@recorder_bp.route('/auth/guest', methods=['POST'])
def guest_login():
    """Guest login - allows viewing sessions for a specific school."""
    data = request.get_json(silent=True) or {}
    school_code = data.get('school_code', '').strip()
    if not school_code:
        default_id = get_default_school_id()
        if default_id:
            school = global_db_session.query(School).filter(School.id == default_id).first()
        else:
            school = locate_school_by_code('SAC1899')
    else:
        school = locate_school_by_code(school_code)
    if not school or school.deleted_at is not None:
        return jsonify({'error': 'School not found'}), 404

    if not school.guest_access_enabled:
        return jsonify({'error': 'Guest access disabled for this school'}), 403

    session['guest_access'] = True
    session['guest_school_id'] = school.id
    session['guest_school_code'] = school.code
    session.pop('school_id', None)
    session.pop('school_code', None)

    log_audit_event(
        school_id=school.id,
        actor_id=None,
        actor_scope='guest',
        action='guest_login',
        target=school.code,
    )

    return jsonify({
        'status': 'success',
        'user': {
            'username': 'guest',
            'name': 'Guest User',
            'role': 'guest',
            'school_code': school.code,
        }
    }), 200


@recorder_bp.route('/auth/signup', methods=['POST'])
def signup():
    """User signup."""
    data = request.get_json(silent=True) or {}
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

    invite = get_invite_code_record(invite_code)
    if not invite or invite.status != 'unused':
        return jsonify({'error': 'Invalid invite code'}), 403

    if invite.expires_at and invite.expires_at < _now_utc():
        return jsonify({'error': 'Invite code has expired'}), 403

    school_id = getattr(invite, 'school_id', None)
    if not school_id:
        school_id = session.get('school_id')

    if not school_id:
        return jsonify({'error': 'Invite code is not associated with a school'}), 400

    existing_entry = get_directory_entry(school_id, username)
    if existing_entry:
        return jsonify({'error': 'Username already exists for this school'}), 409

    token = set_current_school_id(school_id)
    try:
        new_user = create_user_record(
            username,
            password,
            name,
            role=invite.role or 'user',
            status='active'
        )
    finally:
        reset_current_school_id(token)

    if not new_user:
        return jsonify({'error': 'Could not create user'}), 500

    try:
        mark_invite_code_used(invite, new_user)
    except Exception:
        token_cleanup = set_current_school_id(school_id)
        try:
            user_to_delete = get_user_by_username(username)
            if user_to_delete:
                try:
                    db_session.delete(user_to_delete)
                    db_session.commit()
                except Exception:
                    db_session.rollback()
        finally:
            reset_current_school_id(token_cleanup)
        return jsonify({'error': 'Could not update invite code'}), 500

    log_audit_event(
        school_id=school_id,
        actor_id=new_user.id,
        actor_scope='school',
        action='signup',
        target=username,
    )

    return jsonify({
        'status': 'success',
        'message': 'Account created successfully'
    }), 201


@recorder_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status."""
    if require_auth():
        user = get_current_user()
        school_code = session.get('school_code') or session.get('guest_school_code')
        if session.get('global_admin_id') and session.get('impersonated_school_id'):
            impersonated_school = (
                global_db_session.query(School)
                .filter(School.id == session['impersonated_school_id'])
                .first()
            )
            school_code = impersonated_school.code if impersonated_school else school_code
        return jsonify({
            'authenticated': True,
            'user': {
                'username': session['user_id'],
                'name': user['name'],
                'role': user['role'],
                'school_code': school_code,
            }
        }), 200
    if is_guest():
        return jsonify({
            'authenticated': True,
            'user': {
                'username': 'guest',
                'name': 'Guest User',
                'role': 'guest',
                'school_code': session.get('guest_school_code'),
            }
        }), 200
    return jsonify({'authenticated': False}), 200


__all__ = []