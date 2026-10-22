"""Shared, fail-closed Cloudflare Turnstile verification."""
import os
import re
from dataclasses import dataclass
from datetime import datetime

import requests

from .app_config import is_development_environment

VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
PRODUCTION_HOSTNAMES = {'goldenplate.ca', 'www.goldenplate.ca', 'map.goldenplate.ca'}
TEST_SECRETS = {f'{n}x0000000000000000000000000000000AA' for n in (1, 2, 3)}


@dataclass(frozen=True)
class CaptchaFailure:
    code: str
    message: str
    status: int = 400


def captcha_failure(token, expected_action, *, required=False):
    """Verify tokens; required=True also forbids development bypass/test secrets."""
    development = is_development_environment()
    secret = os.environ.get('TURNSTILE_SECRET_KEY', '').strip()
    if not secret:
        if development and not required:
            return None
        return CaptchaFailure('CAPTCHA_UNAVAILABLE', 'Verification is temporarily unavailable. Please contact an administrator.', 503)
    if (not development or required) and secret in TEST_SECRETS:
        return CaptchaFailure('CAPTCHA_UNAVAILABLE', 'Verification is temporarily unavailable. Please contact an administrator.', 503)
    if not isinstance(token, str) or not token.strip():
        return CaptchaFailure('CAPTCHA_REQUIRED', 'Verification is required. Please try submitting again.')
    if len(token) > 2048:
        return CaptchaFailure('CAPTCHA_INVALID', 'Verification failed. Please try again.')
    try:
        response = requests.post(VERIFY_URL, data={'secret': secret, 'response': token.strip()}, timeout=10)
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError):
        return CaptchaFailure('CAPTCHA_UNAVAILABLE', 'Unable to verify this request right now. Please try again.', 503)
    if not isinstance(result, dict):
        return CaptchaFailure('CAPTCHA_INVALID', 'Verification failed. Please try again.')
    errors = result.get('error-codes')
    if errors:
        if isinstance(errors, list) and 'timeout-or-duplicate' in errors:
            return CaptchaFailure('CAPTCHA_EXPIRED', 'The security check expired or was already used. Please try again.')
        if isinstance(errors, list) and any(code in errors for code in ('missing-input-secret', 'invalid-input-secret', 'internal-error')):
            return CaptchaFailure('CAPTCHA_UNAVAILABLE', 'Unable to verify this request right now. Please try again.', 503)
        return CaptchaFailure('CAPTCHA_INVALID', 'Verification failed. Please try again or contact an administrator.')
    if result.get('success') is not True or result.get('action') != expected_action:
        return CaptchaFailure('CAPTCHA_INVALID', 'Verification failed. Please try again.')

    raw_hosts = os.environ.get('TURNSTILE_ALLOWED_HOSTNAMES', '').strip()
    allowed_hosts = {host.lower().rstrip('.') for host in re.split(r'[,;\s]+', raw_hosts) if host} if raw_hosts else set(PRODUCTION_HOSTNAMES)
    if development and not raw_hosts:
        allowed_hosts.update({'localhost', '127.0.0.1'})
    if not development:
        allowed_hosts.difference_update({'localhost', '127.0.0.1', '0.0.0.0', '::1'})
    hostname = result.get('hostname')
    if not isinstance(hostname, str) or hostname.lower().rstrip('.') not in allowed_hosts:
        return CaptchaFailure('CAPTCHA_INVALID', 'Verification failed. Please try again.')
    try:
        timestamp = datetime.fromisoformat(result['challenge_ts'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            raise ValueError('Missing timezone')
    except (KeyError, AttributeError, TypeError, ValueError):
        return CaptchaFailure('CAPTCHA_INVALID', 'Verification failed. Please try again.')
    # Siteverify enforces five-minute expiry and single use; do not add a second
    # expiry rule based on the application server's clock.
    return None
