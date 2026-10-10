import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import requests

from src.routes.golden_plate_recorder_db import interschool_routes, map_routes
from src.routes.golden_plate_recorder_db.email_service import send_verification_email
from src.routes.golden_plate_recorder_db.db import SchoolRegistrationRequest, db_session
from src.services import email_delivery, website_notifications
from scripts import notify_website_update, run_website

MATTHEW = 'matthew.jaekel@sac.on.ca'


def test_verification_code_is_sent_only_to_applicant(email_outbox):
    result = send_verification_email('applicant@example.com', '654321')
    assert result['success']
    assert len(email_outbox) == 1
    assert email_outbox[0]['to'] == [{'email': 'applicant@example.com'}]
    assert '654321' in email_outbox[0]['htmlContent']


def test_notification_recipients_keep_matthew_and_deduplicate(monkeypatch):
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', f'{MATTHEW.upper()}, extra@example.com;extra@example.com')
    assert website_notifications.get_website_update_recipients() == [MATTHEW, 'extra@example.com']


def test_map_custom_database_recipients_still_include_matthew(monkeypatch):
    query = Mock()
    query.filter.return_value.first.return_value = SimpleNamespace(value='custom@example.com')
    monkeypatch.setattr(map_routes, 'map_db_session', SimpleNamespace(query=lambda *args: query))
    monkeypatch.setenv('MAP_APPROVAL_NOTIFY_EMAILS', 'ignored@example.com')
    monkeypatch.delenv('WEBSITE_UPDATE_NOTIFY_EMAILS', raising=False)
    assert map_routes._get_map_approval_notify_recipients() == ['custom@example.com', MATTHEW]


def test_map_default_recipients_do_not_send_duplicate_to_matthew(monkeypatch):
    query = Mock()
    query.filter.return_value.first.return_value = None
    monkeypatch.setattr(map_routes, 'map_db_session', SimpleNamespace(query=lambda *args: query))
    monkeypatch.delenv('MAP_APPROVAL_NOTIFY_EMAILS', raising=False)
    monkeypatch.delenv('WEBSITE_UPDATE_NOTIFY_EMAILS', raising=False)
    recipients = map_routes._get_map_approval_notify_recipients()
    assert recipients.count(MATTHEW) == 1
    assert set(map_routes.DEFAULT_MAP_APPROVAL_NOTIFY_EMAILS) <= set(recipients)


def _school_request(client, monkeypatch):
    monkeypatch.setattr(interschool_routes, 'is_email_verified', lambda *args, **kwargs: True)
    monkeypatch.setenv('RECAPTCHA_SECRET_KEY', '')
    monkeypatch.delenv('WEBSITE_UPDATE_NOTIFY_EMAILS', raising=False)
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
    assert message['to'] == [{'email': MATTHEW}]
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
    monkeypatch.setattr(interschool_routes, 'notify_website_update', failure)
    response, payload = _school_request(client, monkeypatch)
    assert response.status_code == 201
    assert db_session.query(SchoolRegistrationRequest).filter_by(email=payload['email']).one().status == 'pending'


def test_code_change_email_is_marked_prepared_and_contains_summary(monkeypatch, email_outbox):
    monkeypatch.delenv('WEBSITE_UPDATE_NOTIFY_EMAILS', raising=False)
    monkeypatch.setattr(notify_website_update, 'code_details', lambda: [('Revision', 'abc123')])
    assert notify_website_update.main([
        '--kind', 'code-change', '--summary', 'Changes checked locally; not deployed.',
    ]) == 0
    message = email_outbox[0]
    assert 'prepared' in message['subject']
    assert 'not deployed' in message['htmlContent']
    assert 'abc123' in message['htmlContent']


def test_notification_cli_reports_failed_delivery(monkeypatch):
    monkeypatch.setattr(notify_website_update, 'send_update', lambda *args, **kwargs: {'success': False})
    assert notify_website_update.main(['--kind', 'code-change', '--summary', 'Prepared locally.']) == 1


def test_readiness_rejects_failed_server_and_accepts_http_success(monkeypatch):
    process = Mock()
    process.poll.return_value = 1
    get = Mock(return_value=SimpleNamespace(status_code=200))
    monkeypatch.setattr(run_website.requests, 'get', get)
    assert not run_website.wait_until_ready(process, 'http://127.0.0.1:1234/')
    get.assert_not_called()
    process.poll.return_value = None
    assert run_website.wait_until_ready(process, 'http://127.0.0.1:1234/')


def test_deployment_notifies_only_after_readiness(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    process.wait.return_value = 0
    socket = Mock()
    socket.__enter__ = Mock(return_value=socket)
    socket.__exit__ = Mock(return_value=False)
    socket.connect_ex.return_value = 1
    monkeypatch.setattr(run_website.socket, 'socket', lambda: socket)
    monkeypatch.setattr(run_website.subprocess, 'Popen', lambda *args, **kwargs: process)
    stop = Mock()
    monkeypatch.setattr(run_website, 'stop_server', stop)
    send = Mock(return_value={'success': True})
    monkeypatch.setattr(run_website, 'send_update', send)
    monkeypatch.setattr(run_website, 'wait_until_ready', lambda *args: False)
    assert run_website.main() == 1
    send.assert_not_called()
    stop.assert_called_once_with(process)
    monkeypatch.setattr(run_website, 'wait_until_ready', lambda *args: True)
    assert run_website.main() == 0
    assert send.call_args.args[0] == 'deployment'


def test_occupied_port_never_sends_deployment_email(monkeypatch):
    socket = Mock()
    socket.__enter__ = Mock(return_value=socket)
    socket.__exit__ = Mock(return_value=False)
    socket.connect_ex.return_value = 0
    monkeypatch.setattr(run_website.socket, 'socket', lambda: socket)
    send = Mock()
    monkeypatch.setattr(run_website, 'send_update', send)
    assert run_website.main() == 1
    send.assert_not_called()
