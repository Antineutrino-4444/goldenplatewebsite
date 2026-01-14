import logging
import os
import random
import string
from datetime import datetime, timedelta, timezone

import requests as http_requests

from .db import EmailVerification, db_session, _now_utc

logger = logging.getLogger(__name__)

BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'


def _get_brevo_config():
    """Get Brevo configuration from environment variables at runtime."""
    return {
        'api_key': os.environ.get('BREVO_API_KEY', ''),
        'sender_email': os.environ.get('BREVO_SENDER_EMAIL', 'no-reply@goldenplate.ca'),
    }

VERIFICATION_CODE_LENGTH = 6
VERIFICATION_CODE_EXPIRY_MINUTES = 15
MAX_VERIFICATION_ATTEMPTS = 5


def generate_verification_code() -> str:
    """Generate a random 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=VERIFICATION_CODE_LENGTH))


def send_email_via_brevo(to_email: str, subject: str, html_content: str) -> dict:
    """Send an email using Brevo's API."""
    config = _get_brevo_config()
    api_key = config['api_key']
    sender_email = config['sender_email']

    if not api_key:
        logger.error('Email send failed: BREVO_API_KEY environment variable is not set')
        return {'success': False, 'error': 'Brevo API key not configured. Please set BREVO_API_KEY in your .env file.'}

    headers = {
        'accept': 'application/json',
        'api-key': api_key,
        'content-type': 'application/json',
    }

    payload = {
        'sender': {'email': sender_email},
        'to': [{'email': to_email}],
        'subject': subject,
        'htmlContent': html_content,
    }

    try:
        logger.info(f'Sending verification email to {to_email}')
        response = http_requests.post(
            BREVO_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code in (200, 201):
            message_id = response.json().get('messageId')
            logger.info(f'Email sent successfully to {to_email}, message_id: {message_id}')
            return {'success': True, 'message_id': message_id}
        else:
            error_detail = response.json() if response.content else {}
            logger.error(f'Brevo API error {response.status_code} for {to_email}: {error_detail}')
            return {
                'success': False,
                'error': f'Brevo API error: {response.status_code}',
                'detail': error_detail,
            }
    except http_requests.exceptions.Timeout:
        logger.error(f'Brevo API timeout when sending to {to_email}')
        return {'success': False, 'error': 'Request to Brevo timed out'}
    except http_requests.exceptions.RequestException as e:
        logger.error(f'Network error sending email to {to_email}: {str(e)}')
        return {'success': False, 'error': f'Network error: {str(e)}'}
    except Exception as e:
        logger.exception(f'Unexpected error sending email to {to_email}')
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}


def create_verification_code(email: str, purpose: str = 'school_registration') -> EmailVerification:
    """Create a new email verification code record."""
    from sqlalchemy import func

    # Normalize email to lowercase for consistent storage and lookup
    normalized_email = (email or '').strip().lower()

    if not normalized_email:
        raise ValueError('Email address is required')

    logger.info(f'Creating verification code for email={normalized_email}, purpose={purpose}')

    # Invalidate any existing unused codes for this email/purpose (case-insensitive)
    existing_codes = db_session.query(EmailVerification).filter(
        func.lower(EmailVerification.email) == normalized_email,
        EmailVerification.purpose == purpose,
        EmailVerification.verified_at.is_(None),
    ).all()

    if existing_codes:
        logger.info(f'Removing {len(existing_codes)} existing unused codes for {normalized_email}')
        for code_record in existing_codes:
            db_session.delete(code_record)

    # Create new verification code
    code = generate_verification_code()
    expires_at = _now_utc() + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES)

    verification = EmailVerification(
        email=normalized_email,  # Store normalized email
        code=code,
        purpose=purpose,
        expires_at=expires_at,
        attempts=0,
    )

    db_session.add(verification)
    db_session.commit()

    logger.info(f'Created verification code for {normalized_email}, code={code}, expires_at={expires_at.isoformat()}')

    return verification


def send_verification_email(email: str, code: str) -> dict:
    """Send a verification code email to the specified address."""
    subject = 'Golden Plate - Email Verification Code'

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #d97706 0%, #ca8a04 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }}
            .content {{
                background: #ffffff;
                padding: 30px;
                border: 1px solid #e5e7eb;
                border-top: none;
                border-radius: 0 0 10px 10px;
            }}
            .code-box {{
                background: #fef3c7;
                border: 2px solid #d97706;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                margin: 20px 0;
            }}
            .code {{
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 8px;
                color: #92400e;
                font-family: 'Courier New', monospace;
            }}
            .footer {{
                text-align: center;
                color: #6b7280;
                font-size: 12px;
                margin-top: 20px;
            }}
            .warning {{
                color: #dc2626;
                font-size: 13px;
                margin-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1 style="margin: 0; font-size: 24px;">Golden Plate Recorder</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">School Registration Verification</p>
        </div>
        <div class="content">
            <p>Hello,</p>
            <p>You have requested to register your school with Golden Plate Recorder. Please use the verification code below to complete your registration:</p>

            <div class="code-box">
                <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 14px;">Your Verification Code</p>
                <div class="code">{code}</div>
            </div>

            <p>This code will expire in <strong>{VERIFICATION_CODE_EXPIRY_MINUTES} minutes</strong>.</p>

            <p class="warning">If you did not request this verification code, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>This is an automated message from Golden Plate Recorder.</p>
            <p>Please do not reply to this email.</p>
        </div>
    </body>
    </html>
    '''

    return send_email_via_brevo(email, subject, html_content)


def verify_code(email: str, code: str, purpose: str = 'school_registration') -> dict:
    """Verify an email verification code."""
    # Normalize inputs
    normalized_email = (email or '').strip().lower()
    normalized_code = (code or '').strip()

    logger.info(f'Verification attempt for email={normalized_email}, code_length={len(normalized_code)}, purpose={purpose}')

    if not normalized_email:
        logger.warning('Verification failed: empty email provided')
        return {'valid': False, 'error': 'Email address is required'}

    if not normalized_code:
        logger.warning('Verification failed: empty code provided')
        return {'valid': False, 'error': 'Verification code is required'}

    # Query for pending verification - use case-insensitive email match
    from sqlalchemy import func
    verification = db_session.query(EmailVerification).filter(
        func.lower(EmailVerification.email) == normalized_email,
        EmailVerification.purpose == purpose,
        EmailVerification.verified_at.is_(None),
    ).order_by(EmailVerification.created_at.desc()).first()

    if not verification:
        # Log additional debug info - check if there are any records for this email
        all_records = db_session.query(EmailVerification).filter(
            func.lower(EmailVerification.email) == normalized_email,
        ).all()
        if all_records:
            statuses = [f"id={r.id}, purpose={r.purpose}, verified={r.verified_at is not None}, expired={_now_utc() > r.expires_at}" for r in all_records]
            logger.warning(f'No pending verification found for {normalized_email}. Existing records: {statuses}')
            # Check if already verified
            already_verified = any(r.verified_at is not None and r.purpose == purpose for r in all_records)
            if already_verified:
                return {'valid': False, 'error': 'This email has already been verified. Please proceed with registration.'}
            return {'valid': False, 'error': 'No pending verification code found. The code may have expired or been used. Please request a new one.'}
        else:
            logger.warning(f'No verification records exist for {normalized_email}')
            return {'valid': False, 'error': 'No verification code found for this email. Please request a verification code first.'}

    logger.info(f'Found verification record id={verification.id}, stored_code_length={len(verification.code)}, attempts={verification.attempts}')

    # Check if expired
    now = _now_utc()

    # Handle timezone-aware vs naive datetime comparison (SQLite stores naive datetimes)
    expires_at = verification.expires_at
    if expires_at.tzinfo is None:
        # Make expires_at timezone-aware (assume UTC)
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        time_diff = now - expires_at
        logger.warning(f'Verification code expired for {normalized_email}. Expired {abs(time_diff.total_seconds()):.0f}s ago')
        return {'valid': False, 'error': 'Verification code has expired. Please request a new one.'}

    # Check attempt limit
    if verification.attempts >= MAX_VERIFICATION_ATTEMPTS:
        logger.warning(f'Too many attempts for {normalized_email}. Attempts: {verification.attempts}')
        return {'valid': False, 'error': 'Too many failed attempts. Please request a new code.'}

    # Check code - normalize both for comparison
    stored_code = (verification.code or '').strip()
    if stored_code != normalized_code:
        verification.attempts += 1
        db_session.commit()
        remaining = MAX_VERIFICATION_ATTEMPTS - verification.attempts
        logger.warning(
            f'Code mismatch for {normalized_email}. '
            f'Provided: "{normalized_code}" (len={len(normalized_code)}), '
            f'Expected: "{stored_code}" (len={len(stored_code)}). '
            f'{remaining} attempts remaining.'
        )
        if remaining > 0:
            return {
                'valid': False,
                'error': f'Invalid verification code. {remaining} attempts remaining.',
                'debug': {
                    'attempts_used': verification.attempts,
                    'attempts_remaining': remaining,
                    'code_length_provided': len(normalized_code),
                    'code_length_expected': len(stored_code),
                }
            }
        else:
            return {'valid': False, 'error': 'Too many failed attempts. Please request a new code.'}

    # Mark as verified
    verification.verified_at = now
    db_session.commit()
    logger.info(f'Email {normalized_email} verified successfully. Verification ID: {verification.id}')

    return {'valid': True, 'verification_id': verification.id}


def is_email_verified(email: str, purpose: str = 'school_registration', max_age_minutes: int = 30) -> bool:
    """Check if an email has been recently verified for the given purpose."""
    from sqlalchemy import func

    # Normalize email for case-insensitive lookup
    normalized_email = (email or '').strip().lower()

    if not normalized_email:
        logger.warning('is_email_verified called with empty email')
        return False

    cutoff = _now_utc() - timedelta(minutes=max_age_minutes)

    verification = db_session.query(EmailVerification).filter(
        func.lower(EmailVerification.email) == normalized_email,
        EmailVerification.purpose == purpose,
        EmailVerification.verified_at.isnot(None),
        EmailVerification.verified_at >= cutoff,
    ).first()

    is_verified = verification is not None
    logger.info(f'is_email_verified check: email={normalized_email}, purpose={purpose}, verified={is_verified}')

    return is_verified


__all__ = [
    'generate_verification_code',
    'send_email_via_brevo',
    'create_verification_code',
    'send_verification_email',
    'verify_code',
    'is_email_verified',
    'VERIFICATION_CODE_EXPIRY_MINUTES',
]
