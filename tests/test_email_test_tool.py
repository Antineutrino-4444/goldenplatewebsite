from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.services import email_test_tool as tool
from src.services.email_test_samples import build_email_samples
from src.services.notification_preferences import NOTIFICATION_TYPES
from src.routes.golden_plate_recorder_db import captcha
from src.routes.golden_plate_recorder_db.db import EmailNotificationPreference, db_session


@pytest.fixture
def email_tool(tmp_path, monkeypatch):
    database = tmp_path / 'audit.sqlite3'
    app = tool.create_app(database, access_key='server-test-key')
    app.testing = True
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('TURNSTILE_SECRET_KEY', 'real-shaped-secret')
    monkeypatch.setenv('TURNSTILE_SITE_KEY', 'public-site-key')
    monkeypatch.setenv('TURNSTILE_ALLOWED_HOSTNAMES', 'goldenplate.ca')
    monkeypatch.setattr(captcha, 'requests', SimpleNamespace(
        post=lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: dict(success=True, action='email_test', hostname='goldenplate.ca',
                              challenge_ts=datetime.now(timezone.utc).isoformat())),
        RequestException=RuntimeError,
    ))

    class InlineWorker:
        def __init__(self, target, args, **kwargs):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(tool.threading, 'Thread', InlineWorker)
    return app.test_client(), database


def submit(client, **overrides):
    client.get('/')
    with client.session_transaction() as session:
        csrf = session['csrf']
    return client.post('/', data=dict(email='Recipient@Example.com', access_key='server-test-key',
                                      csrf=csrf, **{'cf-turnstile-response': 'verified-token'}) | overrides)


def latest(database):
    with tool.open_audit(database) as store:
        row = store.execute('SELECT id FROM runs ORDER BY started_at DESC LIMIT 1').fetchone()
    return tool.read_run(database, row['id']) if row else None


def test_all_current_email_categories_use_samples_without_live_actions(monkeypatch):
    from src.routes.golden_plate_recorder_db import map_routes
    monkeypatch.setattr(map_routes, '_collect_submission_image_attachments', lambda *args: pytest.fail('Read live submission data'))
    samples = build_email_samples()
    assert len(samples) == 21
    assert len({sample.key for sample in samples}) == 21
    assert {sample.notification_type for sample in samples} == set(NOTIFICATION_TYPES) | {None}
    assert sum('SAMPLE' in sample.html for sample in samples) >= 4
    assert all('example.invalid' in sample.html for sample in samples if sample.key in {
        'password_recovery', 'map_submission', 'lifecycle_deleted'})


def test_sends_only_to_entered_recipient_and_persists_each_timestamp(email_tool, monkeypatch, email_outbox):
    client, database = email_tool
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', 'website-alerts@example.com')
    monkeypatch.setenv('MAP_APPROVAL_NOTIFY_EMAILS', 'reviewers@example.com')
    response = submit(client)
    assert response.status_code == 303
    assert len(email_outbox) == 21
    assert all(message['to'] == [{'email': 'recipient@example.com'}] for message in email_outbox)
    assert all(message['subject'].startswith('[TEST] ') for message in email_outbox)
    assert all('EMAIL TEST' in message['htmlContent'] for message in email_outbox)
    run = latest(database)
    assert run['status'] == 'completed'
    assert len(run['messages']) == 21
    for message in run['messages']:
        assert message['status'] == 'accepted'
        assert datetime.fromisoformat(message['sent_at']) >= datetime.fromisoformat(message['attempted_at'])
        assert datetime.fromisoformat(message['sent_at']).tzinfo is not None
        assert message['message_id'] == 'test-message'
    assert client.get(response.location).status_code == 200
    status = client.get(response.location + '/status')
    assert status.json == run
    assert status.headers['Cache-Control'] == 'no-store'
    assert tool.create_app(database, access_key='new-key')
    assert tool.read_run(database, run['id']) == run
    assert len(email_outbox) == 21


@pytest.mark.parametrize('fields,code', [
    ({'csrf': 'invalid'}, 400), ({'access_key': 'incorrect'}, 403),
    ({'email': 'one@example.com,two@example.com'}, 400),
    ({'email': 'one@example.com\r\nBcc: two@example.com'}, 400),
    ({'cf-turnstile-response': ''}, 400),
])
def test_invalid_requests_do_not_send_or_reserve_a_batch(email_tool, email_outbox, fields, code):
    client, database = email_tool
    assert submit(client, **fields).status_code == code
    assert latest(database) is None
    assert not email_outbox


@pytest.mark.parametrize('secret', ['', '1x0000000000000000000000000000000AA'])
def test_captcha_cannot_be_bypassed_in_development(email_tool, monkeypatch, email_outbox, secret):
    client, database = email_tool
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('TURNSTILE_SECRET_KEY', secret)
    assert submit(client).status_code == 503
    assert latest(database) is None
    assert not email_outbox


@pytest.mark.parametrize('change', [{'action': 'account_signup'}, {'hostname': 'attacker.example'}, {'success': False}])
def test_rejects_wrong_captcha_action_or_hostname(email_tool, monkeypatch, email_outbox, change):
    client, database = email_tool
    monkeypatch.setattr(captcha.requests, 'post', lambda *a, **kw: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: dict(success=True, action='email_test',
            hostname='goldenplate.ca', challenge_ts=datetime.now(timezone.utc).isoformat()) | change))
    assert submit(client).status_code == 400
    assert not email_outbox and latest(database) is None


def test_delivery_failures_are_recorded_and_remaining_emails_continue(email_tool, monkeypatch, email_outbox):
    client, database = email_tool
    real_sender = tool.send_email_via_brevo
    calls = 0

    def send(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            return {'success': False, 'error': 'Brevo API error: 429', 'detail': {'secret': 'never-store-this'}}
        if calls == 3:
            raise RuntimeError('never-store-this-either')
        return real_sender(*args, **kwargs)

    monkeypatch.setattr(tool, 'send_email_via_brevo', send)
    assert submit(client).status_code == 303
    run = latest(database)
    assert calls == 21 and len(email_outbox) == 19
    assert run['status'] == 'completed_with_errors'
    failed = [row for row in run['messages'] if row['status'] == 'failed']
    assert len(failed) == 2
    assert all(row['attempted_at'] and row['sent_at'] is None for row in failed)
    assert 'never-store-this' not in str(run)


def test_respects_disabled_notification_types(email_tool, email_outbox):
    client, database = email_tool
    db_session.add(EmailNotificationPreference(email='recipient@example.com', disabled_types='["server_startup"]'))
    db_session.commit()
    assert submit(client).status_code == 303
    run = latest(database)
    message = next(row for row in run['messages'] if row['kind'] == 'server_startup')
    assert message['status'] == 'skipped' and message['sent_at'] is None
    assert len(email_outbox) == 20
    assert db_session.get(EmailNotificationPreference, 'recipient@example.com').disabled_types == '["server_startup"]'


def test_completed_batch_can_be_repeated_immediately_after_restart(email_tool, email_outbox):
    client, database = email_tool
    assert submit(client).status_code == 303
    other = tool.create_app(database, access_key='server-test-key').test_client()
    assert submit(other, email='another@example.com').status_code == 303
    assert len(email_outbox) == 42


def test_other_browser_cannot_read_results(email_tool):
    client, database = email_tool
    response = submit(client)
    other = client.application.test_client()
    assert other.get(response.location).status_code == 404
    assert other.get(response.location + '/status').status_code == 404


def test_concurrent_requests_reserve_only_one_batch(tmp_path):
    database = tmp_path / 'audit.sqlite3'
    with tool.open_audit(database):
        pass
    samples = build_email_samples()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda email: tool.reserve_run(database, email, samples),
                                ['first@example.com', 'second@example.com']))
    assert sum(value is not None for value in results) == 1


def test_restart_records_ambiguous_sends_without_retrying(tmp_path, email_outbox):
    database = tmp_path / 'audit.sqlite3'
    run_id = tool.reserve_run(database, 'recipient@example.com', build_email_samples())
    with tool.open_audit(database) as store:
        store.execute("UPDATE messages SET status = 'sending', attempted_at = ? WHERE position = 0", (tool.utc_now(),))
    tool.create_app(database, access_key='server-test-key')
    run = tool.read_run(database, run_id)
    assert run['status'] == 'interrupted'
    assert run['messages'][0]['status'] == 'unknown'
    assert run['messages'][0]['sent_at'] is None
    assert all(row['status'] == 'cancelled' for row in run['messages'][1:])
    assert not email_outbox


def test_audit_preparation_failure_never_sends(email_tool, monkeypatch, email_outbox):
    client, _ = email_tool
    monkeypatch.setattr(tool, 'reserve_run', lambda *args: (_ for _ in ()).throw(OSError('disk full')))
    assert submit(client).status_code == 503
    assert not email_outbox


def test_script_mounts_under_https_proxy_without_starting_the_website(tmp_path, monkeypatch, capsys):
    import dotenv
    import sys
    from scripts import test_emails

    database = tmp_path / 'audit.sqlite3'
    app = tool.create_app(database, access_key='fixed-test-key')
    calls = []
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *args: None)
    monkeypatch.setattr(tool, 'create_app', lambda *args, **kwargs: app)
    monkeypatch.setattr(app, 'run', lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(sys, 'argv', ['test_emails.py', '--web', '--database', str(database),
                                     '--url-prefix', '/email-test', '--secure-cookie'])
    assert test_emails.main() == 0
    assert calls == [dict(host='127.0.0.1', port=59238, debug=False, use_reloader=False)]
    client = app.test_client()
    assert client.get('/').status_code == 404
    response = client.get('/email-test/', base_url='https://goldenplate.ca')
    assert response.status_code == 200
    assert b'Send all test emails' in response.data
    assert 'Secure' in response.headers['Set-Cookie']
    assert 'Path=/email-test' in response.headers['Set-Cookie']


def test_history_prints_saved_results_without_delivery(tmp_path, monkeypatch, capsys, email_outbox):
    import dotenv
    import json
    import sys
    from scripts import test_emails

    database = tmp_path / 'audit.sqlite3'
    run_id = tool.reserve_run(database, 'recipient@example.com', build_email_samples())
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *args: None)
    monkeypatch.setattr(sys, 'argv', ['test_emails.py', '--history', '--database', str(database)])
    assert test_emails.main() == 0
    saved = json.loads(capsys.readouterr().out)
    assert saved[0]['id'] == run_id and len(saved[0]['messages']) == 21
    assert not email_outbox


@pytest.mark.parametrize('kind', ['rejection', 'deletion'])
def test_real_map_decision_emails_preserve_attachment_delivery(kind, monkeypatch, email_outbox):
    from src.routes.golden_plate_recorder_db import map_routes

    submission = SimpleNamespace(title='<Sample title>', text_content='<Sample description>',
                                 submitted_at=datetime.now(timezone.utc))
    attachments = [{'name': 'sample.png', 'content': 'c2FtcGxl'}]
    monkeypatch.setattr(map_routes, '_collect_submission_image_attachments', lambda row: (attachments, []))
    result = getattr(map_routes, '_send_' + kind + '_email')(
        to_email='submitter@example.com', submission=submission,
        reason='<Sample reason>', reviewer_display_name='<Sample reviewer>')
    assert result['success']
    assert email_outbox[-1]['attachment'] == attachments
    assert email_outbox[-1]['to'] == [{'email': 'submitter@example.com'}]
    assert '&lt;Sample reason&gt;' in email_outbox[-1]['htmlContent']
    assert '&lt;Sample description&gt;' in email_outbox[-1]['htmlContent']


@pytest.fixture
def terminal_tool(tmp_path, monkeypatch):
    import dotenv
    import sys
    from scripts import test_emails

    database = tmp_path / 'audit.sqlite3'
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *args: None)
    monkeypatch.setattr(sys, 'argv', ['test_emails.py', '--database', str(database)])
    monkeypatch.setattr(tool, 'create_app', lambda *args, **kwargs: pytest.fail('Terminal mode started a web server'))
    monkeypatch.setattr(captcha, 'captcha_failure', lambda *args, **kwargs: pytest.fail('Terminal mode requires browser CAPTCHA'))
    return test_emails, database


def answer_prompts(monkeypatch, *answers):
    responses = iter(answers)
    monkeypatch.setattr('builtins.input', lambda prompt: next(responses))


def test_default_terminal_mode_sends_to_prompted_recipient_without_browser(terminal_tool, monkeypatch, capsys, email_outbox):
    script, database = terminal_tool
    answer_prompts(monkeypatch, 'Reader@Example.com', 'SEND reader@example.com')
    assert script.main() == 0
    assert len(email_outbox) == 21
    assert all(message['to'] == [{'email': 'reader@example.com'}] for message in email_outbox)
    run = latest(database)
    assert run['status'] == 'completed'
    assert all(message['sent_at'] for message in run['messages'])
    output = capsys.readouterr().out
    assert '[1/21]' in output and '[21/21]' in output
    assert '21 accepted, 0 skipped, 0 failed' in output
    assert run['messages'][0]['sent_at'] in output


def test_terminal_email_argument_still_requires_confirmation(terminal_tool, monkeypatch, email_outbox):
    import sys
    script, database = terminal_tool
    monkeypatch.setattr(sys, 'argv', ['test_emails.py', '--database', str(database), '--email', 'reader@example.com'])
    answer_prompts(monkeypatch, 'no')
    assert script.main() == 1
    assert not email_outbox and latest(database) is None


def test_terminal_email_argument_sends_after_confirmation(terminal_tool, monkeypatch, email_outbox):
    import sys
    script, database = terminal_tool
    monkeypatch.setattr(sys, 'argv', ['test_emails.py', '--database', str(database), '--email', 'reader@example.com'])
    answer_prompts(monkeypatch, 'SEND reader@example.com')
    assert script.main() == 0
    assert len(email_outbox) == 21


@pytest.mark.parametrize('recipient', ['one@example.com,two@example.com', 'invalid', 'reader@example.com\nBcc: other@example.com'])
def test_terminal_rejects_invalid_recipient_before_any_send(terminal_tool, monkeypatch, email_outbox, recipient):
    script, database = terminal_tool
    answer_prompts(monkeypatch, recipient)
    assert script.main() == 2
    assert not email_outbox and latest(database) is None


def test_terminal_failure_preserves_results_and_returns_nonzero(terminal_tool, monkeypatch, capsys, email_outbox):
    script, database = terminal_tool
    real_send = tool.send_email_via_brevo
    attempts = 0

    def send(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            return {'success': False, 'error': 'Brevo API error: 503'}
        return real_send(*args, **kwargs)

    monkeypatch.setattr(tool, 'send_email_via_brevo', send)
    answer_prompts(monkeypatch, 'reader@example.com', 'SEND reader@example.com')
    assert script.main() == 1
    assert attempts == 21 and len(email_outbox) == 20
    run = latest(database)
    assert run['status'] == 'completed_with_errors'
    assert run['messages'][1]['status'] == 'failed' and run['messages'][1]['sent_at'] is None
    assert '20 accepted, 0 skipped, 1 failed' in capsys.readouterr().out


def test_terminal_can_run_again_immediately(terminal_tool, monkeypatch, email_outbox):
    script, _ = terminal_tool
    for _ in range(2):
        answer_prompts(monkeypatch, 'reader@example.com', 'SEND reader@example.com')
        assert script.main() == 0
    assert len(email_outbox) == 42


@pytest.mark.parametrize('status', ['completed', 'completed_with_errors', 'interrupted'])
def test_finished_batches_never_delay_a_new_reservation(tmp_path, status):
    database = tmp_path / 'audit.sqlite3'
    samples = build_email_samples()
    first = tool.reserve_run(database, 'reader@example.com', samples)
    with tool.open_audit(database) as store:
        store.execute('UPDATE runs SET status = ? WHERE id = ?', (status, first))
    assert tool.reserve_run(database, 'reader@example.com', samples) is not None


def test_terminal_interrupt_preserves_accepted_and_unknown_results(terminal_tool, monkeypatch, email_outbox):
    script, database = terminal_tool
    real_send = tool.send_email_via_brevo
    attempts = 0

    def send(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise KeyboardInterrupt
        return real_send(*args, **kwargs)

    monkeypatch.setattr(tool, 'send_email_via_brevo', send)
    answer_prompts(monkeypatch, 'reader@example.com', 'SEND reader@example.com')
    assert script.main() == 130
    run = latest(database)
    assert len(email_outbox) == 1
    assert run['status'] == 'interrupted'
    assert run['messages'][0]['status'] == 'accepted' and run['messages'][0]['sent_at']
    assert run['messages'][1]['status'] == 'unknown' and run['messages'][1]['sent_at'] is None
    assert all(row['status'] == 'cancelled' for row in run['messages'][2:])


@pytest.mark.parametrize('interruption', [EOFError, KeyboardInterrupt])
def test_terminal_closed_input_cancels_without_send(terminal_tool, monkeypatch, email_outbox, interruption):
    script, database = terminal_tool
    monkeypatch.setattr('builtins.input', lambda prompt: (_ for _ in ()).throw(interruption()))
    assert script.main() == 1
    assert not email_outbox and latest(database) is None


def test_terminal_respects_notification_preferences(terminal_tool, monkeypatch, email_outbox):
    script, database = terminal_tool
    db_session.add(EmailNotificationPreference(email='reader@example.com', disabled_types='["server_startup"]'))
    db_session.commit()
    answer_prompts(monkeypatch, 'reader@example.com', 'SEND reader@example.com')
    assert script.main() == 0
    assert len(email_outbox) == 20
    skipped = next(row for row in latest(database)['messages'] if row['kind'] == 'server_startup')
    assert skipped['status'] == 'skipped' and skipped['sent_at'] is None
