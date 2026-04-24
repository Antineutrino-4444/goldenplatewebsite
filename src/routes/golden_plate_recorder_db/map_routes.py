import logging
import os
import random
import string
from datetime import timedelta, timezone
from io import BytesIO

import requests as http_requests
from flask import jsonify, request, send_file, session
from sqlalchemy import func
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from . import recorder_bp
from .db import DEFAULT_SCHOOL_ID
from .email_service import VERIFICATION_CODE_EXPIRY_MINUTES, send_email_via_brevo
from .map_db import (
    MapEmailVerification,
    MapSubmission,
    MapSubmitterAccount,
    _map_now_utc,
    map_db_session,
)
from .security import get_current_user, require_admin, require_auth_or_guest

logger = logging.getLogger(__name__)

MAP_VERIFICATION_PURPOSE = 'map_submission'
MAX_VERIFICATION_ATTEMPTS = 5
MAP_EMAIL_VERIFICATION_MAX_AGE_MINUTES = 30
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_MIMES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
SAC_EMAIL_SUFFIX = '@sac.on.ca'

RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '')
RECAPTCHA_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'


def _map_error(code, message, status=400, *, detail=None):
    payload = {
        'status': 'error',
        'code': code,
        'error': message,
        'http_status': status,
    }
    if detail:
        payload['detail'] = detail
    return jsonify(payload), status


@recorder_bp.app_errorhandler(RequestEntityTooLarge)
def handle_map_request_too_large(error):
    if request.path.startswith('/api/map/'):
        return _map_error(
            'MAP_IMAGE_TOO_LARGE',
            'Image must be 5 MB or smaller',
            413,
        )
    return error.get_response()


def _verify_recaptcha(token):
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


def _normalize_email(value):
    return (value or '').strip().lower()


def _is_sac_email(email):
    return _normalize_email(email).endswith(SAC_EMAIL_SUFFIX)


def _generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))


def _create_map_verification_code(email):
    normalized = _normalize_email(email)
    pending_codes = (
        map_db_session.query(MapEmailVerification)
        .filter(
            func.lower(MapEmailVerification.email) == normalized,
            MapEmailVerification.purpose == MAP_VERIFICATION_PURPOSE,
            MapEmailVerification.verified_at.is_(None),
        )
        .all()
    )
    for code_record in pending_codes:
        map_db_session.delete(code_record)

    verification = MapEmailVerification(
        email=normalized,
        code=_generate_verification_code(),
        purpose=MAP_VERIFICATION_PURPOSE,
        expires_at=_map_now_utc() + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES),
        attempts=0,
    )
    map_db_session.add(verification)
    map_db_session.commit()
    return verification


def _send_map_verification_email(email, code):
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                line-height: 1.6;
                color: #1f2937;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: #0f766e;
                color: white;
                padding: 26px;
                text-align: center;
                border-radius: 8px 8px 0 0;
            }}
            .content {{
                background: #ffffff;
                padding: 28px;
                border: 1px solid #e5e7eb;
                border-top: none;
                border-radius: 0 0 8px 8px;
            }}
            .code-box {{
                background: #ecfdf5;
                border: 2px solid #0f766e;
                border-radius: 8px;
                padding: 18px;
                text-align: center;
                margin: 20px 0;
            }}
            .code {{
                font-size: 32px;
                font-weight: 800;
                letter-spacing: 8px;
                color: #134e4a;
                font-family: 'Courier New', monospace;
            }}
            .footer {{
                text-align: center;
                color: #6b7280;
                font-size: 12px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1 style="margin: 0; font-size: 24px;">Golden Plate Map</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Submission Verification</p>
        </div>
        <div class="content">
            <p>Hello,</p>
            <p>Use this verification code to submit to the Golden Plate Map:</p>
            <div class="code-box">
                <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 14px;">Your Verification Code</p>
                <div class="code">{code}</div>
            </div>
            <p>This code will expire in <strong>{VERIFICATION_CODE_EXPIRY_MINUTES} minutes</strong>.</p>
            <p>If you did not request this code, you can ignore this message.</p>
        </div>
        <div class="footer">
            <p>This is an automated message from Golden Plate Recorder.</p>
        </div>
    </body>
    </html>
    '''
    return send_email_via_brevo(email, 'Golden Plate Map - Email Verification Code', html_content)


def _verify_map_email_code(email, code):
    normalized_email = _normalize_email(email)
    normalized_code = (code or '').strip()

    if not normalized_email:
        return {'valid': False, 'code': 'MAP_EMAIL_REQUIRED', 'error': 'Email address is required'}

    if not normalized_code:
        return {'valid': False, 'code': 'MAP_VERIFICATION_CODE_REQUIRED', 'error': 'Verification code is required'}

    verification = (
        map_db_session.query(MapEmailVerification)
        .filter(
            func.lower(MapEmailVerification.email) == normalized_email,
            MapEmailVerification.purpose == MAP_VERIFICATION_PURPOSE,
            MapEmailVerification.verified_at.is_(None),
        )
        .order_by(MapEmailVerification.created_at.desc())
        .first()
    )
    if not verification:
        return {
            'valid': False,
            'code': 'MAP_VERIFICATION_CODE_NOT_FOUND',
            'error': 'No pending verification code found. Please request a new one.',
        }

    now = _map_now_utc()
    expires_at = verification.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        return {
            'valid': False,
            'code': 'MAP_VERIFICATION_CODE_EXPIRED',
            'error': 'Verification code has expired. Please request a new one.',
        }

    if verification.attempts >= MAX_VERIFICATION_ATTEMPTS:
        return {
            'valid': False,
            'code': 'MAP_VERIFICATION_ATTEMPTS_EXCEEDED',
            'error': 'Too many failed attempts. Please request a new code.',
        }

    if (verification.code or '').strip() != normalized_code:
        verification.attempts += 1
        map_db_session.commit()
        remaining = MAX_VERIFICATION_ATTEMPTS - verification.attempts
        if remaining > 0:
            return {
                'valid': False,
                'code': 'MAP_VERIFICATION_CODE_MISMATCH',
                'error': f'Invalid verification code. {remaining} attempts remaining.',
            }
        return {
            'valid': False,
            'code': 'MAP_VERIFICATION_ATTEMPTS_EXCEEDED',
            'error': 'Too many failed attempts. Please request a new code.',
        }

    verification.verified_at = now
    map_db_session.commit()
    return {'valid': True, 'verification_id': verification.id}


def _is_map_email_verified(email):
    normalized_email = _normalize_email(email)
    cutoff = _map_now_utc() - timedelta(minutes=MAP_EMAIL_VERIFICATION_MAX_AGE_MINUTES)
    verification = (
        map_db_session.query(MapEmailVerification)
        .filter(
            func.lower(MapEmailVerification.email) == normalized_email,
            MapEmailVerification.purpose == MAP_VERIFICATION_PURPOSE,
            MapEmailVerification.verified_at.isnot(None),
            MapEmailVerification.verified_at >= cutoff,
        )
        .first()
    )
    return verification is not None


def _current_identity():
    user = get_current_user()
    if user:
        return {
            'user_id': user.get('id'),
            'username': user.get('username') or session.get('username'),
            'display_name': user.get('name') or user.get('username'),
            'role': user.get('role') or 'user',
            'school_id': user.get('school_id') or session.get('school_id') or DEFAULT_SCHOOL_ID,
        }

    return {
        'user_id': None,
        'username': 'guest',
        'display_name': 'Guest User',
        'role': 'guest',
        'school_id': session.get('school_id') or DEFAULT_SCHOOL_ID,
    }


def _current_school_id():
    return _current_identity()['school_id']


def _serialize_submission(submission):
    return {
        'id': submission.id,
        'school_id': submission.school_id,
        'email': submission.email,
        'text': submission.text_content,
        'image_filename': submission.image_filename,
        'image_mime': submission.image_mime,
        'image_size': submission.image_size,
        'image_url': f'/api/map/submissions/{submission.id}/image' if submission.image_data else None,
        'status': submission.status,
        'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
        'submitted_by': {
            'user_id': submission.submitted_user_id,
            'username': submission.submitted_username,
            'display_name': submission.submitted_display_name,
            'role': submission.submitted_role,
        },
        'reviewed_at': submission.reviewed_at.isoformat() if submission.reviewed_at else None,
        'reviewed_by': None if not submission.reviewed_username else {
            'user_id': submission.reviewed_user_id,
            'username': submission.reviewed_username,
            'display_name': submission.reviewed_display_name,
            'role': submission.reviewed_role,
        },
        'rejection_reason': submission.rejection_reason,
    }


def _get_submitter_account(email):
    normalized_email = _normalize_email(email)
    return (
        map_db_session.query(MapSubmitterAccount)
        .filter(func.lower(MapSubmitterAccount.email) == normalized_email)
        .first()
    )


def _verify_submitter_password(email, password):
    account = _get_submitter_account(email)
    if not account or account.status != 'active':
        return False, None
    if not check_password_hash(account.password_hash, password or ''):
        return False, account
    account.last_used_at = _map_now_utc()
    account.updated_at = _map_now_utc()
    return True, account


def _upsert_submitter_password(email, password, school_id, submission_id):
    account = _get_submitter_account(email)
    password_hash = generate_password_hash(password)
    now = _map_now_utc()

    if account:
        account.password_hash = password_hash
        account.status = 'active'
        account.school_id = school_id
        account.updated_at = now
        account.created_from_submission_id = account.created_from_submission_id or submission_id
        return account

    account = MapSubmitterAccount(
        school_id=school_id,
        email=_normalize_email(email),
        password_hash=password_hash,
        status='active',
        created_at=now,
        updated_at=now,
        created_from_submission_id=submission_id,
    )
    map_db_session.add(account)
    return account


@recorder_bp.route('/map/submissions', methods=['GET'])
def get_approved_map_submissions():
    if not require_auth_or_guest():
        return _map_error('MAP_AUTH_REQUIRED', 'Authentication or guest access required', 401)

    school_id = _current_school_id()
    submissions = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.school_id == school_id, MapSubmission.status == 'approved')
        .order_by(MapSubmission.submitted_at.desc())
        .all()
    )
    return jsonify({
        'status': 'success',
        'submissions': [_serialize_submission(submission) for submission in submissions],
    }), 200


@recorder_bp.route('/map/submissions/pending', methods=['GET'])
def get_pending_map_submissions():
    if not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)

    school_id = _current_school_id()
    submissions = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.school_id == school_id, MapSubmission.status == 'pending')
        .order_by(MapSubmission.submitted_at.desc())
        .all()
    )
    return jsonify({
        'status': 'success',
        'submissions': [_serialize_submission(submission) for submission in submissions],
    }), 200


@recorder_bp.route('/map/submissions/<submission_id>/image', methods=['GET'])
def get_map_submission_image(submission_id):
    if not require_auth_or_guest():
        return _map_error('MAP_AUTH_REQUIRED', 'Authentication or guest access required', 401)

    school_id = _current_school_id()
    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id, MapSubmission.school_id == school_id)
        .first()
    )
    if not submission or not submission.image_data:
        return _map_error('MAP_IMAGE_NOT_FOUND', 'Image not found', 404)

    if submission.status != 'approved' and not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)

    return send_file(
        BytesIO(submission.image_data),
        mimetype=submission.image_mime or 'application/octet-stream',
        download_name=submission.image_filename or 'map-submission-image',
    )


@recorder_bp.route('/map/send-verification-code', methods=['POST'])
def send_map_verification_code():
    if not require_auth_or_guest():
        return _map_error('MAP_AUTH_REQUIRED', 'Authentication or guest access required', 401)

    data = request.get_json(silent=True) or {}
    email = _normalize_email(data.get('email'))
    recaptcha_token = (data.get('recaptcha_token') or '').strip()

    if RECAPTCHA_SECRET_KEY and not _verify_recaptcha(recaptcha_token):
        return _map_error('MAP_RECAPTCHA_FAILED', 'reCAPTCHA verification failed. Please try again.', 400)

    if not email:
        return _map_error('MAP_EMAIL_REQUIRED', 'Email address is required', 400)

    if '@' not in email or '.' not in email:
        return _map_error('MAP_EMAIL_INVALID', 'Please enter a valid email address', 400)

    if not _is_sac_email(email):
        return _map_error('MAP_EMAIL_DOMAIN_DENIED', 'Only @sac.on.ca email addresses can submit to the map', 403)

    try:
        verification = _create_map_verification_code(email)
        result = _send_map_verification_email(email, verification.code)
        if not result.get('success'):
            return _map_error(
                'MAP_VERIFICATION_EMAIL_SEND_FAILED',
                'Failed to send verification email. Please try again.',
                500,
                detail=result.get('error'),
            )
    except Exception as exc:
        logger.exception('Unable to send map verification email: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_VERIFICATION_CODE_CREATE_FAILED', 'Failed to send verification code. Please try again.', 500)

    return jsonify({
        'status': 'success',
        'message': 'Verification code sent to your email address.',
        'expiry_minutes': VERIFICATION_CODE_EXPIRY_MINUTES,
    }), 200


@recorder_bp.route('/map/verify-email-code', methods=['POST'])
def verify_map_email_code_endpoint():
    if not require_auth_or_guest():
        return _map_error('MAP_AUTH_REQUIRED', 'Authentication or guest access required', 401)

    data = request.get_json(silent=True) or {}
    email = _normalize_email(data.get('email'))
    code = (data.get('code') or '').strip()

    if not _is_sac_email(email):
        return _map_error('MAP_EMAIL_DOMAIN_DENIED', 'Only @sac.on.ca email addresses can submit to the map', 403)

    if not code.isdigit():
        return _map_error('MAP_VERIFICATION_CODE_NON_DIGIT', 'Verification code must contain only digits', 400)

    if len(code) != 6:
        return _map_error(
            'MAP_VERIFICATION_CODE_LENGTH',
            f'Verification code must be exactly 6 digits (received {len(code)})',
            400,
        )

    try:
        result = _verify_map_email_code(email, code)
    except Exception as exc:
        logger.exception('Unable to verify map email code: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_VERIFICATION_CODE_CHECK_FAILED', 'Failed to verify code. Please try again.', 500)

    if not result.get('valid'):
        return _map_error(
            result.get('code', 'MAP_VERIFICATION_CODE_INVALID'),
            result.get('error', 'Invalid verification code'),
            400,
        )

    return jsonify({
        'status': 'success',
        'message': 'Email verified successfully.',
        'verified': True,
    }), 200


@recorder_bp.route('/map/submitter-account/status', methods=['GET'])
def get_map_submitter_account_status():
    if not require_auth_or_guest():
        return _map_error('MAP_AUTH_REQUIRED', 'Authentication or guest access required', 401)

    email = _normalize_email(request.args.get('email'))
    if not email:
        return jsonify({'has_password': False}), 200

    if not _is_sac_email(email):
        return jsonify({'has_password': False}), 200

    account = _get_submitter_account(email)
    return jsonify({
        'status': 'success',
        'has_password': bool(account and account.status == 'active'),
    }), 200


@recorder_bp.route('/map/submissions', methods=['POST'])
def create_map_submission():
    if not require_auth_or_guest():
        return _map_error('MAP_AUTH_REQUIRED', 'Authentication or guest access required', 401)

    recaptcha_token = (request.form.get('recaptcha_token') or '').strip()
    if RECAPTCHA_SECRET_KEY and not _verify_recaptcha(recaptcha_token):
        return _map_error('MAP_RECAPTCHA_FAILED', 'reCAPTCHA verification failed. Please try again.', 400)

    email = _normalize_email(request.form.get('email'))
    text_content = (request.form.get('text') or '').strip()
    auth_method = (request.form.get('auth_method') or 'email').strip().lower()
    password = request.form.get('password') or ''
    shortcut_password = request.form.get('shortcut_password') or ''
    verification_code = (request.form.get('verification_code') or '').strip()

    if not email:
        return _map_error('MAP_EMAIL_REQUIRED', 'Email address is required', 400)

    if not _is_sac_email(email):
        return _map_error('MAP_EMAIL_DOMAIN_DENIED', 'Only @sac.on.ca email addresses can submit to the map', 403)

    if not text_content:
        return _map_error('MAP_SUBMISSION_TEXT_REQUIRED', 'Submission text is required', 400)

    if len(text_content) > 5000:
        return _map_error('MAP_SUBMISSION_TEXT_TOO_LONG', 'Submission text must be 5000 characters or fewer', 400)

    password_verified = False
    if auth_method == 'password':
        if not password:
            return _map_error('MAP_PASSWORD_REQUIRED', 'Password is required', 400)
        password_verified, account = _verify_submitter_password(email, password)
        if not password_verified:
            return _map_error('MAP_PASSWORD_INVALID', 'Invalid map submission password', 403)
    else:
        try:
            email_verified = _is_map_email_verified(email)
            if not email_verified and verification_code:
                result = _verify_map_email_code(email, verification_code)
                email_verified = bool(result.get('valid'))
                if not email_verified:
                    return _map_error(
                        result.get('code', 'MAP_VERIFICATION_CODE_INVALID'),
                        result.get('error', 'Invalid verification code'),
                        400,
                    )
        except Exception as exc:
            logger.exception('Unable to validate map email verification: %s', exc)
            map_db_session.rollback()
            return _map_error('MAP_EMAIL_VERIFICATION_CHECK_FAILED', 'Failed to validate email verification', 500)

        if not email_verified:
            return _map_error('MAP_EMAIL_NOT_VERIFIED', 'Please verify your SAC email address before submitting', 400)

    if shortcut_password:
        if len(shortcut_password) < 6:
            return _map_error('MAP_SHORTCUT_PASSWORD_TOO_SHORT', 'Shortcut password must be at least 6 characters long', 400)
        if auth_method == 'password' and shortcut_password == password:
            shortcut_password = ''

    image_file = request.files.get('image')
    image_filename = None
    image_mime = None
    image_data = None
    image_size = None

    if image_file and image_file.filename:
        image_mime = (image_file.mimetype or '').lower()
        if image_mime not in ALLOWED_IMAGE_MIMES:
            return _map_error('MAP_IMAGE_TYPE_UNSUPPORTED', 'Image must be a JPG, PNG, WebP, or GIF file', 400)

        image_data = image_file.read()
        image_size = len(image_data)
        if image_size > MAX_IMAGE_BYTES:
            return _map_error('MAP_IMAGE_TOO_LARGE', 'Image must be 5 MB or smaller', 413)

        image_filename = secure_filename(image_file.filename) or 'submission-image'

    identity = _current_identity()
    submission = MapSubmission(
        school_id=identity['school_id'],
        email=email,
        text_content=text_content,
        image_filename=image_filename,
        image_mime=image_mime,
        image_data=image_data,
        image_size=image_size,
        status='pending',
        submitted_user_id=identity['user_id'],
        submitted_username=identity['username'],
        submitted_display_name=identity['display_name'],
        submitted_role=identity['role'],
        submitted_at=_map_now_utc(),
    )

    try:
        map_db_session.add(submission)
        map_db_session.flush()
        password_created = False
        if shortcut_password:
            _upsert_submitter_password(email, shortcut_password, identity['school_id'], submission.id)
            password_created = True
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to create map submission: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_SUBMISSION_CREATE_FAILED', 'Could not submit map entry', 500)

    return jsonify({
        'status': 'success',
        'message': 'Map submission received and is pending approval.',
        'submission': _serialize_submission(submission),
        'password_created': password_created,
        'password_used': password_verified,
    }), 201


@recorder_bp.route('/map/submissions/<submission_id>/approve', methods=['POST'])
def approve_map_submission(submission_id):
    if not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)

    identity = _current_identity()
    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id, MapSubmission.school_id == identity['school_id'])
        .first()
    )
    if not submission:
        return _map_error('MAP_SUBMISSION_NOT_FOUND', 'Submission not found', 404)

    if submission.status != 'pending':
        return _map_error('MAP_SUBMISSION_NOT_PENDING', 'Submission is not pending', 400)

    submission.status = 'approved'
    submission.reviewed_user_id = identity['user_id']
    submission.reviewed_username = identity['username']
    submission.reviewed_display_name = identity['display_name']
    submission.reviewed_role = identity['role']
    submission.reviewed_at = _map_now_utc()
    submission.rejection_reason = None

    try:
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to approve map submission: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_SUBMISSION_APPROVE_FAILED', 'Could not approve submission', 500)

    return jsonify({
        'status': 'success',
        'message': 'Submission approved',
        'submission': _serialize_submission(submission),
    }), 200


@recorder_bp.route('/map/submissions/<submission_id>/reject', methods=['POST'])
def reject_map_submission(submission_id):
    if not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)

    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '').strip()
    identity = _current_identity()
    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id, MapSubmission.school_id == identity['school_id'])
        .first()
    )
    if not submission:
        return _map_error('MAP_SUBMISSION_NOT_FOUND', 'Submission not found', 404)

    if submission.status != 'pending':
        return _map_error('MAP_SUBMISSION_NOT_PENDING', 'Submission is not pending', 400)

    submission.status = 'rejected'
    submission.reviewed_user_id = identity['user_id']
    submission.reviewed_username = identity['username']
    submission.reviewed_display_name = identity['display_name']
    submission.reviewed_role = identity['role']
    submission.reviewed_at = _map_now_utc()
    submission.rejection_reason = reason or None

    try:
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to reject map submission: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_SUBMISSION_REJECT_FAILED', 'Could not reject submission', 500)

    return jsonify({
        'status': 'success',
        'message': 'Submission rejected',
        'submission': _serialize_submission(submission),
    }), 200


__all__ = []
