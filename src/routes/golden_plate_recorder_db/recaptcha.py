"""Shared, fail-closed validation for the five reCAPTCHA v3 actions."""
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from .app_config import is_development_environment

VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'
PRODUCTION_HOSTNAMES = {'goldenplate.ca', 'www.goldenplate.ca', 'map.goldenplate.ca'}


@dataclass(frozen=True)
class RecaptchaFailure:
    code: str
    message: str
    status: int = 400


def recaptcha_failure(token, expected_action):
    """Return None only for verified v3 tokens or unconfigured local development."""
    secret = os.environ.get('RECAPTCHA_SECRET_KEY', '').strip()
    if not secret:
        if is_development_environment():
            return None
        return RecaptchaFailure('RECAPTCHA_UNAVAILABLE', 'Verification is temporarily unavailable. Please contact an administrator.', 503)
    if not isinstance(token, str) or not token.strip():
        return RecaptchaFailure('RECAPTCHA_REQUIRED', 'Verification is required. Please try submitting again.')
    try:
        minimum_score = float(os.environ.get('RECAPTCHA_MIN_SCORE', '0.5'))
        if not math.isfinite(minimum_score) or not 0 <= minimum_score <= 1:
            raise ValueError('Invalid score threshold')
    except ValueError:
        return RecaptchaFailure('RECAPTCHA_UNAVAILABLE', 'Verification is temporarily unavailable. Please contact an administrator.', 503)

    try:
        response = requests.post(VERIFY_URL, data={'secret': secret, 'response': token.strip()}, timeout=10)
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError):
        return RecaptchaFailure('RECAPTCHA_UNAVAILABLE', 'Unable to verify this request right now. Please try again.', 503)
    if not isinstance(result, dict):
        return RecaptchaFailure('RECAPTCHA_INVALID', 'Verification failed. Please try again.')
    errors = result.get('error-codes')
    if errors:
        if isinstance(errors, list) and 'timeout-or-duplicate' in errors:
            return RecaptchaFailure('RECAPTCHA_EXPIRED', 'Verification expired or was already used. Please submit again to get a fresh verification.')
        # Reject errors even when Google also reports success (e.g. quota errors).
        return RecaptchaFailure('RECAPTCHA_INVALID', 'Verification failed. Please try again or contact an administrator.')
    if result.get('success') is not True or result.get('action') != expected_action:
        return RecaptchaFailure('RECAPTCHA_INVALID', 'Verification failed. Please try again.')

    raw_hosts = os.environ.get('RECAPTCHA_ALLOWED_HOSTNAMES', '').strip()
    allowed_hosts = {host.lower().rstrip('.') for host in re.split(r'[,;\s]+', raw_hosts)} if raw_hosts else set(PRODUCTION_HOSTNAMES)
    if not raw_hosts and is_development_environment():
        allowed_hosts.update({'localhost', '127.0.0.1'})
    hostname = result.get('hostname')
    if not isinstance(hostname, str) or hostname.lower().rstrip('.') not in allowed_hosts:
        return RecaptchaFailure('RECAPTCHA_INVALID', 'Verification failed. Please try again.')
    score = result.get('score')
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1 or not math.isfinite(score):
        return RecaptchaFailure('RECAPTCHA_INVALID', 'Verification failed. Please try again.')
    if score < minimum_score:
        return RecaptchaFailure('RECAPTCHA_LOW_SCORE', 'Unable to verify this request. Please try again or contact an administrator for help.', 403)
    try:
        timestamp = datetime.fromisoformat(result['challenge_ts'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            raise ValueError('Missing timezone')
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
    except (KeyError, AttributeError, TypeError, ValueError):
        return RecaptchaFailure('RECAPTCHA_INVALID', 'Verification failed. Please try again.')
    if age < -30:
        return RecaptchaFailure('RECAPTCHA_INVALID', 'Verification failed. Please try again.')
    if age > 120:
        return RecaptchaFailure('RECAPTCHA_EXPIRED', 'Verification expired. Please submit again to get a fresh verification.')
    return None
