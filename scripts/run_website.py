"""Start the built website and notify reviewers once it is responding."""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.notify_website_update import send_update


def wait_until_ready(process, url, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200 and process.poll() is None:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False


def stop_server(process):
    if process.poll() is not None:
        return
    try:
        if os.name == 'nt':
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            if os.name == 'nt':
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def main():
    load_dotenv(PROJECT_ROOT / '.env')
    port = int(os.environ.get('PORT', '59237'))
    # Refuse to mistake an already running server for this deployment.
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1', port)) == 0:
            print(f'ERROR: Port {port} is already in use; no deployment email sent.', file=sys.stderr)
            return 1
    process = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / 'src' / 'main.py')],
        cwd=PROJECT_ROOT,
        start_new_session=os.name != 'nt',
    )
    local_url = f'http://127.0.0.1:{port}/'
    try:
        if not wait_until_ready(process, local_url):
            print('ERROR: Website did not become ready; no deployment email sent.', file=sys.stderr)
            return process.poll() or 1
        result = send_update(
            'deployment',
            'The website build completed and the server is responding successfully. '
            'This notification confirms local server readiness; external routing has not been checked.',
            url=os.environ.get('WEBSITE_PUBLIC_URL') or local_url,
        )
        if not result['success']:
            print('WARNING: Server is running, but the deployment email failed. Check Brevo configuration.', file=sys.stderr)
        return process.wait()
    except KeyboardInterrupt:
        return 130
    finally:
        stop_server(process)


if __name__ == '__main__':
    raise SystemExit(main())
