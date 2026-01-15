import os
import uuid

import requests
from flask import jsonify, request, session

from . import recorder_bp
from .db import DEFAULT_SCHOOL_ID, AccountCreationRequest, User, _now_utc, db_session
from .security import get_current_user, is_guest, require_auth
from .users import (
    create_user_record,
    get_invite_code_record,
    get_school_by_id,
    get_school_by_slug,
    get_user_by_username,
    mark_invite_code_used,
    serialize_school,
)

RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '')
RECAPTCHA_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'


def verify_recaptcha(token):
    """Verify reCAPTCHA token with Google's API.

    Returns True if verification succeeds or if reCAPTCHA is not configured.
    Returns False if verification fails.
    """
    if not RECAPTCHA_SECRET_KEY:
        # reCAPTCHA not configured, skip verification
        return True

    if not token:
        return False

    try:
        response = requests.post(
            RECAPTCHA_VERIFY_URL,
            data={
                'secret': RECAPTCHA_SECRET_KEY,
                'response': token,
            },
            timeout=10,
        )
        result = response.json()
        return result.get('success', False)
    except Exception:
        # If verification request fails, deny signup for safety
        return False


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

    session['user_uuid'] = user.id
    session['user_id'] = username
    session['username'] = username
    session['school_id'] = user.school_id
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
            'role': user.role,
            'school_id': user.school_id,
            'school': serialize_school(user.school) if getattr(user, 'school', None) else None,
        }
    }), 200


@recorder_bp.route('/auth/logout', methods=['POST'])
def logout():
    """User logout."""
    session.pop('user_id', None)
    session.pop('user_uuid', None)
    session.pop('username', None)
    session.pop('school_id', None)
    session.pop('session_id', None)
    session.pop('guest_access', None)
    return jsonify({'status': 'success', 'message': 'Logged out successfully'}), 200


@recorder_bp.route('/auth/guest', methods=['POST'])
def guest_login():
    """Guest login - allows viewing sessions without signup."""
    data = request.get_json(silent=True) or {}
    requested_slug = (data.get('school_slug') or '').strip()
    requested_id = (data.get('school_id') or '').strip()

    target_school = None
    if requested_slug:
        target_school = get_school_by_slug(requested_slug)
        if not target_school:
            return jsonify({'error': 'School not found'}), 404
    elif requested_id:
        target_school = get_school_by_id(requested_id)
        if not target_school:
            return jsonify({'error': 'School not found'}), 404
    else:
        return jsonify({'error': 'School slug is required for guest access'}), 400

    if not target_school or target_school.status != 'active':
        return jsonify({'error': 'School is not available for guest access'}), 403

    # Ensure any previous authenticated session is cleared before entering guest mode.
    session.pop('user_id', None)
    session.pop('user_uuid', None)
    session.pop('username', None)

    session['guest_access'] = True
    session['school_id'] = target_school.id

    return jsonify({
        'status': 'success',
        'user': {
            'username': 'guest',
            'name': 'Guest User',
            'role': 'guest',
            'school_id': target_school.id,
            'school': serialize_school(target_school),
        }
    }), 200


@recorder_bp.route('/auth/signup', methods=['POST'])
def signup():
    """User signup - creates a pending account request for superadmin approval."""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    school_code = data.get('school_code', '').strip()
    invite_code = data.get('invite_code', '').strip()
    recaptcha_token = data.get('recaptcha_token', '').strip()

    # Verify reCAPTCHA if configured
    if RECAPTCHA_SECRET_KEY and not verify_recaptcha(recaptcha_token):
        return jsonify({'error': 'reCAPTCHA verification failed. Please try again.'}), 400

    if not username or not password or not name or (not school_code and not invite_code):
        error_message = 'Username, password, name, and school code are required'
        if invite_code:
            error_message = 'Username, password, name, and invite code are required'
        return jsonify({'error': error_message}), 400

    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters long'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400

    if invite_code:
        invite = get_invite_code_record(invite_code)
        if not invite or invite.status != 'unused':
            return jsonify({'error': 'Invalid invite code'}), 403

        school = get_school_by_id(invite.school_id)
        if not school:
            return jsonify({'error': 'Invite code is not tied to an active school'}), 404

        if school.status != 'active':
            return jsonify({'error': 'This school is not accepting new registrations'}), 403

        if get_user_by_username(username, school_id=invite.school_id):
            return jsonify({'error': 'Username already exists in this school'}), 409

        if get_user_by_username(username):
            return jsonify({'error': 'Username already exists'}), 409

        try:
            user = User(
                id=str(uuid.uuid4()),
                school_id=invite.school_id,
                username=username,
                password_hash=password,
                display_name=name,
                role=invite.role or 'user',
                status='active',
                created_at=_now_utc(),
                updated_at=_now_utc(),
            )
            db_session.add(user)
            invite.status = 'used'
            invite.user_id = user.id
            invite.used_by = user.id
            invite.used_at = _now_utc()
            invite.school_id = user.school_id
            invite.updated_at = _now_utc()
            db_session.commit()
        except Exception:
            db_session.rollback()
            return jsonify({'error': 'Could not create account with invite code'}), 500

        return jsonify({
            'status': 'success',
            'message': 'Account created successfully.'
        }), 201

    # Find the school by slug (school code)
    school = get_school_by_slug(school_code)
    if not school:
        return jsonify({'error': 'Invalid school code. Please check with your administrator.'}), 404

    if school.status != 'active':
        return jsonify({'error': 'This school is not accepting new registrations'}), 403

    # Check if username already exists in this school
    if get_user_by_username(username, school_id=school.id):
        return jsonify({'error': 'Username already exists in this school'}), 409

    # Check if username already exists globally (to prevent confusion)
    if get_user_by_username(username):
        return jsonify({'error': 'Username already exists'}), 409

    # Check if there's already a pending request for this username in this school
    existing_request = db_session.query(AccountCreationRequest).filter(
        AccountCreationRequest.school_id == school.id,
        AccountCreationRequest.username == username,
        AccountCreationRequest.status == 'pending'
    ).first()

    if existing_request:
        return jsonify({'error': 'A request for this username is already pending approval'}), 409

    try:
        account_request = AccountCreationRequest(
            school_id=school.id,
            username=username,
            password_hash=password,
            display_name=name,
            status='pending',
            requested_at=_now_utc(),
        )
        db_session.add(account_request)
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Could not submit account request'}), 500

    return jsonify({
        'status': 'success',
        'message': 'Account request submitted successfully. Please wait for your school administrator to approve your request.'
    }), 201


@recorder_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status."""
    if require_auth():
        user = get_current_user()
        return jsonify({
            'authenticated': True,
            'user': {
                'username': session.get('username'),
                'name': user['name'],
                'role': user['role'],
                'school_id': user['school_id'],
                'school': user.get('school'),
            }
        }), 200
    if is_guest():
        school_id = session.get('school_id', DEFAULT_SCHOOL_ID)
        school = get_school_by_id(school_id)
        return jsonify({
            'authenticated': True,
            'user': {
                'username': 'guest',
                'name': 'Guest User',
                'role': 'guest',
                'school_id': school_id,
                'school': serialize_school(school) if school else None,
            }
        }), 200
    return jsonify({'authenticated': False}), 200


__all__ = []
