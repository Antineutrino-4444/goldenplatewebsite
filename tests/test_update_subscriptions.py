import json
from datetime import timedelta

import pytest

from src.main import app
from src.routes.golden_plate_recorder_db import update_subscription_routes as routes
from src.routes.golden_plate_recorder_db.db import (
    EmailNotificationPreference, EmailVerification, WebsiteUpdateSubscriber, _now_utc, db_session,
)
from src.services.release_notifications import get_release_recipients, send_release_email
from src.services import website_notifications

SEND = '/api/updates/send-verification-code'
SUBSCRIBE = '/api/updates/subscribe'
EMAIL = 'subscriber@example.com'


@pytest.fixture(autouse=True)
def clear_subscriptions():
    for model in (WebsiteUpdateSubscriber,):
        db_session.query(model).delete()
    db_session.query(EmailVerification).filter_by(purpose='website_updates').delete()
    db_session.commit()
    yield
    db_session.query(WebsiteUpdateSubscriber).delete()
    db_session.query(EmailVerification).filter_by(purpose='website_updates').delete()
    db_session.commit()


def challenge(client, email=EMAIL):
    response = client.post(SEND, json={'email': email})
    assert response.status_code == 200
    with client.session_transaction() as session:
        record = db_session.get(EmailVerification, session['website_updates_challenge'])
    return record.id, record.code, response


def subscribe(client, email=EMAIL):
    _, code, _ = challenge(client, email)
    return client.post(SUBSCRIBE, json={'email': email, 'verification_code': code})


def test_verified_subscription_notifies_only_configured_addresses(client, email_outbox, monkeypatch, caplog):
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', ' Owner@Example.com;owner@example.com, other@example.com ')
    record_id, code, response = challenge(client, ' Subscriber@Example.com ')
    assert response.json['expiry_minutes'] == 5
    assert code not in response.text and code not in caplog.text
    with client.session_transaction() as session:
        assert code not in str(dict(session))
    assert len(email_outbox) == 1
    assert 'Website Updates Verification' in email_outbox[0]['htmlContent']
    assert code in email_outbox[0]['htmlContent']
    assert db_session.get(WebsiteUpdateSubscriber, EMAIL) is None
    result = client.post(SUBSCRIBE, json={'email': EMAIL, 'verification_code': code})
    assert result.status_code == 201
    assert db_session.get(WebsiteUpdateSubscriber, EMAIL)
    assert db_session.get(EmailVerification, record_id).verified_at
    assert EMAIL in get_release_recipients(db_session)
    assert sorted(mail['to'][0]['email'].lower() for mail in email_outbox[1:]) == ['other@example.com', 'owner@example.com']
    for mail in email_outbox[1:]:
        assert EMAIL in mail['htmlContent']
        assert code not in mail['htmlContent']
        assert 'New website update subscriber' in mail['subject']
    assert client.post(SUBSCRIBE, json={'email': EMAIL, 'verification_code': code}).status_code == 400


@pytest.mark.parametrize('email', [None, '', [], 'invalid', 'a@example.com,b@example.com'])
def test_invalid_email_rejected(client, email, email_outbox):
    for endpoint in (SEND, SUBSCRIBE):
        assert client.post(endpoint, json={'email': email}).status_code == 400
        assert client.post(endpoint, json=['invalid']).status_code == 400
    assert email_outbox == []


def test_code_is_required_and_bound_to_browser_email_and_purpose(client):
    assert client.post(SUBSCRIBE, json={'email': EMAIL, 'email_verified': True}).status_code == 400
    record_id, code, _ = challenge(client)
    with app.test_client() as other:
        assert other.post(SUBSCRIBE, json={'email': EMAIL, 'verification_code': code}).status_code == 400
    assert client.post(SUBSCRIBE, json={'email': 'other@example.com', 'verification_code': code}).status_code == 400
    record = db_session.get(EmailVerification, record_id)
    record.purpose = 'account_signup'
    db_session.commit()
    assert client.post(SUBSCRIBE, json={'email': EMAIL, 'verification_code': code}).status_code == 400
    assert db_session.get(WebsiteUpdateSubscriber, EMAIL) is None


def test_expiry_attempt_limit_and_resend(client, email_outbox):
    record_id, code, _ = challenge(client)
    record = db_session.get(EmailVerification, record_id)
    record.expires_at = _now_utc() - timedelta(seconds=1)
    record.created_at = _now_utc() - timedelta(seconds=61)
    db_session.commit()
    assert 'expired' in client.post(SUBSCRIBE, json={'email': EMAIL, 'verification_code': code}).json['error']
    _, code, _ = challenge(client)
    assert client.post(SEND, json={'email': EMAIL}).status_code == 429
    wrong = '000000' if code != '000000' else '111111'
    for _ in range(5):
        assert client.post(SUBSCRIBE, json={'email': EMAIL, 'verification_code': wrong}).status_code == 400
    result = client.post(SUBSCRIBE, json={'email': EMAIL, 'verification_code': code})
    assert result.status_code == 400 and 'Too many' in result.json['error']
    assert len(email_outbox) == 2
    assert db_session.get(WebsiteUpdateSubscriber, EMAIL) is None


def test_resend_invalidates_previous_code(client, monkeypatch):
    from src.routes.golden_plate_recorder_db import email_service
    codes = iter(['123456', '654321'])
    monkeypatch.setattr(email_service, 'generate_verification_code', lambda: next(codes))
    record_id, old_code, _ = challenge(client)
    db_session.get(EmailVerification, record_id).created_at = _now_utc() - timedelta(seconds=61)
    db_session.commit()
    _, new_code, _ = challenge(client)
    assert client.post(SUBSCRIBE, json={'email': EMAIL, 'verification_code': old_code}).status_code == 400
    assert client.post(SUBSCRIBE, json={'email': EMAIL, 'verification_code': new_code}).status_code == 201


def test_delivery_failure_does_not_leave_usable_challenge(client, monkeypatch):
    monkeypatch.setattr(routes, 'send_verification_email', lambda *a, **kw: {'success': False})
    assert client.post(SEND, json={'email': EMAIL}).status_code == 503
    with client.session_transaction() as session:
        assert 'website_updates_challenge' not in session
    assert db_session.query(EmailVerification).filter_by(email=EMAIL, purpose='website_updates').first() is None
    assert db_session.get(WebsiteUpdateSubscriber, EMAIL) is None


def test_alert_failure_keeps_subscription_and_reports_warning(client, monkeypatch, caplog):
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', 'owner@example.com')
    record_id, code, _ = challenge(client)
    monkeypatch.setattr(website_notifications, 'send_email_via_brevo', lambda *a, **kw: {'success': False, 'error': 'Offline'})
    response = client.post(SUBSCRIBE, json={'email': EMAIL, 'verification_code': code})
    assert response.status_code == 201 and response.json['warning']
    assert 'signup alert delivery failed' in caplog.text
    assert db_session.get(WebsiteUpdateSubscriber, EMAIL)
    assert db_session.get(EmailVerification, record_id).verified_at


def test_unsubscribe_and_verified_resubscribe_preserve_other_preferences(client, email_outbox, monkeypatch):
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', '')
    assert subscribe(client).status_code == 201
    assert len(email_outbox) == 1  # Only the requested verification email.
    preference = db_session.get(EmailNotificationPreference, EMAIL)
    token = preference.token
    client.post(f'/api/notifications/preferences/{token}', data={'action': 'unsubscribe_all'})
    email_outbox.clear()
    assert send_release_email(EMAIL, [('9.0', '- Update')])['skipped']
    assert email_outbox == []
    record = db_session.query(EmailVerification).filter_by(email=EMAIL, purpose='website_updates').one()
    record.created_at = _now_utc() - timedelta(seconds=61)
    db_session.commit()
    assert subscribe(client).status_code == 201
    preference = db_session.get(EmailNotificationPreference, EMAIL)
    assert 'release_notes' not in json.loads(preference.disabled_types)
    assert 'map_submission' in json.loads(preference.disabled_types)
    assert send_release_email(EMAIL, [('9.1', '- Next update')])['success']
    assert 'Next update' in email_outbox[-1]['htmlContent']


def test_repeated_subscription_is_idempotent_and_sends_no_repeat_alert(client, email_outbox, monkeypatch):
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', 'owner@example.com')
    assert subscribe(client).status_code == 201
    email_outbox.clear()
    record = db_session.query(EmailVerification).filter_by(email=EMAIL, purpose='website_updates').one()
    record.created_at = _now_utc() - timedelta(seconds=61)
    db_session.commit()
    assert subscribe(client, 'SUBSCRIBER@example.com').status_code == 200
    assert len(email_outbox) == 1
    assert db_session.query(WebsiteUpdateSubscriber).count() == 1


def test_captcha_is_required_for_public_send(client, monkeypatch, email_outbox):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('TURNSTILE_SECRET_KEY', 'production-secret')
    response = client.post(SEND, json={'email': EMAIL})
    assert response.status_code == 400 and response.json['code'] == 'CAPTCHA_REQUIRED'
    assert email_outbox == []


def test_signed_in_visitors_can_subscribe(client, login, monkeypatch):
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', '')
    login()
    assert subscribe(client).status_code == 201
