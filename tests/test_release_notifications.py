import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.routes.golden_plate_recorder_db.db import Base, ReleaseEmailBatch, ReleaseEmailDelivery, School, User
from src.services import release_notes, release_notifications


@pytest.fixture
def releases(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "releases.db"}')
    Base.metadata.create_all(engine, tables=[
        School.__table__, User.__table__, ReleaseEmailBatch.__table__, ReleaseEmailDelivery.__table__,
    ])
    store = sessionmaker(bind=engine)
    monkeypatch.setattr(release_notifications, 'SessionFactory', store)
    notes = tmp_path / 'RELEASE_NOTES.md'
    monkeypatch.setattr(release_notes, 'RELEASE_NOTES_PATH', notes)
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', ' shared@Example.com, env@example.com;ENV@example.com ')
    monkeypatch.setenv('WEBSITE_PUBLIC_URL', 'https://goldenplate.example/')
    notes.write_text('## 1.2.1.1\n\n- Previously published\n')
    yield store, notes
    engine.dispose()


def test_release_digests_deduplicate_roles_and_environment_and_link_to_first_omitted(releases, email_outbox):
    store, notes = releases
    with store.begin() as session:
        for username, role, email in (
            ('lead', 'superadmin', 'SHARED@example.com'),
            ('assistant', 'admin', 'shared@example.com'),
            ('other', 'admin', 'admin@example.com'),
            ('regular', 'user', 'regular@example.com'),
            ('missing', 'superadmin', None),
        ):
            session.add(User(username=username, display_name=username, role=role, email=email, password_hash='unused'))

    release_notifications.notify_new_releases()
    assert email_outbox == []
    with notes.open('a') as file:
        for part in [2, 4, 3, 10]:
            file.write(f'\n## 1.2.1.{part}\n\n- New change {part} <test>\n')

    release_notifications.notify_new_releases()
    release_notifications.notify_new_releases()
    assert sorted(message['to'][0]['email'] for message in email_outbox) == [
        'admin@example.com', 'env@example.com', 'shared@example.com',
    ]
    for message in email_outbox:
        assert message['subject'] == 'Golden Plate — Version 1.2.1.10'
        html = message['htmlContent']
        assert html.index('New change 10') < html.index('New change 4') < html.index('New change 3')
        assert '<li>New change 10 &lt;test&gt;</li>' in html
        assert 'New change 2' not in html and 'Previously published' not in html
        assert 'https://goldenplate.example/release-notes#version-1.2.1.2">Check out more</a>' in html

    with notes.open('a') as file:
        file.write('\n## 1.2.1.11\n\n- Latest only\n')
    release_notifications.notify_new_releases()
    assert len(email_outbox) == 6
    assert all('Latest only' in mail['htmlContent'] and 'Check out more' not in mail['htmlContent']
               and 'New change 10' not in mail['htmlContent'] for mail in email_outbox[3:])


def test_concurrent_workers_queue_and_send_once(releases, monkeypatch):
    _, notes = releases
    notes.write_text('## 1.2.1.2\n\n- New release\n')
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', 'updates@example.com')
    send = Mock(return_value={'success': True})
    monkeypatch.setattr(release_notifications, 'send_release_email', send)
    ready = Barrier(4)

    def initialize():
        ready.wait(timeout=5)
        release_notifications.notify_new_releases()

    with ThreadPoolExecutor(max_workers=4) as workers:
        for attempt in [workers.submit(initialize) for _ in range(4)]:
            attempt.result(timeout=10)
    send.assert_called_once_with('updates@example.com', [('1.2.1.2', '- New release')])


def test_failed_delivery_can_retry_without_resending_successes(releases, monkeypatch, caplog):
    _, notes = releases
    notes.write_text('## 1.2.1.2\n\n- New release\n')
    send = Mock(side_effect=lambda email, _: {'success': email == 'shared@example.com', 'error': 'Offline'})
    monkeypatch.setattr(release_notifications, 'send_release_email', send)
    release_notifications.notify_new_releases()
    assert 'to env@example.com failed: Offline' in caplog.text
    send.reset_mock(side_effect=True)
    send.return_value = {'success': True}

    release_notifications.notify_new_releases()
    release_notifications.notify_new_releases()
    send.assert_called_once_with('env@example.com', [('1.2.1.2', '- New release')])


def test_worker_respects_initialization_guards_and_falls_back_without_threads(monkeypatch):
    app = Flask(__name__)
    notify = Mock()
    monkeypatch.setattr(release_notifications, 'notify_new_releases', notify)
    monkeypatch.setenv('WEBSITE_RELEASE_NOTIFY_ENABLED', 'false')
    assert release_notifications.start_release_notifications(app) is None
    monkeypatch.setenv('WEBSITE_RELEASE_NOTIFY_ENABLED', 'true')
    assert release_notifications.start_release_notifications(app, reloader_parent=True) is None
    app.testing = True
    assert release_notifications.start_release_notifications(app) is None
    notify.assert_not_called()

    app.testing = False
    monkeypatch.setattr(release_notifications.threading.Thread, 'start', Mock(side_effect=RuntimeError))
    assert release_notifications.start_release_notifications(app) is None
    assert release_notifications.start_release_notifications(app) is None
    notify.assert_called_once()


def test_wsgi_import_checks_releases_without_requests_or_a_script(tmp_path):
    env = dict(os.environ, WEBSITE_RELEASE_NOTIFY_ENABLED='true', FLASK_DEBUG='0',
               WEBSITE_UPDATE_NOTIFY_EMAILS='updates@example.com',
               DATABASE_URL=f'sqlite:///{tmp_path / "website.db"}',
               MAP_DATABASE_URL=f'sqlite:///{tmp_path / "map.db"}')
    notes = tmp_path / 'RELEASE_NOTES.md'
    notes.write_text('## 1.2.1.2\n\n- WSGI release\n')
    code = f"""
import threading
from pathlib import Path
from unittest.mock import Mock
from src.services import release_notes, release_notifications
release_notes.RELEASE_NOTES_PATH = Path({str(notes)!r})
sent = threading.Event()
def deliver(*args):
    sent.set()
    return {{'success': True}}
release_notifications.send_release_email = Mock(side_effect=deliver)
from src.main import app
assert sent.wait(5), 'Release email must send without receiving any requests'
app.test_client().get('/api/auth/status')
assert release_notifications.send_release_email.call_count == 1
"""
    completed = subprocess.run([sys.executable, '-c', code], env=env,
                               cwd=Path(__file__).resolve().parent.parent,
                               capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
