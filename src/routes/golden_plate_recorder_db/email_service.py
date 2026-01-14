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
    # Invalidate any existing unused codes for this email/purpose
    existing_codes = db_session.query(EmailVerification).filter(
        EmailVerification.email == email,
        EmailVerification.purpose == purpose,
        EmailVerification.verified_at.is_(None),
    ).all()

    for code_record in existing_codes:
        db_session.delete(code_record)

    # Create new verification code
    code = generate_verification_code()
    expires_at = _now_utc() + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES)

    verification = EmailVerification(
        email=email,
        code=code,
        purpose=purpose,
        expires_at=expires_at,
        attempts=0,
    )

    db_session.add(verification)
    db_session.commit()

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
    verification = db_session.query(EmailVerification).filter(
        EmailVerification.email == email,
        EmailVerification.purpose == purpose,
        EmailVerification.verified_at.is_(None),
    ).order_by(EmailVerification.created_at.desc()).first()

    if not verification:
        return {'valid': False, 'error': 'No verification code found for this email'}

    # Check if expired
    now = _now_utc()
    if now > verification.expires_at:
        return {'valid': False, 'error': 'Verification code has expired. Please request a new one.'}

    # Check attempt limit
    if verification.attempts >= MAX_VERIFICATION_ATTEMPTS:
        return {'valid': False, 'error': 'Too many failed attempts. Please request a new code.'}

    # Check code
    if verification.code != code:
        verification.attempts += 1
        db_session.commit()
        remaining = MAX_VERIFICATION_ATTEMPTS - verification.attempts
        if remaining > 0:
            return {'valid': False, 'error': f'Invalid code. {remaining} attempts remaining.'}
        else:
            return {'valid': False, 'error': 'Too many failed attempts. Please request a new code.'}

    # Mark as verified
    verification.verified_at = now
    db_session.commit()

    return {'valid': True, 'verification_id': verification.id}


def is_email_verified(email: str, purpose: str = 'school_registration', max_age_minutes: int = 30) -> bool:
    """Check if an email has been recently verified for the given purpose."""
    cutoff = _now_utc() - timedelta(minutes=max_age_minutes)

    verification = db_session.query(EmailVerification).filter(
        EmailVerification.email == email,
        EmailVerification.purpose == purpose,
        EmailVerification.verified_at.isnot(None),
        EmailVerification.verified_at >= cutoff,
    ).first()

    return verification is not None


__all__ = [
    'generate_verification_code',
    'send_email_via_brevo',
    'create_verification_code',
    'send_verification_email',
    'verify_code',
    'is_email_verified',
    'VERIFICATION_CODE_EXPIRY_MINUTES',
]
