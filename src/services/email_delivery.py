"""Email delivery shared by the website and deployment tools; no database imports."""

import logging
import os

import requests as http_requests

logger = logging.getLogger(__name__)

BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'


def _get_brevo_config():
    """Get Brevo configuration from environment variables at runtime."""
    return {
        'api_key': os.environ.get('BREVO_API_KEY', ''),
        'sender_email': os.environ.get('BREVO_SENDER_EMAIL', 'no-reply@goldenplate.ca'),
    }


def send_email_via_brevo(to_email: str, subject: str, html_content: str, attachments: list | None = None) -> dict:
    """Send an email using Brevo's API.

    `attachments` is an optional list of dicts shaped like
    ``{"name": "image.png", "content": "<base64 string>"}`` per the Brevo
    SMTP API spec. The ``content`` value MUST already be base64-encoded.
    """
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
    if attachments:
        payload['attachment'] = attachments

    try:
        logger.info(f'Sending email to {to_email}')
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
