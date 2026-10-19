"""Persistent notification choices and private per-recipient management links."""

import json
import os
import re
from html import escape

from sqlalchemy.exc import IntegrityError


NOTIFICATION_TYPES = {
    'account_lifecycle': ('Account inactivity notices', 'Warnings about disabled accounts and permanent account deletion.'),
    'server_startup': ('Server restarts', 'Announcements when the website server starts or reloads.'),
    'school_registration': ('School registration requests', 'New schools requesting registration.'),
    'account_signup': ('Account signup requests', 'People requesting an account at a school.'),
    'invite_signup': ('Invite signups', 'Accounts created using a school invite code.'),
    'map_submission': ('Map submissions to review', 'New ecological map submissions awaiting review.'),
    'map_status': ('Map submission decisions', 'Rejection or deletion messages about your submissions.'),
}


def prepare_email_preferences(email, notification_type=None):
    """Use a separate short transaction so email cannot commit application work."""
    from src.routes.golden_plate_recorder_db.db import EmailNotificationPreference, SessionFactory

    if notification_type is not None and notification_type not in NOTIFICATION_TYPES:
        raise ValueError('Unknown notification type')
    normalized = email.strip().lower()
    for attempt in range(2):
        try:
            with SessionFactory() as session:
                preference = session.get(EmailNotificationPreference, normalized)
                if preference is None:
                    preference = EmailNotificationPreference(email=normalized)
                    session.add(preference)
                    session.flush()
                known = set(json.loads(preference.known_types))
                if notification_type:
                    known.add(notification_type)
                    preference.known_types = json.dumps(sorted(known))
                allowed = notification_type not in json.loads(preference.disabled_types)
                token = preference.token
                session.commit()
                base_url = os.environ.get('WEBSITE_PUBLIC_URL', 'https://goldenplate.ca').rstrip('/')
                return allowed, f'{base_url}/api/notifications/preferences/{token}'
        except IntegrityError:
            if attempt:
                raise


def add_preferences_footer(html, url):
    footer = (
        '<div style="margin:24px 0;padding:16px;border-top:1px solid #ddd;'
        'font-family:Arial,sans-serif;font-size:13px;color:#666">'
        f'<a href="{escape(url, quote=True)}">Unsubscribe or manage notification preferences</a>'
        '</div>'
    )
    if re.search(r'</body\s*>', html, flags=re.IGNORECASE):
        return re.sub(r'</body\s*>', lambda _: footer + '</body>', html, count=1, flags=re.IGNORECASE)
    return html + footer
