import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

from flask import Flask

from src.services import startup_notifications


def test_startup_sends_once_without_requests_and_again_for_a_new_process(monkeypatch, email_outbox):
    monkeypatch.setenv('WEBSITE_STARTUP_NOTIFY_ENABLED', 'true')
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', 'updates@example.com')
    app = Flask(__name__)
    worker = startup_notifications.start_startup_notification(app)
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert len(email_outbox) == 1
    assert 'Website server started' in email_outbox[0]['subject']
    assert startup_notifications.start_startup_notification(app) is None
    assert len(email_outbox) == 1
    monkeypatch.setattr(startup_notifications.os, 'getpid', lambda: -1)
    worker = startup_notifications.start_startup_notification(app)
    worker.join(timeout=2)
    assert len(email_outbox) == 2


def test_startup_skips_tests_disabled_settings_and_reloader_parent(monkeypatch, email_outbox):
    app = Flask(__name__)
    monkeypatch.setenv('WEBSITE_STARTUP_NOTIFY_ENABLED', 'false')
    assert startup_notifications.start_startup_notification(app) is None
    monkeypatch.setenv('WEBSITE_STARTUP_NOTIFY_ENABLED', 'true')
    assert startup_notifications.start_startup_notification(app, reloader_parent=True) is None
    app.testing = True
    assert startup_notifications.start_startup_notification(app) is None
    assert email_outbox == []


def test_startup_failure_does_not_break_application(monkeypatch):
    monkeypatch.setenv('WEBSITE_STARTUP_NOTIFY_ENABLED', 'true')
    send = Mock(side_effect=RuntimeError('Mail unavailable'))
    monkeypatch.setattr(startup_notifications, 'notify_website_update', send)
    worker = startup_notifications.start_startup_notification(Flask(__name__))
    worker.join(timeout=2)
    send.assert_called_once()
    assert not worker.is_alive()


def test_host_without_threads_still_announces_automatically(monkeypatch):
    monkeypatch.setenv('WEBSITE_STARTUP_NOTIFY_ENABLED', 'true')
    send = Mock(return_value={'success': True})
    monkeypatch.setattr(startup_notifications, 'notify_website_update', send)
    monkeypatch.setattr(startup_notifications.threading.Thread, 'start',
                        Mock(side_effect=RuntimeError('Threads disabled')))
    assert startup_notifications.start_startup_notification(Flask(__name__)) is None
    send.assert_called_once()


def test_wsgi_import_automatically_announces_without_a_script(tmp_path):
    """Run a fresh application import with mail mocked before initialization."""
    env = dict(os.environ, WEBSITE_STARTUP_NOTIFY_ENABLED='true', FLASK_DEBUG='0',
               DATABASE_URL=f'sqlite:///{tmp_path / "website.db"}',
               MAP_DATABASE_URL=f'sqlite:///{tmp_path / "map.db"}')
    code = '''
import threading
from unittest.mock import Mock
from src.services import startup_notifications
sent = threading.Event()
send = Mock(side_effect=lambda *args, **kwargs: sent.set())
startup_notifications.notify_website_update = send
from src.main import app
assert sent.wait(2), "Startup must announce without receiving any requests"
assert send.call_count == 1
app.test_client().get('/api/auth/status')
app.test_client().get('/api/auth/status')
assert send.call_count == 1, "Ordinary requests must not repeat announcements"
'''
    completed = subprocess.run([sys.executable, '-c', code], env=env,
                               cwd=Path(__file__).resolve().parent.parent,
                               capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
