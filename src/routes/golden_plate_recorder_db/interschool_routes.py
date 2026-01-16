import os
import re
import uuid

import requests as http_requests
from flask import jsonify, request
from sqlalchemy import func

from . import recorder_bp
from .db import (
    DEFAULT_SCHOOL_ID,
    INTERSCHOOL_SCHOOL_ID,
    School,
    SchoolInviteCode,
    SchoolRegistrationRequest,
    User,
    _now_utc,
    db_session,
)
from .email_service import (
    create_verification_code,
    VERIFICATION_CODE_EXPIRY_MINUTES,
    is_email_verified,
    send_verification_email,
    verify_code as verify_email_code,
)
from .security import get_current_user, is_interschool_user, require_auth
from .users import (
    create_school_invite_code_record,
    get_school_invite_code_record,
    get_user_by_username,
)

RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '')
RECAPTCHA_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'


def verify_recaptcha(token):
    """Verify reCAPTCHA token with Google's API."""
    if not RECAPTCHA_SECRET_KEY:
        return True

    if not token:
        return False

    try:
        response = http_requests.post(
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
        return False


def _serialize_school_model(school, *, user_counts=None):
    user_counts = user_counts or {}
    if not school:
        return None
    return {
        'id': school.id,
        'name': school.name,
        'slug': school.slug,
        'status': school.status,
        'created_at': school.created_at.isoformat() if school.created_at else None,
        'updated_at': school.updated_at.isoformat() if school.updated_at else None,
        'user_count': user_counts.get(school.id, 0),
    }


def _serialize_invite_model(invite, user_lookup):
    if not invite:
        return None
    issued_by_user = user_lookup.get(invite.issued_by) if invite.issued_by else None
    used_by_user = user_lookup.get(invite.used_by) if invite.used_by else None
    return {
        'id': invite.id,
        'code': invite.code,
        'school_id': invite.school_id,
        'status': invite.status,
        'issued_at': invite.issued_at.isoformat() if invite.issued_at else None,
        'used_at': invite.used_at.isoformat() if invite.used_at else None,
        'issued_by': None if not issued_by_user else {
            'id': issued_by_user.id,
            'username': issued_by_user.username,
            'display_name': issued_by_user.display_name,
        },
        'used_by': None if not used_by_user else {
            'id': used_by_user.id,
            'username': used_by_user.username,
            'display_name': used_by_user.display_name,
        },
    }


def _normalize_slug(value: str) -> str:
    base = (value or '').strip().lower()
    slug = re.sub(r'[^a-z0-9]+', '-', base)
    slug = slug.strip('-')
    if not slug:
        slug = f'school-{uuid.uuid4().hex[:6]}'
    return slug


@recorder_bp.route('/interschool/school-invite', methods=['POST'])
def create_school_invite():
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if not is_interschool_user():
        return jsonify({'error': 'Interschool access required'}), 403

    current = get_current_user()
    issued_by = get_user_by_username(current['username'], school_id=current['school_id']) if current else None
    if not issued_by:
        return jsonify({'error': 'Unable to resolve issuing user'}), 500

    try:
        invite = create_school_invite_code_record(issued_by)
    except Exception:
        return jsonify({'error': 'Unable to create school invite code'}), 500

    return jsonify({
        'status': 'success',
        'invite_code': invite.code,
        'school_id': invite.school_id,
    }), 201


@recorder_bp.route('/auth/send-verification-code', methods=['POST'])
def send_verification_code():
    """Send a verification code to the provided email address."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    recaptcha_token = (data.get('recaptcha_token') or '').strip()

    # Verify reCAPTCHA if configured
    if RECAPTCHA_SECRET_KEY and not verify_recaptcha(recaptcha_token):
        return jsonify({'error': 'reCAPTCHA verification failed. Please try again.'}), 400

    if not email:
        return jsonify({'error': 'Email address is required'}), 400

    # Basic email validation
    if '@' not in email or '.' not in email:
        return jsonify({'error': 'Please enter a valid email address'}), 400

    # Check if there's already a pending request with this email
    existing_request = db_session.query(SchoolRegistrationRequest).filter(
        SchoolRegistrationRequest.email == email,
        SchoolRegistrationRequest.status == 'pending'
    ).first()
    if existing_request:
        return jsonify({'error': 'A registration request with this email is already pending approval'}), 409

    try:
        # Create verification code
        verification = create_verification_code(email, purpose='school_registration')

        # Send email
        result = send_verification_email(email, verification.code)

        if not result.get('success'):
            return jsonify({
                'error': 'Failed to send verification email. Please try again.',
                'detail': result.get('error'),
            }), 500

        return jsonify({
            'status': 'success',
            'message': 'Verification code sent to your email address.',
            'expiry_minutes': VERIFICATION_CODE_EXPIRY_MINUTES,
        }), 200

    except Exception as e:
        db_session.rollback()
        return jsonify({'error': 'Failed to send verification code. Please try again.'}), 500


@recorder_bp.route('/auth/verify-email-code', methods=['POST'])
def verify_email_code_endpoint():
    """Verify an email verification code."""
    import logging
    logger = logging.getLogger(__name__)

    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()

    logger.info(f'Verify email code endpoint called: email={email}, code_length={len(code)}')

    if not email or not code:
        logger.warning(f'Missing required fields: email={bool(email)}, code={bool(code)}')
        return jsonify({
            'error': 'Email and verification code are required',
            'debug': {
                'email_provided': bool(email),
                'code_provided': bool(code),
            }
        }), 400

    # Ensure code is exactly 6 digits
    if not code.isdigit():
        logger.warning(f'Code is not all digits: "{code}"')
        return jsonify({
            'error': 'Verification code must contain only digits',
            'debug': {
                'code_length': len(code),
                'is_digit': code.isdigit(),
            }
        }), 400

    if len(code) != 6:
        logger.warning(f'Code length incorrect: {len(code)} (expected 6)')
        return jsonify({
            'error': f'Verification code must be exactly 6 digits (received {len(code)})',
            'debug': {
                'code_length': len(code),
            }
        }), 400

    try:
        result = verify_email_code(email, code, purpose='school_registration')

        if not result.get('valid'):
            error_msg = result.get('error', 'Invalid verification code')
            debug_info = result.get('debug', {})
            logger.warning(f'Verification failed for {email}: {error_msg}')
            response_data = {'error': error_msg}
            if debug_info:
                response_data['debug'] = debug_info
            return jsonify(response_data), 400

        logger.info(f'Email verified successfully: {email}')
        return jsonify({
            'status': 'success',
            'message': 'Email verified successfully.',
            'verified': True,
        }), 200

    except Exception as e:
        db_session.rollback()
        logger.exception(f'Exception during verification for {email}: {str(e)}')
        return jsonify({
            'error': 'Failed to verify code. Please try again.',
            'debug': {
                'exception': str(e),
            }
        }), 500


@recorder_bp.route('/auth/register-school', methods=['POST'])
def register_school():
    """Submit a school registration request for interschool admin approval."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    school_name = (data.get('school_name') or '').strip()
    school_slug = (data.get('school_slug') or '').strip()
    invite_code = (data.get('invite_code') or '').strip()
    invite_school_id = (data.get('school_id') or '').strip()
    admin_username = (data.get('admin_username') or '').strip()
    admin_password = (data.get('admin_password') or '').strip()
    admin_display_name = (data.get('admin_display_name') or '').strip()
    recaptcha_token = (data.get('recaptcha_token') or '').strip()

    # Verify reCAPTCHA if configured
    if RECAPTCHA_SECRET_KEY and not verify_recaptcha(recaptcha_token):
        return jsonify({'error': 'reCAPTCHA verification failed. Please try again.'}), 400

    if not school_name or not admin_username or not admin_password or not admin_display_name:
        return jsonify({'error': 'School name and admin credentials are required'}), 400

    if not invite_code:
        if not email:
            return jsonify({'error': 'Email, school name, and admin credentials are required'}), 400

        # Basic email validation
        if '@' not in email or '.' not in email:
            return jsonify({'error': 'Please enter a valid email address'}), 400

    if len(admin_username) < 3:
        return jsonify({'error': 'Admin username must be at least 3 characters long'}), 400

    if len(admin_password) < 6:
        return jsonify({'error': 'Admin password must be at least 6 characters long'}), 400

    if invite_code:
        invite = get_school_invite_code_record(invite_code)
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

        if invite_school_id and invite_school_id != invite.school_id:
            return jsonify({'error': 'Invite code does not match the provided school ID'}), 400

        existing_school = db_session.query(School).filter(School.id == invite.school_id).first()
        if existing_school:
            return jsonify({'error': 'A school has already been registered with this invite code'}), 409
    else:
        # Check if email has been verified
        if not is_email_verified(email.lower(), purpose='school_registration'):
            return jsonify({'error': 'Please verify your email address before submitting the registration'}), 400

    if not invite_code:
        # Check for existing pending request with same email
        existing_request = db_session.query(SchoolRegistrationRequest).filter(
            SchoolRegistrationRequest.email == email,
            SchoolRegistrationRequest.status == 'pending'
        ).first()
        if existing_request:
            return jsonify({'error': 'A registration request with this email is already pending approval'}), 409

    if not invite_code:
        # Check for existing pending request with same school name
        existing_name_request = db_session.query(SchoolRegistrationRequest).filter(
            func.lower(SchoolRegistrationRequest.school_name) == school_name.lower(),
            SchoolRegistrationRequest.status == 'pending'
        ).first()
        if existing_name_request:
            return jsonify({'error': 'A registration request for this school name is already pending approval'}), 409

    # Check if school name already exists
    normalized_slug = _normalize_slug(school_slug or school_name)
    slug_conflict = (
        db_session.query(School)
        .filter(func.lower(School.slug) == normalized_slug.lower())
        .first()
    )
    if slug_conflict:
        return jsonify({'error': 'A school with this name or code already exists'}), 409

    # Ensure username availability
    if get_user_by_username(admin_username):
        return jsonify({'error': 'Username already exists'}), 409

    if invite_code:
        school_id = invite.school_id
        new_school = School(
            id=school_id,
            name=school_name,
            slug=normalized_slug,
            status='active',
            created_at=_now_utc(),
            updated_at=_now_utc(),
        )

        admin_user = User(
            id=str(uuid.uuid4()),
            school_id=school_id,
            username=admin_username,
            password_hash=admin_password,
            display_name=admin_display_name,
            role='superadmin',
            status='active',
            created_at=_now_utc(),
            updated_at=_now_utc(),
        )

        invite.status = 'used'
        invite.used_by = admin_user.id
        invite.used_at = _now_utc()

        try:
            db_session.add(new_school)
            db_session.add(admin_user)
            db_session.commit()
        except Exception:
            db_session.rollback()
            return jsonify({'error': 'Unable to create school with invite code'}), 500

        return jsonify({
            'status': 'success',
            'message': 'School created successfully using the invite code.',
            'school': {
                'id': new_school.id,
                'name': new_school.name,
                'slug': new_school.slug,
            },
            'admin_user': {
                'username': admin_user.username,
                'display_name': admin_user.display_name,
            },
        }), 201

    try:
        registration_request = SchoolRegistrationRequest(
            email=email,
            school_name=school_name,
            school_slug=school_slug or None,
            admin_username=admin_username,
            admin_password_hash=admin_password,
            admin_display_name=admin_display_name,
            status='pending',
            requested_at=_now_utc(),
        )
        db_session.add(registration_request)
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Could not submit registration request'}), 500

    return jsonify({
        'status': 'success',
        'message': 'School registration request submitted successfully. Please wait for approval from the PLATE administrator.'
    }), 201


@recorder_bp.route('/interschool/overview', methods=['GET'])
def get_interschool_overview():
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if not is_interschool_user():
        return jsonify({'error': 'Interschool access required'}), 403

    schools = (
        db_session.query(School)
        .order_by(func.lower(School.name).asc())
        .all()
    )

    user_counts = dict(
        db_session.query(User.school_id, func.count(User.id))
        .group_by(User.school_id)
        .all()
    )

    invites = (
        db_session.query(SchoolInviteCode)
        .order_by(SchoolInviteCode.issued_at.desc())
        .all()
    )

    user_ids = {
        ident
        for entry in invites
        for ident in [entry.issued_by, entry.used_by]
        if ident
    }

    user_lookup = {}
    if user_ids:
        user_lookup = {
            user.id: user
            for user in db_session.query(User).filter(User.id.in_(user_ids)).all()
        }

    # Also include pending school registration requests
    registration_requests = (
        db_session.query(SchoolRegistrationRequest)
        .order_by(SchoolRegistrationRequest.requested_at.desc())
        .all()
    )

    return jsonify({
        'status': 'success',
        'schools': [_serialize_school_model(school, user_counts=user_counts) for school in schools],
        'invites': [_serialize_invite_model(invite, user_lookup) for invite in invites],
        'registration_requests': [_serialize_registration_request(req) for req in registration_requests],
    }), 200


def _serialize_registration_request(req):
    if not req:
        return None
    return {
        'id': req.id,
        'email': req.email,
        'school_name': req.school_name,
        'school_slug': req.school_slug,
        'admin_username': req.admin_username,
        'admin_display_name': req.admin_display_name,
        'status': req.status,
        'requested_at': req.requested_at.isoformat() if req.requested_at else None,
        'reviewed_at': req.reviewed_at.isoformat() if req.reviewed_at else None,
        'rejection_reason': req.rejection_reason,
    }


@recorder_bp.route('/interschool/registration-requests', methods=['GET'])
def get_registration_requests():
    """Get all pending school registration requests."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if not is_interschool_user():
        return jsonify({'error': 'Interschool access required'}), 403

    requests_list = (
        db_session.query(SchoolRegistrationRequest)
        .filter(SchoolRegistrationRequest.status == 'pending')
        .order_by(SchoolRegistrationRequest.requested_at.desc())
        .all()
    )

    return jsonify({
        'status': 'success',
        'requests': [_serialize_registration_request(req) for req in requests_list],
    }), 200


@recorder_bp.route('/interschool/registration-requests/<request_id>/approve', methods=['POST'])
def approve_registration_request(request_id):
    """Approve a school registration request and create the school."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if not is_interschool_user():
        return jsonify({'error': 'Interschool access required'}), 403

    current = get_current_user()
    reviewer = get_user_by_username(current['username'], school_id=current['school_id']) if current else None
    if not reviewer:
        return jsonify({'error': 'Unable to resolve reviewing user'}), 500

    reg_request = db_session.query(SchoolRegistrationRequest).filter(
        SchoolRegistrationRequest.id == request_id
    ).first()

    if not reg_request:
        return jsonify({'error': 'Registration request not found'}), 404

    if reg_request.status != 'pending':
        return jsonify({'error': 'This request has already been processed'}), 400

    # Re-validate that the school can still be created
    normalized_slug = _normalize_slug(reg_request.school_slug or reg_request.school_name)
    slug_conflict = (
        db_session.query(School)
        .filter(func.lower(School.slug) == normalized_slug.lower())
        .first()
    )
    if slug_conflict:
        return jsonify({'error': 'A school with this name or code already exists'}), 409

    if get_user_by_username(reg_request.admin_username):
        return jsonify({'error': 'The requested admin username already exists'}), 409

    school_id = str(uuid.uuid4())

    new_school = School(
        id=school_id,
        name=reg_request.school_name,
        slug=normalized_slug,
        status='active',
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )

    admin_user = User(
        id=str(uuid.uuid4()),
        school_id=school_id,
        username=reg_request.admin_username,
        password_hash=reg_request.admin_password_hash,
        display_name=reg_request.admin_display_name,
        role='superadmin',
        status='active',
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )

    reg_request.status = 'approved'
    reg_request.reviewed_by = reviewer.id
    reg_request.reviewed_at = _now_utc()

    try:
        db_session.add(new_school)
        db_session.add(admin_user)
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to create school'}), 500

    return jsonify({
        'status': 'success',
        'message': f'School "{new_school.name}" has been approved and created.',
        'school': {
            'id': new_school.id,
            'name': new_school.name,
            'slug': new_school.slug,
        },
        'admin_user': {
            'username': admin_user.username,
            'display_name': admin_user.display_name,
        }
    }), 200


@recorder_bp.route('/interschool/registration-requests/<request_id>/reject', methods=['POST'])
def reject_registration_request(request_id):
    """Reject a school registration request."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if not is_interschool_user():
        return jsonify({'error': 'Interschool access required'}), 403

    current = get_current_user()
    reviewer = get_user_by_username(current['username'], school_id=current['school_id']) if current else None
    if not reviewer:
        return jsonify({'error': 'Unable to resolve reviewing user'}), 500

    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '').strip()

    reg_request = db_session.query(SchoolRegistrationRequest).filter(
        SchoolRegistrationRequest.id == request_id
    ).first()

    if not reg_request:
        return jsonify({'error': 'Registration request not found'}), 404

    if reg_request.status != 'pending':
        return jsonify({'error': 'This request has already been processed'}), 400

    reg_request.status = 'rejected'
    reg_request.reviewed_by = reviewer.id
    reg_request.reviewed_at = _now_utc()
    reg_request.rejection_reason = reason or None

    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to reject registration request'}), 500

    return jsonify({
        'status': 'success',
        'message': f'Registration request for "{reg_request.school_name}" has been rejected.',
    }), 200


@recorder_bp.route('/interschool/schools/<school_id>', methods=['DELETE'])
def delete_school(school_id):
    """Delete a school and all associated data."""
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if not is_interschool_user():
        return jsonify({'error': 'Interschool access required'}), 403

    # Prevent deletion of system schools
    protected_school_ids = {DEFAULT_SCHOOL_ID, INTERSCHOOL_SCHOOL_ID}
    if school_id in protected_school_ids:
        return jsonify({'error': 'Cannot delete system schools'}), 403

    school = db_session.query(School).filter(School.id == school_id).first()

    if not school:
        return jsonify({'error': 'School not found'}), 404

    school_name = school.name

    try:
        # Delete all users associated with this school
        db_session.query(User).filter(User.school_id == school_id).delete()

        # Delete the school (cascade will handle related records)
        db_session.delete(school)
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to delete school'}), 500

    return jsonify({
        'status': 'success',
        'message': f'School "{school_name}" has been deleted.',
    }), 200


__all__ = []
