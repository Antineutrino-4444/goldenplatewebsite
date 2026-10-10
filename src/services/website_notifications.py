"""User-requested website update notifications."""

import logging
import os
from datetime import datetime, timezone
from html import escape

from .email_delivery import send_email_via_brevo

logger = logging.getLogger(__name__)
WEBSITE_UPDATE_RECIPIENT = 'matthew.jaekel@sac.on.ca'


def get_website_update_recipients():
    """Matthew always receives updates; the environment can add other recipients."""
    extras = os.environ.get('WEBSITE_UPDATE_NOTIFY_EMAILS', '').replace(';', ',')
    recipients = [WEBSITE_UPDATE_RECIPIENT, *extras.split(',')]
    unique = {}
    for recipient in recipients:
        recipient = recipient.strip()
        if recipient:
            unique.setdefault(recipient.lower(), recipient)
    return list(unique.values())


def notify_website_update(title, summary, details=(), *, url=None):
    """Send escaped metadata only, never passwords, verification codes or secrets.

    Return delivery status instead of raising, so a mail failure cannot discard
    an already saved signup request or stop a running deployment.
    """
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
    results = {}
    for recipient in get_website_update_recipients():
        try:
            result = send_email_via_brevo(recipient, f'Golden Plate — {title}', html)
        except Exception:
            logger.exception('Website update notification failed for %s', recipient)
            result = {'success': False, 'error': 'Email delivery failed'}
        results[recipient] = result
        if not result.get('success'):
            logger.warning('Website update email to %s failed: %s', recipient, result.get('error'))
    return {'success': all(result.get('success') for result in results.values()), 'deliveries': results}
