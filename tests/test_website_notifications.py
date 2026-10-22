import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import requests
import pytest

from src.routes.golden_plate_recorder_db import interschool_routes, map_routes
from src.routes.golden_plate_recorder_db.email_service import send_verification_email
from src.routes.golden_plate_recorder_db.db import SchoolRegistrationRequest, db_session
from src.services import email_delivery, website_notifications

RECIPIENT = 'updates@example.com'


def test_verification_code_is_sent_only_to_applicant(email_outbox):
    result = send_verification_email('applicant@example.com', '654321')
    assert result['success']
    assert len(email_outbox) == 1
    assert email_outbox[0]['to'] == [{'email': 'applicant@example.com'}]
    assert '654321' in email_outbox[0]['htmlContent']


def test_notification_recipients_use_only_configuration_and_deduplicate(monkeypatch):
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', f'{RECIPIENT.upper()}, extra@example.com;EXTRA@example.com\nthird@example.com')
    assert website_notifications.get_website_update_recipients() == [
        RECIPIENT.upper(), 'extra@example.com', 'third@example.com',
    ]
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', 'replacement@example.com')
    assert website_notifications.get_website_update_recipients() == ['replacement@example.com']


@pytest.mark.parametrize('configured', [None, '', ' , ; \n '])
def test_empty_notification_configuration_sends_no_mail(monkeypatch, email_outbox, configured):
    if configured is None:
        monkeypatch.delenv('WEBSITE_UPDATE_NOTIFY_EMAILS', raising=False)
    else:
        monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', configured)
    result = website_notifications.notify_website_update('Changes prepared', 'Prepared locally.')
    assert result == {'success': True, 'skipped': True, 'deliveries': {}}
    assert email_outbox == []


def test_multiple_configured_recipients_receive_one_email_each(monkeypatch, email_outbox):
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', f'{RECIPIENT},second@example.com,{RECIPIENT.upper()}')
    result = website_notifications.notify_website_update('Changes prepared', 'Prepared locally.')
    assert result['success']
    assert [message['to'] for message in email_outbox] == [
        [{'email': RECIPIENT}], [{'email': 'second@example.com'}],
    ]


def test_map_custom_database_recipients_include_configured_website_recipients(monkeypatch):
    query = Mock()
    query.filter.return_value.first.return_value = SimpleNamespace(value='custom@example.com')
    monkeypatch.setattr(map_routes, 'map_db_session', SimpleNamespace(query=lambda *args: query))
    monkeypatch.setenv('MAP_APPROVAL_NOTIFY_EMAILS', 'ignored@example.com')
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', RECIPIENT)
    assert map_routes._get_map_approval_notify_recipients() == ['custom@example.com', RECIPIENT]
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', '')
    assert map_routes._get_map_approval_notify_recipients() == ['custom@example.com']


def test_map_environment_recipients_deduplicate_and_can_be_removed(monkeypatch):
    query = Mock()
    query.filter.return_value.first.return_value = None
    monkeypatch.setattr(map_routes, 'map_db_session', SimpleNamespace(query=lambda *args: query))
    monkeypatch.setenv('MAP_APPROVAL_NOTIFY_EMAILS', f'reviewer@example.com,{RECIPIENT}')
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', RECIPIENT.upper())
    assert map_routes._get_map_approval_notify_recipients() == ['reviewer@example.com', RECIPIENT]
    monkeypatch.setenv('MAP_APPROVAL_NOTIFY_EMAILS', '')
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', '')
    assert map_routes._get_map_approval_notify_recipients() == []
    monkeypatch.delenv('MAP_APPROVAL_NOTIFY_EMAILS')
    monkeypatch.delenv('WEBSITE_UPDATE_NOTIFY_EMAILS')
    assert map_routes._get_map_approval_notify_recipients() == []


def test_map_recipient_editor_reports_environment_or_no_recipients(client, login, monkeypatch):
    monkeypatch.setenv('MAP_LEGACY_FEATURES_ENABLED', 'true')
    login()
    query = Mock()
    query.filter.return_value.first.return_value = None
    monkeypatch.setattr(map_routes, 'map_db_session', SimpleNamespace(query=lambda *args: query))
    monkeypatch.setenv('MAP_APPROVAL_NOTIFY_EMAILS', '')
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', RECIPIENT)
    response = client.get('/api/map/settings/approval-recipients')
    assert response.status_code == 200
    data = response.get_json()
    assert data['source'] == 'env'
    assert data['recipients'] == [RECIPIENT]
    assert data['database_recipients'] == []
    assert data['website_recipients'] == [RECIPIENT]
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', '')
    data = client.get('/api/map/settings/approval-recipients').get_json()
    assert data['source'] == 'none'
    assert data['recipients'] == []


def _school_request(client, monkeypatch):
    monkeypatch.setattr(interschool_routes, 'is_email_verified', lambda *args, **kwargs: True)
    monkeypatch.setenv('TURNSTILE_SECRET_KEY', '')
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', RECIPIENT)
    suffix = uuid.uuid4().hex[:8]
    payload = {
        'email': f'new-school-{suffix}@example.com',
        'school_name': f'Academy <script>{suffix}</script>',
        'admin_username': f'admin-{suffix}',
        'admin_password': 'never-email-this-password',
        'admin_display_name': 'New Administrator',
    }
    response = client.post('/api/auth/register-school', json=payload)
    return response, payload


def test_school_request_notifies_once_without_password(client, monkeypatch, email_outbox):
    response, payload = _school_request(client, monkeypatch)
    assert response.status_code == 201
    assert len(email_outbox) == 1
    message = email_outbox[0]
    assert message['to'] == [{'email': RECIPIENT}]
    assert 'New school registration request' in message['subject']
    assert payload['email'] in message['htmlContent']
    assert '&lt;script&gt;' in message['htmlContent']
    assert '<script>' not in message['htmlContent']
    assert payload['admin_password'] not in message['htmlContent']
    saved = db_session.query(SchoolRegistrationRequest).filter_by(email=payload['email']).one()
    assert saved.id in message['htmlContent']
    assert saved.admin_password_hash not in message['htmlContent']
    duplicate = client.post('/api/auth/register-school', json=payload)
    assert duplicate.status_code == 409
    assert len(email_outbox) == 1


def test_email_timeout_does_not_discard_school_request(client, monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.exceptions.Timeout()
    monkeypatch.setattr(email_delivery.http_requests, 'post', timeout)
    response, payload = _school_request(client, monkeypatch)
    assert response.status_code == 201
    saved = db_session.query(SchoolRegistrationRequest).filter_by(email=payload['email']).one()
    assert saved.status == 'pending'


def test_unexpected_notification_error_does_not_discard_school_request(client, monkeypatch):
    def failure(*args, **kwargs):
        raise RuntimeError('Notification failed unexpectedly')
    monkeypatch.setattr(interschool_routes, 'notify_school_registration', failure)
    response, payload = _school_request(client, monkeypatch)
    assert response.status_code == 201
    assert db_session.query(SchoolRegistrationRequest).filter_by(email=payload['email']).one().status == 'pending'
