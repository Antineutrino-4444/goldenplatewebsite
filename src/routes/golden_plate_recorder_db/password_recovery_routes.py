"""Password recovery changes credentials only; it never creates a login session."""
import hashlib
import logging
import os
import secrets
from datetime import timedelta, timezone
from html import escape
from urllib.parse import urlsplit

from flask import jsonify, request, session

from src.services.email_delivery import send_email_via_brevo
from . import recorder_bp
from .db import PasswordRecovery, User, _now_utc, db_session
from .passwords import hash_password, verify_password
from .captcha import captcha_failure
from .security import password_session_token
from .users import get_user_by_login

logger = logging.getLogger(__name__)
RECOVERY_MINUTES = 20
GENERIC_MESSAGE = 'If this account has a verified email and is eligible, a password reset link has been sent. Check your inbox or ask a school superadmin for help.'
INVALID_LINK = 'This password reset link is invalid or expired. Request a new link or ask a superadmin for help.'


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _response(data, status=200):
    response = jsonify(data)
    response.headers['Cache-Control'] = 'no-store'
    return response, status


def _recovery_link(token):
    base = os.environ.get('WEBSITE_PUBLIC_URL', 'https://goldenplate.ca').rstrip('/')
    url = urlsplit(base)
    if url.scheme not in {'https', 'http'} or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise ValueError('Invalid WEBSITE_PUBLIC_URL')
    if url.scheme != 'https' and url.hostname not in {'localhost', '127.0.0.1'}:
        raise ValueError('Password recovery requires an HTTPS public URL')
    return f'{base}/reset-password#token={token}'


@recorder_bp.route('/auth/password-recovery/request', methods=['POST'])
def request_password_recovery():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('confirmed') is not True:
        return _response({'error': 'Confirm that you want to send a password recovery email.'}, 400)
    identifier = data.get('identifier')
    if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 320:
        return _response({'error': 'Enter your username or verified email.'}, 400)
    failure = captcha_failure(data.get('captcha_token'), 'password_recovery')
    if failure:
        return _response({'error': failure.message, 'code': failure.code}, failure.status)
    generic = {'message': GENERIC_MESSAGE}
    user = get_user_by_login(identifier)
    if (not user or user.is_record_actor or user.status != 'active'
            or user.role not in {'user', 'admin', 'superadmin', 'inter_school'}
            or not user.email or not user.email_verified_at):
        return _response(generic)
    now = _now_utc()
    previous = db_session.get(PasswordRecovery, user.id)
    if previous and (now - _aware(previous.created_at) < timedelta(minutes=1)
                     or (now - _aware(previous.window_start) < timedelta(hours=1) and previous.send_count >= 3)):
        return _response(generic)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    same_window = previous and now - _aware(previous.window_start) < timedelta(hours=1)
    values = dict(token_hash=token_hash, email=user.email.strip().lower(),
                  password_token=password_session_token(user), created_at=now,
                  expires_at=now + timedelta(minutes=RECOVERY_MINUTES), used_at=None,
                  window_start=previous.window_start if same_window else now,
                  send_count=previous.send_count + 1 if same_window else 1)
    try:
        link = _recovery_link(token)
        if previous:
            claimed = db_session.query(PasswordRecovery).filter_by(
                user_id=user.id, created_at=previous.created_at,
            ).update(values, synchronize_session=False)
            if claimed != 1:
                db_session.rollback()
                return _response(generic)
        else:
            db_session.add(PasswordRecovery(user_id=user.id, **values))
        db_session.commit()  # Persist cooldown before sending, including across workers.
    except Exception:
        db_session.rollback()
        logger.exception('Unable to prepare password recovery')
        return _response({'error': 'Unable to prepare recovery. Please try again or ask a superadmin.'}, 503)
    try:
        result = send_email_via_brevo(values['email'], 'Golden Plate - Reset your password',
            render_password_recovery_email(link))
        delivered = result.get('success') and not result.get('skipped')
    except Exception:
        logger.exception('Password recovery delivery failed')
        delivered = False
    if not delivered:
        db_session.query(PasswordRecovery).filter_by(token_hash=token_hash).update(
            {PasswordRecovery.used_at: now}, synchronize_session=False)
        db_session.commit()
        return _response({'error': 'Unable to send recovery email right now. Try again or ask a superadmin.'}, 503)
    return _response(generic)


def _valid_recovery(data):
    token = data.get('token') if isinstance(data, dict) else None
    if not isinstance(token, str) or not 40 <= len(token) <= 128:
        return None, None
    recovery = db_session.query(PasswordRecovery).filter_by(
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
    ).first()
    if not recovery or recovery.used_at or _aware(recovery.expires_at) <= _now_utc():
        return None, None
    user = db_session.get(User, recovery.user_id)
    if (not user or user.is_record_actor or user.status != 'active' or not user.email_verified_at
            or (user.email or '').strip().lower() != recovery.email
            or not secrets.compare_digest(password_session_token(user), recovery.password_token)):
        return None, None
    return recovery, user


@recorder_bp.route('/auth/password-recovery/inspect', methods=['POST'])
def inspect_password_recovery():
    recovery, _ = _valid_recovery(request.get_json(silent=True))
    return _response({'valid': True} if recovery else {'error': INVALID_LINK}, 200 if recovery else 400)


@recorder_bp.route('/auth/password-recovery/reset', methods=['POST'])
def complete_password_recovery():
    data = request.get_json(silent=True)
    recovery, user = _valid_recovery(data)
    if not recovery:
        return _response({'error': INVALID_LINK}, 400)
    password = data.get('new_password')
    if not isinstance(password, str) or not password.strip() or not 6 <= len(password) <= 256:
        return _response({'error': 'New password must be between 6 and 256 characters.'}, 400)
    if verify_password(user.password_hash, password):
        return _response({'error': 'Choose a password different from your current password.'}, 400)
    now = _now_utc()
    try:
        claimed = db_session.query(PasswordRecovery).filter(
            PasswordRecovery.token_hash == recovery.token_hash,
            PasswordRecovery.used_at.is_(None), PasswordRecovery.expires_at > now,
        ).update({PasswordRecovery.used_at: now}, synchronize_session=False)
        changed = db_session.query(User).filter(
            User.id == user.id, User.password_hash == user.password_hash,
            User.email == user.email, User.email_verified_at == user.email_verified_at,
            User.updated_at == user.updated_at, User.status == 'active', User.is_record_actor == 0,
        ).update({User.password_hash: hash_password(password), User.updated_at: now}, synchronize_session=False) if claimed else 0
        if claimed != 1 or changed != 1:
            db_session.rollback()
            return _response({'error': INVALID_LINK}, 400)
        db_session.commit()
    except Exception:
        db_session.rollback()
        logger.exception('Unable to save recovered password')
        return _response({'error': 'Unable to save the new password. Please try again.'}, 500)
    # Existing sessions have the previous password token. Never authenticate here.
    if session.get('user_uuid') == user.id:
        session.clear()
    return _response({'message': 'Password changed. Sign in with your username or verified email and your new password.'})


def render_password_recovery_email(link):
    """Render recovery content without issuing a working reset token."""
    return (
        '<h1>Reset your Golden Plate password</h1>'
        '<p>You requested a password reset. Choose a new password using the link below.</p>'
        f'<p><a href="{escape(link, quote=True)}">Choose a new password</a></p>'
        f'<p>This link expires in {RECOVERY_MINUTES} minutes and can be used once. '
        'You must sign in with your password afterward; this link does not sign you in.</p>'
        '<p>If you did not request this, ignore this email. Your password has not changed.</p>'
    )
