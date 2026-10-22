"""Send the website's emails from the server terminal.

Usage: python scripts/test_emails.py [--email recipient@example.com]
Use --history for saved results or --web for the optional CAPTCHA browser form.
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


def run_terminal(database, email=None):
    from src.services.email_test_tool import (
        build_email_samples, normalize_recipient, read_run, recover_interrupted_runs,
        reserve_run, send_batch,
    )
    try:
        recipient = normalize_recipient(email if email is not None else input('Recipient email: '))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print('\nCancelled. No test emails were sent.')
        return 1
    try:
        samples = build_email_samples()
    except Exception:
        print('Could not prepare the email scenarios. Check the server configuration. No test emails were sent.', file=sys.stderr)
        return 1
    print(f'This will send {len(samples)} emails using the website’s normal send functions to {recipient}.')
    print('Disabled notification types will be skipped. Results and UTC send times are saved.')
    print('Terminal mode uses your server access and this confirmation; it does not use browser CAPTCHA.')
    confirmation = f'SEND {recipient}'
    try:
        if input(f'Type "{confirmation}" to send: ').strip() != confirmation:
            print('Cancelled. No test emails were sent.')
            return 1
    except (EOFError, KeyboardInterrupt):
        print('\nCancelled. No test emails were sent.')
        return 1

    run_id = None
    try:
        recover_interrupted_runs(database)
        run_id = reserve_run(database, recipient, samples)
        if run_id is None:
            print('An email test is already running. Wait for it to finish before starting another.', file=sys.stderr)
            return 1
        print(f'Batch: {run_id}\nPersistent send log: {database}', flush=True)

        def progress(result):
            print(f"[{result['position'] + 1}/{len(samples)}] {result['finished_at']} "
                  f"{result['label']}: {result['status'].upper()}", flush=True)
            if result['message_id']:
                print(f"  Provider message ID: {result['message_id']}", flush=True)
            if result['error']:
                print(f"  {result['error']}", flush=True)

        send_batch(database, run_id, samples, on_result=progress)
        run = read_run(database, run_id)
        counts = {status: sum(item['status'] == status for item in run['messages'])
                  for status in ('accepted', 'skipped', 'failed', 'unknown', 'cancelled')}
        print('Results: ' + ', '.join(f'{count} {status}' for status, count in counts.items()), flush=True)
        print('Accepted means the provider accepted the request; check the inbox to confirm arrival.')
        return 0 if run['status'] == 'completed' else 1
    except KeyboardInterrupt:
        if run_id:
            recover_interrupted_runs(database, run_id)
        print('\nStopped. Saved results are preserved; interrupted sends are not retried.', file=sys.stderr)
        return 130
    except Exception:
        print('Email test stopped. Check the saved history and server configuration before retrying.', file=sys.stderr)
        return 1


def main():
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--web', action='store_true', help='Start the optional CAPTCHA-protected browser form')
    mode.add_argument('--history', action='store_true', help='Print the latest 50 saved runs; send nothing')
    parser.add_argument('--email', help='Recipient for terminal mode; prompted if omitted')
    parser.add_argument('--port', type=int, default=59238)
    parser.add_argument('--database', type=Path, default=PROJECT_ROOT / 'data' / 'email_test_runs.sqlite3')
    parser.add_argument('--url-prefix', default='', help='Optional reverse-proxy mount path, e.g. /email-test')
    parser.add_argument('--secure-cookie', action='store_true', help='Use when the browser accesses the tool over HTTPS')
    args = parser.parse_args()
    if args.email is not None and (args.web or args.history):
        parser.error('--email is for terminal mode only')
    if not args.web and (args.url_prefix or args.secure_cookie or args.port != 59238):
        parser.error('--port, --url-prefix and --secure-cookie require --web')
    prefix = args.url_prefix.rstrip('/')
    if prefix and not re.fullmatch(r'/[a-zA-Z0-9/_-]+', prefix):
        parser.error('--url-prefix must be a path such as /email-test')
    args.database = args.database.expanduser().resolve()
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
    # A second instance must not mark a running batch interrupted or send again.
    import fcntl
    args.database.parent.mkdir(parents=True, exist_ok=True)
    with args.database.with_suffix('.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('An email test process is already using this audit database.')
        if not args.web:
            return run_terminal(args.database, args.email)
        access_key = os.environ.get('EMAIL_TEST_ACCESS_KEY', '').strip() or secrets.token_urlsafe(32)
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
