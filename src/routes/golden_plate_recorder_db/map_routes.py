import logging
import os
import random
import string
from datetime import timedelta, timezone
from io import BytesIO
import html as _html_lib

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
    MapBackground,
    MapEmailVerification,
    MapPin,
    MapSubmission,
    MapSubmissionImage,
    MapSubmitterAccount,
    _map_now_utc,
    map_db_session,
)
from .security import get_current_user, is_interschool_user, require_admin, require_superadmin

logger = logging.getLogger(__name__)

MAP_VERIFICATION_PURPOSE = 'map_submission'
MAX_VERIFICATION_ATTEMPTS = 5
MAP_EMAIL_VERIFICATION_MAX_AGE_MINUTES = 30
MAX_IMAGE_BYTES = 50 * 1024 * 1024
ALLOWED_IMAGE_MIMES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
HEIC_IMAGE_MIMES = {'image/heic', 'image/heif', 'image/heic-sequence', 'image/heif-sequence'}
HEIC_FILE_EXTENSIONS = ('.heic', '.heif')
SAC_EMAIL_SUFFIX = '@sac.on.ca'

# Register HEIC/HEIF support with Pillow if pillow-heif is installed.
try:
    from pillow_heif import register_heif_opener  # type: ignore
    register_heif_opener()
    _HEIC_SUPPORTED = True
except Exception:  # pragma: no cover - dependency missing
    _HEIC_SUPPORTED = False

try:
    from PIL import Image  # type: ignore
    _PIL_AVAILABLE = True
except Exception:  # pragma: no cover - dependency missing
    Image = None  # type: ignore
    _PIL_AVAILABLE = False


def _is_heic_upload(filename: str | None, mime: str | None) -> bool:
    if mime and mime.lower() in HEIC_IMAGE_MIMES:
        return True
    if filename and filename.lower().endswith(HEIC_FILE_EXTENSIONS):
        return True
    return False


def _normalize_heic_to_jpeg(raw_bytes: bytes) -> tuple[bytes, str, str] | None:
    """Decode a HEIC/HEIF blob and re-encode losslessly as PNG.

    Returns (png_bytes, 'image/png', '.png') or None if decoding failed.
    PNG is fully lossless, so no quality is lost during the conversion
    beyond what HEIC itself stored.
    """
    if not (_PIL_AVAILABLE and _HEIC_SUPPORTED):
        return None
    try:
        with Image.open(BytesIO(raw_bytes)) as img:
            img.load()
            # Preserve transparency if present; otherwise keep RGB.
            if img.mode not in ('RGB', 'RGBA', 'L', 'LA', 'I', 'I;16'):
                img = img.convert('RGBA' if 'A' in img.getbands() else 'RGB')
            out = BytesIO()
            # PNG is lossless. compress_level only affects file size / CPU.
            img.save(out, format='PNG', optimize=True, compress_level=6)
            return out.getvalue(), 'image/png', '.png'
    except Exception:
        logger.exception('Failed to convert HEIC image to PNG')
        return None


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
            'Image must be 50 MB or smaller',
            413,
        )
    return error.get_response()


@recorder_bp.before_app_request
def _block_interschool_from_map():
    if not request.path.startswith('/api/map/'):
        return None
    if is_interschool_user():
        return _map_error(
            'MAP_INTERSCHOOL_FORBIDDEN',
            'Inter-school admin accounts cannot access the Ecological Map',
            403,
        )
    return None


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
    images = []
    if submission.image_data:
        images.append({
            'id': 'primary',
            'filename': submission.image_filename,
            'mime': submission.image_mime,
            'size': submission.image_size,
            'url': f'/api/map/submissions/{submission.id}/image',
        })
    extras = (
        map_db_session.query(MapSubmissionImage)
        .filter(MapSubmissionImage.submission_id == submission.id)
        .order_by(MapSubmissionImage.position.asc(), MapSubmissionImage.created_at.asc())
        .all()
    )
    for extra in extras:
        images.append({
            'id': extra.id,
            'filename': extra.image_filename,
            'mime': extra.image_mime,
            'size': extra.image_size,
            'url': f'/api/map/submissions/{submission.id}/images/{extra.id}',
        })
    return {
        'id': submission.id,
        'school_id': submission.school_id,
        'email': submission.email,
        'title': submission.title or '',
        'text': submission.text_content,
        'submission_display_name': submission.submission_display_name or '',
        'pin_id': submission.pin_id,
        'image_filename': submission.image_filename,
        'image_mime': submission.image_mime,
        'image_size': submission.image_size,
        'image_url': images[0]['url'] if images else None,
        'images': images,
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
    submissions = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.status == 'approved')
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

    submissions = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.status == 'pending')
        .order_by(MapSubmission.submitted_at.desc())
        .all()
    )
    return jsonify({
        'status': 'success',
        'submissions': [_serialize_submission(submission) for submission in submissions],
    }), 200


@recorder_bp.route('/map/submissions/<submission_id>/image', methods=['GET'])
def get_map_submission_image(submission_id):
    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id)
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


@recorder_bp.route('/map/submissions/<submission_id>/images/<image_id>', methods=['GET'])
def get_map_submission_extra_image(submission_id, image_id):
    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id)
        .first()
    )
    if not submission:
        return _map_error('MAP_IMAGE_NOT_FOUND', 'Image not found', 404)
    if submission.status != 'approved' and not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)
    image = (
        map_db_session.query(MapSubmissionImage)
        .filter(
            MapSubmissionImage.id == image_id,
            MapSubmissionImage.submission_id == submission_id,
        )
        .first()
    )
    if not image or not image.image_data:
        return _map_error('MAP_IMAGE_NOT_FOUND', 'Image not found', 404)
    return send_file(
        BytesIO(image.image_data),
        mimetype=image.image_mime or 'application/octet-stream',
        download_name=image.image_filename or 'map-submission-image',
    )


@recorder_bp.route('/map/send-verification-code', methods=['POST'])
def send_map_verification_code():
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
    recaptcha_token = (request.form.get('recaptcha_token') or '').strip()
    if RECAPTCHA_SECRET_KEY and not _verify_recaptcha(recaptcha_token):
        return _map_error('MAP_RECAPTCHA_FAILED', 'reCAPTCHA verification failed. Please try again.', 400)

    email = _normalize_email(request.form.get('email'))
    text_content = (request.form.get('text') or '').strip()
    title = (request.form.get('title') or '').strip()
    submission_display_name = (request.form.get('submission_display_name') or '').strip()
    pin_id_raw = (request.form.get('pin_id') or '').strip()
    pin_id = pin_id_raw if pin_id_raw else None
    auth_method = (request.form.get('auth_method') or 'email').strip().lower()
    password = request.form.get('password') or ''
    shortcut_password = request.form.get('shortcut_password') or ''
    verification_code = (request.form.get('verification_code') or '').strip()

    if not email:
        return _map_error('MAP_EMAIL_REQUIRED', 'Email address is required', 400)

    if not _is_sac_email(email):
        return _map_error('MAP_EMAIL_DOMAIN_DENIED', 'Only @sac.on.ca email addresses can submit to the map', 403)

    if not title:
        return _map_error('MAP_SUBMISSION_TITLE_REQUIRED', 'Submission title is required', 400)

    if len(title) > 200:
        return _map_error('MAP_SUBMISSION_TITLE_TOO_LONG', 'Submission title must be 200 characters or fewer', 400)

    if not text_content:
        return _map_error('MAP_SUBMISSION_TEXT_REQUIRED', 'Submission description is required', 400)

    if len(text_content) > 5000:
        return _map_error('MAP_SUBMISSION_TEXT_TOO_LONG', 'Submission description must be 5000 characters or fewer', 400)

    if len(submission_display_name) > 80:
        return _map_error('MAP_SUBMISSION_DISPLAY_NAME_TOO_LONG', 'Display name must be 80 characters or fewer', 400)

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
        original_filename = image_file.filename
        image_data = image_file.read()
        image_size = len(image_data)
        if image_size > MAX_IMAGE_BYTES:
            return _map_error('MAP_IMAGE_TOO_LARGE', 'Image must be 50 MB or smaller', 413)

        if _is_heic_upload(original_filename, image_mime):
            converted = _normalize_heic_to_jpeg(image_data)
            if not converted:
                return _map_error('MAP_IMAGE_HEIC_DECODE_FAILED', 'Could not decode HEIC image', 400)
            image_data, image_mime, new_ext = converted
            image_size = len(image_data)
            base = os.path.splitext(secure_filename(original_filename) or 'submission-image')[0] or 'submission-image'
            image_filename = f'{base}{new_ext}'
        else:
            if image_mime not in ALLOWED_IMAGE_MIMES:
                return _map_error('MAP_IMAGE_TYPE_UNSUPPORTED', 'Image must be a JPG, PNG, WebP, GIF, or HEIC file', 400)
            image_filename = secure_filename(original_filename) or 'submission-image'

    # Additional images uploaded as field 'images' (one or many).
    extra_uploads = request.files.getlist('images')
    extra_processed = []  # list of dicts: filename, mime, data, size
    for extra in extra_uploads:
        if not extra or not extra.filename:
            continue
        ext_mime = (extra.mimetype or '').lower()
        ext_original = extra.filename
        ext_data = extra.read()
        ext_size = len(ext_data)
        if ext_size > MAX_IMAGE_BYTES:
            return _map_error('MAP_IMAGE_TOO_LARGE', 'Image must be 50 MB or smaller', 413)
        if _is_heic_upload(ext_original, ext_mime):
            converted = _normalize_heic_to_jpeg(ext_data)
            if not converted:
                return _map_error('MAP_IMAGE_HEIC_DECODE_FAILED', 'Could not decode HEIC image', 400)
            ext_data, ext_mime, new_ext = converted
            ext_size = len(ext_data)
            base = os.path.splitext(secure_filename(ext_original) or 'submission-image')[0] or 'submission-image'
            ext_filename = f'{base}{new_ext}'
        else:
            if ext_mime not in ALLOWED_IMAGE_MIMES:
                return _map_error('MAP_IMAGE_TYPE_UNSUPPORTED', 'Image must be a JPG, PNG, WebP, GIF, or HEIC file', 400)
            ext_filename = secure_filename(ext_original) or 'submission-image'
        extra_processed.append({
            'filename': ext_filename,
            'mime': ext_mime,
            'data': ext_data,
            'size': ext_size,
        })

    # If no primary 'image' field but extras exist, promote the first extra.
    if image_data is None and extra_processed:
        first = extra_processed.pop(0)
        image_filename = first['filename']
        image_mime = first['mime']
        image_data = first['data']
        image_size = first['size']

    identity = _current_identity()

    if pin_id:
        pin = (
            map_db_session.query(MapPin)
            .filter(MapPin.id == pin_id, MapPin.school_id == identity['school_id'])
            .first()
        )
        if not pin:
            return _map_error('MAP_PIN_NOT_FOUND', 'Selected pin does not exist', 404)

    submission = MapSubmission(
        school_id=identity['school_id'],
        email=email,
        text_content=text_content,
        title=title,
        submission_display_name=submission_display_name or None,
        pin_id=pin_id,
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
        # Persist any additional gallery images.
        for index, extra in enumerate(extra_processed):
            map_db_session.add(MapSubmissionImage(
                submission_id=submission.id,
                position=index + 1,
                image_filename=extra['filename'],
                image_mime=extra['mime'],
                image_data=extra['data'],
                image_size=extra['size'],
            ))
        # Backfill: any prior submissions from the same email take on the latest display name
        if submission_display_name:
            map_db_session.query(MapSubmission).filter(
                func.lower(MapSubmission.email) == email.lower(),
                MapSubmission.id != submission.id,
            ).update(
                {'submission_display_name': submission_display_name},
                synchronize_session=False,
            )
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

    # If a comment was supplied, send the notification email FIRST. If the
    # email fails, do not reject the submission — the submitter would otherwise
    # never learn the reason. Plain rejections (no comment) skip the email.
    email_status = None
    if reason:
        if not submission.email:
            return _map_error(
                'MAP_REJECT_NO_EMAIL',
                'Cannot send rejection comment: submitter has no email on file',
                400,
            )
        try:
            email_status = _send_rejection_email(
                to_email=submission.email,
                submission=submission,
                reason=reason,
                reviewer_display_name=identity.get('display_name') or identity.get('username') or 'Admin',
            )
        except Exception as exc:
            logger.exception('Unable to send map rejection email: %s', exc)
            email_status = {'success': False, 'error': str(exc)}
        if not email_status or not email_status.get('success'):
            detail = (email_status or {}).get('error') or 'Unknown email error'
            return _map_error(
                'MAP_REJECT_EMAIL_FAILED',
                'Submission was not rejected: notification email failed',
                502,
                detail=detail,
            )

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

    response_payload = {
        'status': 'success',
        'message': 'Submission rejected',
        'submission': _serialize_submission(submission),
    }
    if email_status is not None:
        response_payload['notification_email'] = email_status
    return jsonify(response_payload), 200


def _send_deletion_email(*, to_email: str, submission, reason: str, reviewer_display_name: str) -> dict:
    """Send a formatted deletion email to the submitter via Brevo."""
    title = (submission.title or '').strip() or 'your submission'
    safe_title = _html_lib.escape(title)
    safe_reason = _html_lib.escape(reason).replace('\n', '<br/>')
    safe_reviewer = _html_lib.escape(reviewer_display_name)
    submitted_at = ''
    if submission.submitted_at:
        try:
            submitted_at = submission.submitted_at.strftime('%B %d, %Y at %I:%M %p UTC')
        except Exception:
            submitted_at = str(submission.submitted_at)
    safe_submitted_at = _html_lib.escape(submitted_at)
    excerpt = (submission.text_content or '').strip()
    if len(excerpt) > 400:
        excerpt = excerpt[:400] + '…'
    safe_excerpt = _html_lib.escape(excerpt).replace('\n', '<br/>')

    subject = 'Your Ecological Map submission was deleted'
    html_content = f"""
<!doctype html>
<html>
  <body style=\"margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0f172a;\">
    <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f1f5f9;padding:24px 0;\">
      <tr><td align=\"center\">
        <table role=\"presentation\" width=\"600\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 14px rgba(15,23,42,0.06);\">
          <tr>
            <td style=\"background:linear-gradient(135deg,#7f1d1d,#dc2626);padding:24px 28px;color:#ffffff;\">
              <div style=\"font-size:12px;letter-spacing:0.18em;text-transform:uppercase;opacity:0.85;\">Ecological Map</div>
              <div style=\"font-size:22px;font-weight:700;margin-top:6px;\">Submission was deleted</div>
            </td>
          </tr>
          <tr>
            <td style=\"padding:24px 28px;\">
              <p style=\"margin:0 0 14px 0;font-size:15px;line-height:1.55;\">Hi,</p>
              <p style=\"margin:0 0 14px 0;font-size:15px;line-height:1.55;\">
                Your submission <strong>{safe_title}</strong> on the Ecological Map has been removed by an administrator.
              </p>
              <div style=\"background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:14px 16px;margin:16px 0;\">
                <div style=\"font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#991b1b;margin-bottom:6px;\">Reason</div>
                <div style=\"font-size:14px;line-height:1.55;color:#7f1d1d;\">{safe_reason}</div>
              </div>
              <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;margin:16px 0;\">
                <tr>
                  <td style=\"padding:14px 16px;font-size:13px;line-height:1.55;color:#334155;\">
                    <div><strong>Title:</strong> {safe_title}</div>
                    <div><strong>Originally submitted:</strong> {safe_submitted_at or '—'}</div>
                    <div><strong>Deleted by:</strong> {safe_reviewer}</div>
                  </td>
                </tr>
              </table>
              {('<div style="font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#475569;margin:18px 0 6px 0;">Your submission</div><div style="font-size:14px;line-height:1.55;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;padding:14px 16px;color:#334155;">' + safe_excerpt + '</div>') if safe_excerpt else ''}
              <p style=\"margin:18px 0 6px 0;font-size:14px;line-height:1.55;\">If you believe this was a mistake, please contact a site administrator.</p>
              <p style=\"margin:0;font-size:14px;line-height:1.55;color:#475569;\">— The Ecological Map team</p>
            </td>
          </tr>
          <tr>
            <td style=\"padding:14px 28px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b;\">
              You're receiving this email because you submitted an entry to the Ecological Map.
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>
"""
    return send_email_via_brevo(to_email, subject, html_content)


def _send_rejection_email(*, to_email: str, submission, reason: str, reviewer_display_name: str) -> dict:
    """Send a formatted rejection email to the submitter via Brevo."""
    title = (submission.title or '').strip() or 'your submission'
    safe_title = _html_lib.escape(title)
    safe_reason = _html_lib.escape(reason).replace('\n', '<br/>')
    safe_reviewer = _html_lib.escape(reviewer_display_name)
    submitted_at = ''
    if submission.submitted_at:
        try:
            submitted_at = submission.submitted_at.strftime('%B %d, %Y at %I:%M %p UTC')
        except Exception:
            submitted_at = str(submission.submitted_at)
    safe_submitted_at = _html_lib.escape(submitted_at)
    excerpt = (submission.text_content or '').strip()
    if len(excerpt) > 400:
        excerpt = excerpt[:400] + '…'
    safe_excerpt = _html_lib.escape(excerpt).replace('\n', '<br/>')

    subject = f'Your Ecological Map submission was not approved'
    html_content = f"""
<!doctype html>
<html>
  <body style=\"margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0f172a;\">
    <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f1f5f9;padding:24px 0;\">
      <tr><td align=\"center\">
        <table role=\"presentation\" width=\"600\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 14px rgba(15,23,42,0.06);\">
          <tr>
            <td style=\"background:linear-gradient(135deg,#0f766e,#0ea5e9);padding:24px 28px;color:#ffffff;\">
              <div style=\"font-size:12px;letter-spacing:0.18em;text-transform:uppercase;opacity:0.85;\">Ecological Map</div>
              <div style=\"font-size:22px;font-weight:700;margin-top:6px;\">Submission was not approved</div>
            </td>
          </tr>
          <tr>
            <td style=\"padding:24px 28px;\">
              <p style=\"margin:0 0 14px 0;font-size:15px;line-height:1.55;\">Hi,</p>
              <p style=\"margin:0 0 14px 0;font-size:15px;line-height:1.55;\">
                Thanks for contributing to the Ecological Map. After review, <strong>{safe_title}</strong> was not approved.
              </p>
              <div style=\"background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:14px 16px;margin:16px 0;\">
                <div style=\"font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#991b1b;margin-bottom:6px;\">Reviewer comment</div>
                <div style=\"font-size:14px;line-height:1.55;color:#7f1d1d;\">{safe_reason}</div>
              </div>
              <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;margin:16px 0;\">
                <tr>
                  <td style=\"padding:14px 16px;font-size:13px;line-height:1.55;color:#334155;\">
                    <div><strong>Title:</strong> {safe_title}</div>
                    <div><strong>Submitted:</strong> {safe_submitted_at or '—'}</div>
                    <div><strong>Reviewed by:</strong> {safe_reviewer}</div>
                  </td>
                </tr>
              </table>
              {('<div style="font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#475569;margin:18px 0 6px 0;">Your submission</div><div style="font-size:14px;line-height:1.55;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;padding:14px 16px;color:#334155;">' + safe_excerpt + '</div>') if safe_excerpt else ''}
              <p style=\"margin:18px 0 6px 0;font-size:14px;line-height:1.55;\">You're welcome to revise it and submit again.</p>
              <p style=\"margin:0;font-size:14px;line-height:1.55;color:#475569;\">— The Ecological Map team</p>
            </td>
          </tr>
          <tr>
            <td style=\"padding:14px 28px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b;\">
              You're receiving this email because you submitted an entry to the Ecological Map.
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>
"""
    return send_email_via_brevo(to_email, subject, html_content)


def _serialize_pin(pin):
    return {
        'id': pin.id,
        'name': pin.name,
        'x': pin.x,
        'y': pin.y,
        'created_at': pin.created_at.isoformat() if pin.created_at else None,
        'created_by': {
            'user_id': pin.created_by_user_id,
            'username': pin.created_by_username,
            'display_name': pin.created_by_display_name,
            'email': pin.created_by_email,
        },
    }


@recorder_bp.route('/map/pins', methods=['GET'])
def list_map_pins():
    # Auto-cleanup: remove pins that have no submissions attached. Skip pins
    # created in the last 10 minutes so a freshly created pin awaiting its
    # first submission isn't yanked out from under the submitter.
    grace_cutoff = _map_now_utc() - timedelta(minutes=10)
    try:
        empty_pin_ids = [
            row[0]
            for row in (
                map_db_session.query(MapPin.id)
                .outerjoin(MapSubmission, MapSubmission.pin_id == MapPin.id)
                .filter(MapPin.created_at < grace_cutoff)
                .group_by(MapPin.id)
                .having(func.count(MapSubmission.id) == 0)
                .all()
            )
        ]
        if empty_pin_ids:
            map_db_session.query(MapPin).filter(MapPin.id.in_(empty_pin_ids)).delete(
                synchronize_session=False
            )
            map_db_session.commit()
    except Exception as exc:
        logger.exception('Empty-pin cleanup failed: %s', exc)
        map_db_session.rollback()

    pins = (
        map_db_session.query(MapPin)
        .order_by(MapPin.created_at.asc())
        .all()
    )
    return jsonify({
        'status': 'success',
        'pins': [_serialize_pin(pin) for pin in pins],
    }), 200


@recorder_bp.route('/map/pins', methods=['POST'])
def create_map_pin():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    x = data.get('x')
    y = data.get('y')
    email = _normalize_email(data.get('email'))

    if not name:
        return _map_error('MAP_PIN_NAME_REQUIRED', 'Pin name is required', 400)
    if len(name) > 80:
        return _map_error('MAP_PIN_NAME_TOO_LONG', 'Pin name must be 80 characters or fewer', 400)

    try:
        x = float(x)
        y = float(y)
    except (TypeError, ValueError):
        return _map_error('MAP_PIN_COORDS_INVALID', 'Pin coordinates must be numeric', 400)

    if not (0 <= x <= 100 and 0 <= y <= 100):
        return _map_error('MAP_PIN_COORDS_OUT_OF_RANGE', 'Pin coordinates must be within map bounds (0-100)', 400)

    user = get_current_user()
    if user:
        identity = _current_identity()
        creator_email = email or identity['username']
        creator_username = identity['username']
        creator_display = identity['display_name']
        creator_user_id = identity['user_id']
    else:
        # Guest / map submitter — must provide a verified SAC email
        if not email or not _is_sac_email(email):
            return _map_error('MAP_PIN_EMAIL_REQUIRED', 'A verified @sac.on.ca email is required to create a pin', 403)
        if not _is_map_email_verified(email):
            return _map_error('MAP_PIN_EMAIL_NOT_VERIFIED', 'Verify your SAC email before creating a pin', 403)
        creator_email = email
        creator_username = email
        creator_display = email
        creator_user_id = None

    school_id = _current_school_id()
    pin = MapPin(
        school_id=school_id,
        name=name,
        x=x,
        y=y,
        created_by_user_id=creator_user_id,
        created_by_username=creator_username,
        created_by_display_name=creator_display,
        created_by_email=creator_email,
    )
    try:
        map_db_session.add(pin)
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to create map pin: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_PIN_CREATE_FAILED', 'Could not create pin', 500)

    return jsonify({'status': 'success', 'pin': _serialize_pin(pin)}), 201


@recorder_bp.route('/map/pins/<pin_id>', methods=['DELETE'])
def delete_map_pin(pin_id):
    if not require_superadmin():
        return _map_error('MAP_SUPERADMIN_REQUIRED', 'Super admin access required', 403)

    pin = (
        map_db_session.query(MapPin)
        .filter(MapPin.id == pin_id)
        .first()
    )
    if not pin:
        return _map_error('MAP_PIN_NOT_FOUND', 'Pin not found', 404)

    # Detach submissions from this pin (move to "Others")
    map_db_session.query(MapSubmission).filter(
        MapSubmission.pin_id == pin_id,
    ).update({'pin_id': None}, synchronize_session=False)

    try:
        map_db_session.delete(pin)
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to delete map pin: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_PIN_DELETE_FAILED', 'Could not delete pin', 500)

    return jsonify({'status': 'success', 'message': 'Pin deleted'}), 200


@recorder_bp.route('/map/submissions/<submission_id>', methods=['DELETE'])
def delete_map_submission(submission_id):
    if not require_superadmin():
        return _map_error('MAP_SUPERADMIN_REQUIRED', 'Super admin access required', 403)

    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '').strip()

    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id)
        .first()
    )
    if not submission:
        return _map_error('MAP_SUBMISSION_NOT_FOUND', 'Submission not found', 404)

    identity = _current_identity()

    # If a comment was supplied, send the notification email FIRST. If the
    # email fails, do not delete the submission.
    email_status = None
    if reason:
        if not submission.email:
            return _map_error(
                'MAP_DELETE_NO_EMAIL',
                'Cannot send deletion comment: submitter has no email on file',
                400,
            )
        try:
            email_status = _send_deletion_email(
                to_email=submission.email,
                submission=submission,
                reason=reason,
                reviewer_display_name=identity.get('display_name') or identity.get('username') or 'Admin',
            )
        except Exception as exc:
            logger.exception('Unable to send map deletion email: %s', exc)
            email_status = {'success': False, 'error': str(exc)}
        if not email_status or not email_status.get('success'):
            detail = (email_status or {}).get('error') or 'Unknown email error'
            return _map_error(
                'MAP_DELETE_EMAIL_FAILED',
                'Submission was not deleted: notification email failed',
                502,
                detail=detail,
            )

    pin_id = submission.pin_id

    try:
        # Explicitly remove gallery rows (SQLite ignores ON DELETE CASCADE
        # unless PRAGMA foreign_keys=ON is set per-connection).
        map_db_session.query(MapSubmissionImage).filter(
            MapSubmissionImage.submission_id == submission.id
        ).delete(synchronize_session=False)
        map_db_session.delete(submission)
        map_db_session.flush()
        # If the pin no longer has any submissions attached, remove it too.
        if pin_id:
            remaining = (
                map_db_session.query(MapSubmission)
                .filter(MapSubmission.pin_id == pin_id)
                .count()
            )
            if remaining == 0:
                map_db_session.query(MapPin).filter(MapPin.id == pin_id).delete(
                    synchronize_session=False
                )
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to delete map submission: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_SUBMISSION_DELETE_FAILED', 'Could not delete submission', 500)

    response_payload = {'status': 'success', 'message': 'Submission deleted'}
    if email_status is not None:
        response_payload['notification_email'] = email_status
    return jsonify(response_payload), 200


@recorder_bp.route('/map/leaderboard', methods=['GET'])
def map_leaderboard():
    rows = (
        map_db_session.query(
            MapSubmission.email,
            MapSubmission.submission_display_name,
            func.count(MapSubmission.id).label('count'),
        )
        .filter(MapSubmission.status == 'approved')
        .group_by(MapSubmission.email, MapSubmission.submission_display_name)
        .all()
    )
    # Aggregate by email; pick most-recent display name per email
    by_email = {}
    for email, display_name, count in rows:
        bucket = by_email.setdefault(email, {'email': email, 'display_name': '', 'count': 0})
        bucket['count'] += int(count or 0)
        if display_name and not bucket['display_name']:
            bucket['display_name'] = display_name
    leaders = sorted(by_email.values(), key=lambda item: item['count'], reverse=True)
    return jsonify({'status': 'success', 'leaderboard': leaders[:50]}), 200


@recorder_bp.route('/map/convert-heic', methods=['POST'])
def convert_heic_image():
    """Convert an uploaded HEIC/HEIF file to JPEG and return the bytes.

    Lets browsers (which can't natively decode HEIC) preview/edit HEIC files
    by round-tripping through the server.
    """
    image_file = request.files.get('image')
    if not image_file or not image_file.filename:
        return _map_error('MAP_HEIC_FILE_REQUIRED', 'Image file is required', 400)

    if not _is_heic_upload(image_file.filename, image_file.mimetype):
        return _map_error('MAP_HEIC_NOT_HEIC', 'File is not a HEIC/HEIF image', 400)

    raw = image_file.read()
    if len(raw) > MAX_IMAGE_BYTES:
        return _map_error('MAP_IMAGE_TOO_LARGE', 'Image must be 50 MB or smaller', 413)

    converted = _normalize_heic_to_jpeg(raw)
    if not converted:
        return _map_error('MAP_IMAGE_HEIC_DECODE_FAILED', 'Could not decode HEIC image', 400)
    jpeg_bytes, mime, _ext = converted
    return send_file(BytesIO(jpeg_bytes), mimetype=mime, max_age=0)


@recorder_bp.route('/map/background', methods=['GET'])
def get_map_background():
    background = (
        map_db_session.query(MapBackground)
        .order_by(MapBackground.uploaded_at.desc())
        .first()
    )
    if not background:
        return _map_error('MAP_BACKGROUND_NOT_FOUND', 'No background uploaded', 404)

    return send_file(
        BytesIO(background.image_data),
        mimetype=background.image_mime or 'application/octet-stream',
        download_name=background.image_filename or 'map-background',
    )


@recorder_bp.route('/map/background/info', methods=['GET'])
def get_map_background_info():
    background = (
        map_db_session.query(MapBackground)
        .order_by(MapBackground.uploaded_at.desc())
        .first()
    )
    if not background:
        return jsonify({'status': 'success', 'has_background': False}), 200

    return jsonify({
        'status': 'success',
        'has_background': True,
        'image_url': '/api/map/background',
        'image_mime': background.image_mime,
        'image_size': background.image_size,
        'uploaded_at': background.uploaded_at.isoformat() if background.uploaded_at else None,
    }), 200


@recorder_bp.route('/map/background', methods=['POST'])
def upload_map_background():
    if not require_superadmin():
        return _map_error('MAP_SUPERADMIN_REQUIRED', 'Super admin access required', 403)

    image_file = request.files.get('image')
    if not image_file or not image_file.filename:
        return _map_error('MAP_BACKGROUND_IMAGE_REQUIRED', 'Image file is required', 400)

    image_mime = (image_file.mimetype or '').lower()
    original_filename = image_file.filename
    image_data = image_file.read()
    image_size = len(image_data)
    if image_size > MAX_IMAGE_BYTES:
        return _map_error('MAP_IMAGE_TOO_LARGE', 'Image must be 50 MB or smaller', 413)

    if _is_heic_upload(original_filename, image_mime):
        converted = _normalize_heic_to_jpeg(image_data)
        if not converted:
            return _map_error('MAP_IMAGE_HEIC_DECODE_FAILED', 'Could not decode HEIC image', 400)
        image_data, image_mime, new_ext = converted
        image_size = len(image_data)
        base = os.path.splitext(secure_filename(original_filename) or 'map-background')[0] or 'map-background'
        stored_filename = f'{base}{new_ext}'
    else:
        if image_mime not in ALLOWED_IMAGE_MIMES:
            return _map_error('MAP_IMAGE_TYPE_UNSUPPORTED', 'Image must be a JPG, PNG, WebP, GIF, or HEIC file', 400)
        stored_filename = secure_filename(original_filename) or 'map-background'

    identity = _current_identity()
    school_id = identity['school_id']
    background = (
        map_db_session.query(MapBackground)
        .filter(MapBackground.school_id == school_id)
        .first()
    )
    if background:
        background.image_data = image_data
        background.image_mime = image_mime
        background.image_filename = stored_filename
        background.image_size = image_size
        background.uploaded_at = _map_now_utc()
        background.uploaded_by_user_id = identity['user_id']
        background.uploaded_by_username = identity['username']
    else:
        background = MapBackground(
            school_id=school_id,
            image_data=image_data,
            image_mime=image_mime,
            image_filename=stored_filename,
            image_size=image_size,
            uploaded_at=_map_now_utc(),
            uploaded_by_user_id=identity['user_id'],
            uploaded_by_username=identity['username'],
        )
        map_db_session.add(background)

    try:
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to save map background: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_BACKGROUND_SAVE_FAILED', 'Could not save background image', 500)

    return jsonify({
        'status': 'success',
        'message': 'Background image saved',
        'image_url': '/api/map/background',
        'image_size': image_size,
    }), 200


__all__ = []