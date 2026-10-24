"""User-requested website update notifications."""

import logging
import os
import re
from datetime import datetime, timezone
from html import escape
from functools import partial

from .email_delivery import send_email_via_brevo

logger = logging.getLogger(__name__)


def get_website_update_recipients():
    """Use only configured recipients; an empty or missing setting disables mail."""
    recipients = re.split(r'[\s,;]+', os.environ.get('WEBSITE_UPDATE_NOTIFY_EMAILS', ''))
    unique = {}
    for recipient in recipients:
        recipient = recipient.strip()
        if recipient:
            unique.setdefault(recipient.lower(), recipient)
    return list(unique.values())


def notify_website_update(title, summary, details=(), *, url=None, notification_type='server_startup'):
    return send_notification(title, summary, details, url=url,
                             recipients=get_website_update_recipients(), notification_type=notification_type)


def notify_school_registration(registration_request, *, recipients=None):
    """Send the standard new-school request email using the saved request fields."""
    sender = notify_website_update if recipients is None else partial(send_notification, recipients=recipients)
    return sender(
        'New school registration request',
        'A school has requested registration and is awaiting administrator approval. '
        'Sign in to the inter-school administrator dashboard to review it.',
        [
            ('School', registration_request.school_name),
            ('Applicant email', registration_request.email),
            ('Requested school code', registration_request.school_slug or 'Automatic from school name'),
            ('Administrator name', registration_request.admin_display_name),
            ('Administrator username', registration_request.admin_username),
            ('Request ID', registration_request.id),
        ], notification_type='school_registration',
    )


def notify_school_approval(school, admin_user):
    """Send the applicant a transactional confirmation after approval is saved."""
    return send_notification(
        'Your school has been approved',
        f'Your school, {school.name}, has been approved. You can now sign in '
        'to Golden Plate using the username and password you chose during registration. '
        'Your signup email is already saved and verified on your account.',
        [('School', school.name), ('Username', admin_user.username)],
        recipients=[admin_user.email], notification_type=None,
    )


def send_notification(title, summary, details=(), *, url=None, recipients=(), notification_type='server_startup'):
    """Send escaped metadata only, never passwords, verification codes or secrets.

    Return delivery status instead of raising, so a mail failure cannot discard
    an already saved signup request or stop a running deployment.
    """
    unique = {}
    for recipient in recipients:
        recipient = recipient.strip()
        if recipient:
            unique.setdefault(recipient.lower(), recipient)
    recipients = list(unique.values())
    if not recipients:
        return {'success': True, 'skipped': True, 'deliveries': {}}
    html = render_notification(title, summary, details, url=url)
    results = {}
    for recipient in recipients:
        try:
            result = send_email_via_brevo(recipient, f'Golden Plate — {title}', html, notification_type=notification_type)
        except Exception:
            logger.exception('Website update notification failed for %s', recipient)
            result = {'success': False, 'error': 'Email delivery failed'}
        results[recipient] = result
        if not result.get('success'):
            logger.warning('Website update email to %s failed: %s', recipient, result.get('error'))
    return {'success': all(result.get('success') for result in results.values()), 'deliveries': results}


def render_notification(title, summary, details=(), *, url=None):
    """Render notification metadata without resolving recipients or sending mail."""
    website_url = url or os.environ.get('WEBSITE_PUBLIC_URL', 'https://goldenplate.ca')
    rows = ''.join(
        f'<tr><th align="left">{escape(str(label))}</th>'
        f'<td>{escape(str(value))}</td></tr>'
        for label, value in details
    )
    html = (
        f'<h1>{escape(title)}</h1><p>{escape(summary)}</p><table>{rows}</table>'
        f'<p>Notification time: {datetime.now(timezone.utc).isoformat()}</p>'
        f'<p><a href="{escape(website_url, quote=True)}">Open Golden Plate</a></p>'
    )
    return html
