"""Public, verified subscriptions to published website release emails."""

import json
import logging
from datetime import timedelta

from flask import jsonify, request, session

from . import recorder_bp
from .auth_routes import _consume_signup_verification, _signup_email_verification
from .captcha import captcha_failure
from .db import EmailNotificationPreference, EmailVerification, WebsiteUpdateSubscriber, _now_utc, db_session
from .email_policy import normalize_email
from .email_service import VERIFICATION_CODE_EXPIRY_MINUTES, create_verification_code, send_verification_email
from src.services.notification_preferences import disabled_notification_types
from src.services.website_notifications import notify_update_subscription

logger = logging.getLogger(__name__)
PURPOSE = 'website_updates'
SESSION_KEY = 'website_updates_challenge'


def _input():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('Enter a valid email address.')
    return data, normalize_email(data.get('email'))


@recorder_bp.route('/updates/send-verification-code', methods=['POST'])
def send_update_subscription_code():
    try:
        data, email = _input()
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    failure = captcha_failure(data.get('captcha_token'), 'website_updates_code')
    if failure:
        return jsonify({'error': failure.message, 'code': failure.code}), failure.status
    recent = db_session.query(EmailVerification).filter(
        EmailVerification.email == email, EmailVerification.purpose == PURPOSE,
        EmailVerification.created_at > _now_utc() - timedelta(seconds=60),
    ).first()
    if recent:
        return jsonify({'error': 'Please wait a minute before requesting another code.'}), 429, {'Retry-After': '60'}
    session.pop(SESSION_KEY, None)
    verification = None
    try:
        verification = create_verification_code(email, purpose=PURPOSE)
        result = send_verification_email(email, verification.code, purpose=PURPOSE)
        if not result.get('success') or result.get('skipped'):
            raise RuntimeError('Verification email could not be delivered')
        session[SESSION_KEY] = verification.id
    except Exception:
        db_session.rollback()
        if verification is not None:
            db_session.delete(verification)
            db_session.commit()
        logger.exception('Unable to send update subscription verification email')
        return jsonify({'error': 'Unable to send the verification email. Please try again.'}), 503
    return jsonify({'message': 'Verification code sent. Check your inbox or spam folder.',
                    'expiry_minutes': VERIFICATION_CODE_EXPIRY_MINUTES})


@recorder_bp.route('/updates/subscribe', methods=['POST'])
def subscribe_to_updates():
    try:
        data, email = _input()
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    verification, error = _signup_email_verification(
        email, data.get('verification_code'), purpose=PURPOSE, session_key=SESSION_KEY,
    )
    if error:
        return jsonify({'error': error}), 400
    try:
        if not _consume_signup_verification(verification):
            db_session.rollback()
            return jsonify({'error': 'Please request a new verification code.'}), 400
        subscriber = db_session.get(WebsiteUpdateSubscriber, email)
        preference = db_session.get(EmailNotificationPreference, email)
        disabled = disabled_notification_types(preference.disabled_types) if preference else set()
        newly_subscribed = subscriber is None or 'release_notes' in disabled
        if subscriber is None:
            db_session.add(WebsiteUpdateSubscriber(email=email))
        elif newly_subscribed:
            subscriber.subscribed_at = _now_utc()
        # Verifying an explicit subscription also restores release emails after
        # an earlier unsubscribe, without changing any other notification choice.
        if preference:
            disabled.discard('release_notes')
            preference.disabled_types = json.dumps(sorted(disabled))
            preference.known_types = json.dumps(sorted(set(json.loads(preference.known_types)) | {'release_notes'}))
        db_session.commit()
    except Exception:
        db_session.rollback()
        logger.exception('Unable to save website update subscription')
        return jsonify({'error': 'Unable to save your subscription. Please try again.'}), 503
    session.pop(SESSION_KEY, None)
    notification = {'success': True}
    if newly_subscribed:
        try:
            notification = notify_update_subscription(email)
        except Exception:
            logger.exception('Unable to notify website recipients about a new subscriber')
            notification = {'success': False}
    response = {'message': 'You’re subscribed! New website releases will be emailed to you.'}
    if not notification.get('success'):
        logger.warning('Website update subscription saved, but signup alert delivery failed')
        response['warning'] = 'Your subscription is saved, but the administrator signup alert could not be delivered.'
    return jsonify(response), 201 if newly_subscribed else 200
