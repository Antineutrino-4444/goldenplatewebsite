"""Start the CAPTCHA-protected email test tool on the web server.

Usage: python scripts/test_emails.py [--port 59238] [--history]
See docs/email-test-tool.md for browser access and Turnstile configuration.
"""
from pathlib import Path
import argparse
import json
import os
import re
import secrets
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=59238)
    parser.add_argument('--history', action='store_true', help='Print the latest 50 saved runs; send nothing')
    parser.add_argument('--database', type=Path, default=PROJECT_ROOT / 'data' / 'email_test_runs.sqlite3')
    parser.add_argument('--url-prefix', default='', help='Optional reverse-proxy mount path, e.g. /email-test')
    parser.add_argument('--secure-cookie', action='store_true', help='Use when the browser accesses the tool over HTTPS')
    args = parser.parse_args()
    prefix = args.url_prefix.rstrip('/')
    if prefix and not re.fullmatch(r'/[a-zA-Z0-9/_-]+', prefix):
        parser.error('--url-prefix must be a path such as /email-test')
    # Match the website's relative database paths even when run from elsewhere.
    os.chdir(PROJECT_ROOT)
    from src.services.email_test_tool import create_app, open_audit
    if args.history:
        with open_audit(args.database) as store:
            runs = [dict(row) for row in store.execute('SELECT * FROM runs ORDER BY started_at DESC LIMIT 50')]
            for run in runs:
                run['messages'] = [dict(row) for row in store.execute(
                    'SELECT * FROM messages WHERE run_id = ? ORDER BY position', (run['id'],))]
        print(json.dumps(runs, indent=2))
        return 0
    access_key = os.environ.get('EMAIL_TEST_ACCESS_KEY', '').strip() or secrets.token_urlsafe(32)
    # A second instance must not mark a running batch interrupted or send again.
    import fcntl
    args.database.parent.mkdir(parents=True, exist_ok=True)
    with args.database.with_suffix('.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('An email test process is already using this audit database.')
        app = create_app(args.database, access_key=access_key)
        app.config.update(SESSION_COOKIE_SECURE=args.secure_cookie, SESSION_COOKIE_PATH=prefix or '/')
        if prefix:
            from werkzeug.middleware.dispatcher import DispatcherMiddleware
            from werkzeug.exceptions import NotFound
            app.wsgi_app = DispatcherMiddleware(NotFound(), {prefix: app.wsgi_app})
        print(f'Email test form: http://127.0.0.1:{args.port}{prefix}/', flush=True)
        print(f'Server access key (enter in the form): {access_key}', flush=True)
        print(f'Persistent send log: {args.database.resolve()}', flush=True)
        app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
