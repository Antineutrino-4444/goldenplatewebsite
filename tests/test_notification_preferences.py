import html
import re
from urllib.parse import urlsplit

from src.routes.golden_plate_recorder_db.db import EmailNotificationPreference, db_session
from src.services.email_delivery import send_email_via_brevo
from src.services.notification_preferences import NOTIFICATION_TYPES
from src.services.website_notifications import notify_website_update


def preferences_path(message):
    url = re.search(r'href="([^"]+)"[^>]*>Unsubscribe or manage notification preferences', message['htmlContent']).group(1)
    return urlsplit(html.unescape(url)).path


def test_every_email_has_a_persistent_private_preferences_link(client, email_outbox, monkeypatch):
    monkeypatch.setenv('WEBSITE_PUBLIC_URL', 'https://goldenplate.example')
    assert send_email_via_brevo('Reader@Example.com', 'Verification code', '<html><body>Requested code</body></html>')['success']
    path = preferences_path(email_outbox[-1])
    assert '@' not in path
    assert email_outbox[-1]['htmlContent'].index('Unsubscribe') < email_outbox[-1]['htmlContent'].index('</body>')
    response = client.get(path)
    assert response.status_code == 200 and b'reader@example.com' in response.data
    assert response.headers['Cache-Control'] == 'no-store'
    for title, _ in NOTIFICATION_TYPES.values():
        assert title.encode() in response.data
    # Reading the link cannot unsubscribe someone (including email link scanners).
    assert db_session.get(EmailNotificationPreference, 'reader@example.com').disabled_types == '[]'
    assert send_email_via_brevo('reader@example.com', 'Another email', '<p>Hello</p>')['success']
    assert preferences_path(email_outbox[-1]) == path
    assert client.get(path[:-1] + ('X' if path[-1] != 'X' else 'Y')).status_code == 404


def test_selective_unsubscribe_filters_notifications_but_not_requested_codes(client, email_outbox, monkeypatch):
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', 'reader@example.com')
    notify_website_update('Website started', 'Startup')
    path = preferences_path(email_outbox[-1])
    data = {key: 'on' for key in NOTIFICATION_TYPES if key != 'server_startup'}
    response = client.post(path, data={**data, 'action': 'save'}, follow_redirects=True)
    assert response.status_code == 200 and b'Preferences saved.' in response.data
    email_outbox.clear()
    result = notify_website_update('Website started', 'Startup')
    assert result['success'] and result['deliveries']['reader@example.com']['skipped']
    assert email_outbox == []
    notify_website_update('School signup', 'New school', notification_type='school_registration')
    assert len(email_outbox) == 1

    assert client.post(path, data={'action': 'unsubscribe_all'}).status_code == 303
    email_outbox.clear()
    for key in NOTIFICATION_TYPES:
        assert send_email_via_brevo('reader@example.com', 'Alert', '<p>Alert</p>', notification_type=key)['skipped']
    assert email_outbox == []
    assert send_email_via_brevo('reader@example.com', 'Requested verification', '<p>123456</p>')['success']
    assert len(email_outbox) == 1 and preferences_path(email_outbox[0]) == path
    # Re-enabling only invite signups does not alter any configured recipient list.
    client.post(path, data={'action': 'save', 'invite_signup': 'on'})
    assert send_email_via_brevo('READER@example.com', 'Invite signup', '<p>Invite</p>', notification_type='invite_signup')['success']
    assert len(email_outbox) == 2


def test_preferences_are_independent_for_each_recipient(client, email_outbox):
    for email in ['first@example.com', 'second@example.com']:
        send_email_via_brevo(email, 'Notice', '<p>Notice</p>', notification_type='map_submission')
    first, second = [preferences_path(message) for message in email_outbox]
    assert first != second
    client.post(first, data={'action': 'unsubscribe_all'})
    email_outbox.clear()
    send_email_via_brevo('first@example.com', 'Map', '<p>Map</p>', notification_type='map_submission')
    send_email_via_brevo('second@example.com', 'Map', '<p>Map</p>', notification_type='map_submission')
    assert len(email_outbox) == 1 and email_outbox[0]['to'] == [{'email': 'second@example.com'}]
