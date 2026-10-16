import uuid
import logging

from src.services.signup_notifications import notify_school_signup

from flask import jsonify, request, session

from . import recorder_bp
from .recaptcha import recaptcha_failure
from .app_config import default_admin_credentials_enabled
from .db import DEFAULT_SCHOOL_ID, AccountCreationRequest, User, _now_utc, db_session
from .passwords import hash_password, is_password_hash, verify_password
from .security import get_current_user, is_guest, password_session_token, require_auth
from .users import (
    create_user_record,
    get_invite_code_record,
    get_school_by_id,
    get_school_by_slug,
    get_user_by_username,
    mark_invite_code_used,
    serialize_school,
    serialize_user_model,
    DEVELOPMENT_SUPERADMIN_CREDENTIALS,
)

logger = logging.getLogger(__name__)


def _notify_saved_signup(school, account, *, invited=False):
    try:
        notify_school_signup(school, account, invited=invited)
    except Exception:
        logger.exception('Unable to notify reviewers of a saved account signup')


def _is_default_superadmin_login_attempt(username, password):
    normalized_username = (username or '').strip()
    for default_credentials in DEVELOPMENT_SUPERADMIN_CREDENTIALS:
        if normalized_username != default_credentials['username']:
            continue
        if verify_password(default_credentials['password_hash'], password or ''):
            return True
    return False


@recorder_bp.route('/auth/login', methods=['POST'])
def login():
    """User login."""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if (
        _is_default_superadmin_login_attempt(username, password)
        and not default_admin_credentials_enabled()
    ):
        return jsonify({'error': 'Default development admin credentials are disabled'}), 401

    user = get_user_by_username(username)
    if not user or not verify_password(user.password_hash, password):
        return jsonify({'error': 'Invalid username or password'}), 401

    if user.status != 'active':
        return jsonify({'error': 'Account is disabled. Please contact an administrator.'}), 403

    if not is_password_hash(user.password_hash):
        user.password_hash = hash_password(password)
    session['user_uuid'] = user.id
    session['user_id'] = username
    session['username'] = username
    session['school_id'] = user.school_id
    session['password_token'] = password_session_token(user)
    session.pop('guest_access', None)
    user.last_login_at = _now_utc()
    user.updated_at = _now_utc()
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to update login information'}), 500

    return jsonify({
        'status': 'success',
        'user': serialize_user_model(user),
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
    session.pop('password_token', None)
    return jsonify({'status': 'success', 'message': 'Logged out successfully'}), 200


@recorder_bp.route('/auth/guest/logout', methods=['POST'])
def guest_logout():
    """End a page-scoped guest visit without signing out a real account."""
    if is_guest():
        return logout()
    return jsonify({'status': 'success'}), 200


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
    session.pop('password_token', None)

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
    if require_auth() or is_guest():
        return jsonify({'error': 'Unable to sign up while signed in. Please log out and try again.', 'code': 'already_authenticated'}), 409
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    school_code = data.get('school_code', '').strip()
    invite_code = data.get('invite_code', '').strip()
    recaptcha_token = data.get('recaptcha_token', '')

    # Verify this endpoint's reCAPTCHA v3 action.
    failure = recaptcha_failure(recaptcha_token, 'account_signup')
    if failure:
        return jsonify({'error': failure.message, 'code': failure.code}), failure.status

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
            return jsonify({'error': 'Invalid or already used invite code'}), 403

        # Check if invite code has expired
        if invite.expires_at is not None:
            now = _now_utc()
            expires_at = invite.expires_at
            # Handle timezone-naive comparison
            if expires_at.tzinfo is None:
                from datetime import timezone
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now > expires_at:
                return jsonify({'error': 'Invite code has expired'}), 403

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
                password_hash=hash_password(password),
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
            invite.updated_at = _now_utc()
            db_session.commit()
        except Exception:
            db_session.rollback()
            return jsonify({'error': 'Could not create account with invite code'}), 500

        _notify_saved_signup(school, user, invited=True)
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
            password_hash=hash_password(password),
            display_name=name,
            status='pending',
            requested_at=_now_utc(),
        )
        db_session.add(account_request)
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Could not submit account request'}), 500

    _notify_saved_signup(school, account_request)
    return jsonify({
        'status': 'success',
        'message': 'Account request submitted. Your school superadmin must approve it before you can sign in.'
    }), 201


@recorder_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status."""
    if require_auth():
        user = get_current_user()
        return jsonify({
            'authenticated': True,
            'user': user,
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
