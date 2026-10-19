"""School email rules, verified personal addresses, and the email access gate."""

import json
import logging
from datetime import timedelta

from flask import jsonify, request, session

from . import recorder_bp
from .auth_routes import _consume_signup_verification, _signup_email_verification
from .db import EmailVerification, School, User, _now_utc, db_session
from .email_policy import email_allowed, normalize_email, school_email_policy, validate_policy
from .email_service import VERIFICATION_CODE_EXPIRY_MINUTES, create_verification_code, send_verification_email
from .recaptcha import recaptcha_failure
from .security import get_current_user

logger = logging.getLogger(__name__)


@recorder_bp.before_app_request
def require_account_email():
    if not request.path.startswith('/api/') or request.method == 'OPTIONS':
        return None
    if request.path.startswith('/api/account-deletion/'):
        return None
    if request.path in {
        '/api/auth/login', '/api/auth/logout', '/api/auth/status',
        '/api/auth/account-email/send-verification-code', '/api/auth/account-email',
        '/api/app/environment',
    }:
        return None
    actor = get_current_user()
    if actor and actor['email_required']:
        return jsonify({
            'error': 'Verify your account email to continue, or log out.',
            'code': 'ACCOUNT_EMAIL_REQUIRED', 'user': actor,
        }), 403


@recorder_bp.route('/school/email-policy', methods=['GET', 'PUT'])
def email_policy_settings():
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Authentication required'}), 401
    if actor['role'] not in {'admin', 'superadmin'}:
        return jsonify({'error': 'Admin access required'}), 403
    school = db_session.get(School, actor['school_id'])
    if request.method == 'PUT':
        try:
            policy = validate_policy(request.get_json(silent=True))
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        school.signup_email_policy = json.dumps(policy)
        school.updated_at = _now_utc()
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            return jsonify({'error': 'Unable to save school email rules. Please try again.'}), 500
    response = jsonify(school_email_policy(school))
    response.headers['Cache-Control'] = 'no-store'
    return response


def _personal_email_input(actor):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, None, (jsonify({'error': 'Enter a valid email address.'}), 400)
    try:
        email = normalize_email(data.get('email'))
    except ValueError as exc:
        return None, None, (jsonify({'error': str(exc)}), 400)
    user = db_session.get(User, actor['id'])
    if user.role == 'user' and not email_allowed(user.school, email):
        return None, None, (jsonify({
            'error': 'This email is not allowed by your school. Use an approved domain or ask an administrator for an exception.',
            'code': 'SCHOOL_EMAIL_NOT_ALLOWED',
        }), 400)
    return user, email, None


@recorder_bp.route('/auth/account-email/send-verification-code', methods=['POST'])
def send_account_email_code():
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Authentication required'}), 401
    user, email, error = _personal_email_input(actor)
    if error:
        return error
    data = request.get_json()
    failure = recaptcha_failure(data.get('recaptcha_token'), 'account_email_code')
    if failure:
        return jsonify({'error': failure.message, 'code': failure.code}), failure.status
    recent = db_session.query(EmailVerification).filter(
        EmailVerification.email == email, EmailVerification.user_id == user.id,
        EmailVerification.purpose == 'account_email',
        EmailVerification.created_at > _now_utc() - timedelta(seconds=60),
    ).first()
    if recent:
        return jsonify({'error': 'Please wait a minute before requesting another code.'}), 429, {'Retry-After': '60'}
    session.pop('account_email_challenge', None)
    try:
        verification = create_verification_code(email, purpose='account_email', school_id=user.school_id, user_id=user.id)
        result = send_verification_email(email, verification.code, purpose='account_email')
        if not result.get('success') or result.get('skipped'):
            db_session.delete(verification)
            db_session.commit()
            logger.error('Account email verification could not be delivered')
            return jsonify({'error': 'Unable to send the verification email. Please try again.'}), 503
        session['account_email_challenge'] = verification.id
    except Exception:
        db_session.rollback()
        logger.exception('Unable to send account email verification')
        return jsonify({'error': 'Unable to send the verification email. Please try again.'}), 503
    return jsonify({'message': 'Verification code sent. Check your inbox or spam folder.',
                    'expiry_minutes': VERIFICATION_CODE_EXPIRY_MINUTES}), 200


@recorder_bp.route('/auth/account-email', methods=['PUT'])
def save_account_email():
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Authentication required'}), 401
    user, email, error = _personal_email_input(actor)
    if error:
        return error
    verification, error = _signup_email_verification(
        email, request.get_json().get('verification_code'),
        purpose='account_email', session_key='account_email_challenge',
        school_id=user.school_id, user_id=user.id,
    )
    if error:
        return jsonify({'error': error}), 400
    try:
        if not _consume_signup_verification(verification):
            db_session.rollback()
            return jsonify({'error': 'Please request a new verification code.'}), 400
        user.email = email
        user.email_verified_at = _now_utc()
        user.updated_at = _now_utc()
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to save your email. Please try again.'}), 500
    session.pop('account_email_challenge', None)
    return jsonify({'message': 'Your email has been verified.', 'user': get_current_user()}), 200


@recorder_bp.route('/superadmin/users/<user_id>/require-email', methods=['POST'])
def require_admin_email(user_id):
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Authentication required'}), 401
    if actor['role'] != 'superadmin':
        return jsonify({'error': 'Superadmin access required'}), 403
    target = db_session.query(User).filter_by(id=user_id, school_id=actor['school_id']).first()
    if not target:
        return jsonify({'error': 'Account not found'}), 404
    if target.role != 'admin':
        return jsonify({'error': 'This action applies only to admin accounts.'}), 403
    target.admin_email_required_at = _now_utc()
    target.updated_at = _now_utc()
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to require email verification. Please try again.'}), 500
    return jsonify({'message': 'This admin must verify their email at their next login.'}), 200
