import csv
import io
import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from http.client import responses
from pathlib import Path
from secrets import token_hex
from time import perf_counter
from traceback import walk_tb

from flask import current_app, g, has_request_context, request, session


SERVER_LOG_RETENTION = timedelta(days=30)
LIVE_LOG_LIMIT = 200
_LOG_COLUMNS = ('id', 'occurred_at', 'actor', 'actor_id', 'school', 'method', 'route',
                'status', 'elapsed_ms', 'code', 'reference', 'detail')
_LOG_SELECT = ', '.join(_LOG_COLUMNS)


def _is_api_request():
    return has_request_context() and (request.path == '/api' or request.path.startswith('/api/'))


def _request_actor():
    school = str(session.get('audit_school_slug') or session.get('school_id') or '')
    if session.get('user_uuid') and session.get('password_token'):
        return str(session.get('username') or session.get('user_id') or 'Account')[:128], str(session['user_uuid']), school
    if session.get('guest_access'):
        if not session.get('audit_guest_id'):
            session['audit_guest_id'] = token_hex(6).upper()
        return 'Guest', session['audit_guest_id'], school
    return 'Anonymous', '', ''


def start_api_request():
    if _is_api_request():
        g.api_started_at = perf_counter()
        g.api_initial_actor = _request_actor()


def note_api_exception(error):
    """Keep a diagnostic summary without exception text or request data."""
    if not _is_api_request():
        return
    original = getattr(error, 'orig', error)
    reason = getattr(original, 'sqlite_errorname', None) or getattr(original, 'sqlstate', None)
    if not isinstance(reason, str) or not re.fullmatch(r'[A-Z0-9_]+', reason):
        reason = type(original).__name__
    locations = [(frame.f_globals.get('__name__', ''), line) for frame, line in walk_tb(error.__traceback__)]
    source = next((f'{module.rsplit(".", 1)[-1]}.py:{line}'
                   for module, line in reversed(locations) if module.startswith('src.')), '')
    g.api_error_detail = ' · '.join(filter(None, (reason, source)))


def _initialize_log(db):
    if db.execute('PRAGMA user_version').fetchone()[0] != 0:
        return
    db.execute('PRAGMA journal_mode=WAL').fetchone()
    with db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('PRAGMA user_version').fetchone()[0] != 0:
            return
        db.execute('''CREATE TABLE server_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT '', actor_id TEXT NOT NULL DEFAULT '', school TEXT NOT NULL DEFAULT '',
            method TEXT NOT NULL, route TEXT NOT NULL, status INTEGER NOT NULL, elapsed_ms INTEGER,
            code TEXT NOT NULL, reference TEXT NOT NULL, detail TEXT NOT NULL
        )''')
        db.execute('CREATE INDEX server_activity_date ON server_activity (occurred_at)')
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='api_errors'").fetchone():
            db.execute('''INSERT INTO server_activity (occurred_at, method, route, status, code, reference, detail)
                SELECT occurred_at, method, route, status, code, reference, detail FROM api_errors
                WHERE occurred_at >= ? ORDER BY id''',
                       ((datetime.now(timezone.utc) - SERVER_LOG_RETENTION).isoformat(),))
        db.execute('PRAGMA user_version = 1')


@contextmanager
def _error_log():
    path = Path(current_app.config['API_ERROR_LOG_PATH'])
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=1)) as db:
        db.row_factory = sqlite3.Row
        _initialize_log(db)
        yield db


def recent_api_errors():
    """The previous error-only endpoint keeps its original response fields."""
    with _error_log() as db:
        rows = db.execute('''SELECT occurred_at, reference, code, method, route, status, detail
            FROM server_activity WHERE status >= 500 AND occurred_at >= ?
            ORDER BY id DESC LIMIT 500''', (_retention_start(),))
        return [dict(row) for row in rows]


def _retention_start():
    return (datetime.now(timezone.utc) - SERVER_LOG_RETENTION).isoformat()


def _activity_filter(search, failures):
    conditions = ['occurred_at >= ?']
    parameters = [_retention_start()]
    if failures:
        conditions.append('status >= 400')
    if search:
        conditions.append("""instr(lower(actor || ' ' || actor_id || ' ' || school || ' ' || method || ' ' ||
            route || ' ' || status || ' ' || code || ' ' || reference || ' ' || detail), ?) > 0""")
        parameters.append(search.lower())
    return ' AND '.join(conditions), parameters


def recent_server_activity(search, failures, after):
    where, values = _activity_filter(search, failures)
    with _error_log() as db:
        newest = db.execute('SELECT COALESCE(MAX(id), 0) FROM server_activity').fetchone()[0]
        # A restored or replaced log can start numbering below an open viewer's cursor.
        reset = after > newest
        rows = db.execute(f'''SELECT {_LOG_SELECT} FROM server_activity
            WHERE id > ? AND id <= ? AND {where} ORDER BY id DESC LIMIT ?''',
                          (0 if reset else after, newest, *values, LIVE_LOG_LIMIT))
        return {'entries': [dict(row) for row in reversed(rows.fetchall())], 'cursor': newest,
                'limit': LIVE_LOG_LIMIT, 'reset': reset}


def _csv_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def export_server_activity(search, failures):
    where, values = _activity_filter(search, failures)
    with _error_log() as db:
        last = db.execute('SELECT COALESCE(MAX(id), 0) FROM server_activity').fetchone()[0]
    return _stream_activity_csv(last, where, values)


def _stream_activity_csv(last, where, values):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_LOG_COLUMNS)
    yield buffer.getvalue()
    while last > 0:
        with _error_log() as db:
            rows = db.execute(f'''SELECT {_LOG_SELECT} FROM server_activity
                WHERE id <= ? AND {where} ORDER BY id DESC LIMIT 500''', (last, *values)).fetchall()
        if not rows:
            break
        buffer.seek(0)
        buffer.truncate()
        writer.writerows([_csv_cell(value) for value in row] for row in rows)
        last = rows[-1]['id'] - 1
        yield buffer.getvalue()


def _save_activity(status, code='', reference=''):
    # Opening/exporting the log is an action. The viewer's automatic polls are housekeeping.
    if (request.endpoint == 'recorder.get_server_log' and request.args.get('poll') == '1'
            and request.args.get('format') != 'csv' and status == 200):
        return
    route = request.url_rule.rule if request.url_rule and request.endpoint != 'serve' else 'Unmatched API route'
    if request.endpoint == 'recorder.record_student':
        category = request.view_args.get('category')
        if category in {'clean', 'dirty', 'red', 'faculty'}:
            route = f'/api/record/{category}'
    detail = getattr(g, 'api_error_detail', '')
    actor, actor_id, school = _request_actor()
    if not actor_id and status < 400 and request.endpoint in {
        'recorder.logout', 'recorder.guest_logout',
        'recorder.authorize_deletion', 'recorder.final_deletion_confirmation',
    }:
        actor, actor_id, school = getattr(g, 'api_initial_actor', (actor, actor_id, school))
    now = datetime.now(timezone.utc)
    elapsed = round((perf_counter() - g.api_started_at) * 1000) if hasattr(g, 'api_started_at') else None
    if reference:
        current_app.logger.error('API error %s ref=%s (%s %s %s) %s',
                                 code, reference, request.method, route, status, detail)
    try:
        with _error_log() as db, db:
            db.execute('''INSERT INTO server_activity (occurred_at, actor, actor_id, school, method, route,
                status, elapsed_ms, code, reference, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (now.isoformat(), actor, actor_id, school, request.method, route,
                        status, elapsed, code, reference, detail))
            db.execute('DELETE FROM server_activity WHERE occurred_at < ?',
                       ((now - SERVER_LOG_RETENTION).isoformat(),))
    except (OSError, sqlite3.Error):
        current_app.logger.exception('Could not store API activity for %s %s', request.method, route)


def log_api_response(response):
    """Audit completed API requests and add a public code to failed responses."""
    if not _is_api_request():
        return response
    status = response.status_code
    if status < 400:
        _save_activity(status)
        return response

    data = response.get_json(silent=True) if response.is_json else None
    if not isinstance(data, dict):
        data = {}

    endpoint = request.endpoint
    operation = endpoint.rsplit('.', 1)[-1].upper() if endpoint and endpoint != 'serve' else 'API'
    code = data.get('error_code') or data.get('code')
    if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,95}', code):
        code = f'{operation}_{status}'
    data['error_code'] = code
    if not data.get('error'):
        data['error'] = data.get('message') or f'{responses.get(status, "Request failed")}.'
    reference = token_hex(6).upper() if status >= 500 else ''
    if reference:
        data['error_reference'] = reference
        response.headers['Cache-Control'] = 'no-store'
    _save_activity(status, code, reference)
    response.set_data(current_app.json.dumps(data))
    response.mimetype = 'application/json'
    return response
