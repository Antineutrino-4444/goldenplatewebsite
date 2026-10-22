"""Operator-only, standalone email diagnostics with a durable audit trail."""

from datetime import datetime, timezone
from contextlib import contextmanager
from html import escape
from pathlib import Path
import os
import re
import secrets
import sqlite3
import threading

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for

from .email_delivery import send_email_via_brevo
from .email_test_samples import build_email_samples

COOLDOWN_SECONDS = 300


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize_recipient(value):
    recipient = value.strip().lower()
    if len(recipient) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", recipient):
        raise ValueError('Enter one valid recipient email address.')
    return recipient


@contextmanager
def open_audit(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Audit records contain email addresses; create private files by default.
    descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    os.close(descriptor)
    store = sqlite3.connect(path, timeout=10)
    store.row_factory = sqlite3.Row
    try:
        store.executescript('''
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, recipient TEXT NOT NULL, started_at TEXT NOT NULL,
            finished_at TEXT, status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            run_id TEXT NOT NULL, position INTEGER NOT NULL, kind TEXT NOT NULL,
            label TEXT NOT NULL, status TEXT NOT NULL, attempted_at TEXT,
            sent_at TEXT, finished_at TEXT, message_id TEXT, error TEXT,
            PRIMARY KEY (run_id, position)
        );
        ''')
        with store:
            yield store
    finally:
        store.close()


def read_run(path, run_id):
    with open_audit(path) as store:
        row = store.execute('SELECT * FROM runs WHERE id = ?', (run_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result['messages'] = [dict(item) for item in store.execute(
            'SELECT * FROM messages WHERE run_id = ? ORDER BY position', (run_id,))]
        return result


def reserve_run(path, recipient, samples):
    """Commit the cooldown and planned messages before starting any delivery."""
    with open_audit(path) as store:
        store.execute('BEGIN IMMEDIATE')
        latest = store.execute('SELECT started_at, status FROM runs ORDER BY started_at DESC LIMIT 1').fetchone()
        now = datetime.now(timezone.utc)
        if latest and (latest['status'] == 'running' or
                       (now - datetime.fromisoformat(latest['started_at'])).total_seconds() < COOLDOWN_SECONDS):
            return None
        run_id = secrets.token_urlsafe(24)
        store.execute('INSERT INTO runs VALUES (?, ?, ?, NULL, ?)',
                      (run_id, recipient, now.isoformat(), 'running'))
        store.executemany('INSERT INTO messages (run_id, position, kind, label, status) VALUES (?, ?, ?, ?, ?)',
                          [(run_id, index, sample.key, sample.label, 'queued') for index, sample in enumerate(samples)])
    return run_id


def delivery_error(result):
    """Do not persist provider response bodies, exception contents or credentials."""
    error = result.get('error', '')
    if isinstance(error, str) and (
        error in {'Request to Brevo timed out', 'Unable to apply notification preferences'}
        or error.startswith('Brevo API key not configured.')
        or re.fullmatch(r'Brevo API error: \d{3}', error)
    ):
        return error
    return 'Email delivery failed. Check the server email configuration and provider logs.'


def recover_interrupted_runs(path, run_id=None):
    """Caller must own the process lock before recovering abandoned work."""
    condition, parameters = (' AND run_id = ?', (run_id,)) if run_id else ('', ())
    with open_audit(path) as store:
        store.execute("UPDATE messages SET status = 'unknown', error = 'Process interrupted; provider acceptance is unknown.' WHERE status = 'sending'" + condition, parameters)
        store.execute("UPDATE messages SET status = 'cancelled', error = 'Process interrupted before sending.' WHERE status = 'queued'" + condition, parameters)
        if run_id:
            store.execute("UPDATE runs SET status = 'interrupted', finished_at = ? WHERE id = ?", (utc_now(), run_id))
        else:
            store.execute("UPDATE runs SET status = 'interrupted', finished_at = ? WHERE status = 'running'", (utc_now(),))


def send_batch(path, run_id, samples, *, on_result=None):
    """Never retry an ambiguous send automatically; keep each result independent."""
    try:
        run = read_run(path, run_id)
        for index, sample in enumerate(samples):
            attempted_at = utc_now()
            with open_audit(path) as store:
                store.execute('UPDATE messages SET status = ?, attempted_at = ? WHERE run_id = ? AND position = ?',
                              ('sending', attempted_at, run_id, index))
            banner = (
                '<p style="padding:16px;background:#fff3cd;color:#513d00;font:16px Arial,sans-serif">'
                '<strong>EMAIL TEST — sample data only.</strong> No account, school or map action occurred. '
                'Verification text and action links are inactive.<br>'
                f'Test: {escape(sample.label)}<br>Send attempt (UTC): {attempted_at}</p>'
            )
            html = sample.html
            if re.search(r'<body\b[^>]*>', html, re.IGNORECASE):
                html = re.sub(r'(<body\b[^>]*>)', lambda match: match[0] + banner, html, count=1, flags=re.IGNORECASE)
            else:
                html = banner + html
            try:
                result = send_email_via_brevo(run['recipient'], '[TEST] ' + sample.subject, html,
                                              notification_type=sample.notification_type)
                status = 'skipped' if result.get('skipped') else 'accepted' if result.get('success') else 'failed'
                error = 'Recipient disabled this notification type.' if status == 'skipped' else delivery_error(result) if status == 'failed' else None
                message_id = str(result.get('message_id') or '')[:1024] or None
            except Exception:
                status, error, message_id = 'failed', 'Email delivery raised an unexpected error.', None
            finished_at = utc_now()
            with open_audit(path) as store:
                store.execute('''UPDATE messages SET status = ?, sent_at = ?, finished_at = ?,
                                 message_id = ?, error = ? WHERE run_id = ? AND position = ?''',
                              (status, finished_at if status == 'accepted' else None, finished_at,
                               message_id, error, run_id, index))
            if on_result:
                on_result(dict(position=index, label=sample.label, status=status,
                               attempted_at=attempted_at, finished_at=finished_at,
                               sent_at=finished_at if status == 'accepted' else None,
                               message_id=message_id, error=error))
        with open_audit(path) as store:
            failed = store.execute("SELECT COUNT(*) FROM messages WHERE run_id = ? AND status = 'failed'", (run_id,)).fetchone()[0]
            store.execute('UPDATE runs SET status = ?, finished_at = ? WHERE id = ?',
                          ('completed_with_errors' if failed else 'completed', utc_now(), run_id))
    except Exception:
        # A database failure must stop subsequent sends: never send unrecorded mail.
        # An in-flight row is unknown, rather than falsely reported as failed.
        import logging
        logging.getLogger(__name__).exception('Email test stopped; inspect the audit log before retrying')
        recover_interrupted_runs(path, run_id)
    finally:
        from src.routes.golden_plate_recorder_db.db import db_session
        from src.routes.golden_plate_recorder_db.map_db import map_db_session
        db_session.remove()
        map_db_session.remove()


def create_app(database, *, access_key):
    if not access_key:
        raise ValueError('An email test access key is required')
    database = Path(database).resolve()
    app = Flask(__name__, template_folder=str(Path(__file__).with_name('email_test_templates')))
    app.config.update(SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=8192,
                      SESSION_COOKIE_NAME='goldenplate_email_test', SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Strict')

    @app.template_filter('display_time')
    def display_time(value):
        return datetime.fromisoformat(value).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if value else '—'

    # This tool is a single process. Do not resend work interrupted by a restart.
    recover_interrupted_runs(database)

    @app.after_request
    def private_response(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    def form(error=None, status=200):
        session.setdefault('csrf', secrets.token_urlsafe(32))
        return render_template('form.html', error=error, csrf=session['csrf'],
                               site_key=os.environ.get('TURNSTILE_SITE_KEY') or os.environ.get('VITE_TURNSTILE_SITE_KEY', '')), status

    @app.route('/', methods=['GET', 'POST'])
    def index():
        if request.method == 'GET':
            return form()
        csrf = request.form.get('csrf', '')
        if not session.get('csrf') or not secrets.compare_digest(csrf.encode(), session['csrf'].encode()):
            return form('The form expired. Please try again.', 400)
        if not secrets.compare_digest(request.form.get('access_key', '').encode(), access_key.encode()):
            return form('The server access key is incorrect.', 403)
        try:
            recipient = normalize_recipient(request.form.get('email', ''))
        except ValueError as error:
            return form(str(error), 400)
        from src.routes.golden_plate_recorder_db.captcha import captcha_failure
        failure = captcha_failure(request.form.get('cf-turnstile-response'), 'email_test', required=True)
        if failure:
            return form(failure.message, failure.status)
        try:
            samples = build_email_samples()
            run_id = reserve_run(database, recipient, samples)
        except Exception:
            app.logger.exception('Unable to prepare the email test audit')
            return form('Could not prepare the send log. No test emails were sent.', 503)
        if run_id is None:
            return form('A test is running or was started in the last five minutes. Please try again later.', 429)
        session['run_ids'] = (session.get('run_ids', []) + [run_id])[-20:]
        worker = threading.Thread(target=send_batch, args=(database, run_id, samples), daemon=True)
        try:
            worker.start()
        except RuntimeError:
            with open_audit(database) as store:
                store.execute("UPDATE runs SET status = 'interrupted', finished_at = ? WHERE id = ?", (utc_now(), run_id))
                store.execute("UPDATE messages SET status = 'cancelled', error = 'Unable to start send worker.' WHERE run_id = ?", (run_id,))
        return redirect(url_for('results', run_id=run_id), code=303)

    def permitted_run(run_id):
        if run_id not in session.get('run_ids', []):
            abort(404)
        run = read_run(database, run_id)
        if run is None:
            abort(404)
        return run

    @app.get('/runs/<run_id>')
    def results(run_id):
        return render_template('results.html', run=permitted_run(run_id))

    @app.get('/runs/<run_id>/status')
    def status(run_id):
        return jsonify(permitted_run(run_id))

    return app
