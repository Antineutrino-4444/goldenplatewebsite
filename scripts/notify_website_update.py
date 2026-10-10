"""Send one code-change or deployment summary using the existing Brevo service."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.website_notifications import notify_website_update


def code_details():
    """Describe the revision and changed filenames, without sending file contents."""
    def git(*args):
        try:
            return subprocess.check_output(
                ['git', *args], cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL,
                timeout=10,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            return ''

    revision = git('rev-parse', '--short', 'HEAD')
    subject = git('log', '-1', '--format=%s')
    paths = ('src', 'frontend', 'scripts', 'deploy_local.sh', 'deploy.bat',
             'requirements.txt', 'README.md', 'docs', 'AGENTS.md', '.env.example')
    tracked = git('diff', '--name-only', 'HEAD', '--', *paths)
    untracked = git('ls-files', '--others', '--exclude-standard', '--', *paths)
    # Filenames only; secrets, database contents, and diffs are never emailed.
    changed = sorted(set((tracked + '\n' + untracked).splitlines()) - {''})
    return [
        ('Environment', os.environ.get('APP_ENV', 'development')),
        ('Revision', revision or 'Not available'),
        ('Latest commit', subject or 'Not available'),
        ('Uncommitted website files', ', '.join(changed) or 'None'),
    ]


def send_update(kind, summary, *, url=None):
    title = 'Website code changes prepared' if kind == 'code-change' else 'Website deployment ready'
    return notify_website_update(title, summary, code_details(), url=url)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=('code-change', 'deployment'), required=True)
    parser.add_argument('--summary', required=True)
    parser.add_argument('--url', help='Website link to include in the notification')
    args = parser.parse_args(argv)
    load_dotenv(PROJECT_ROOT / '.env')
    result = send_update(args.kind, args.summary, url=args.url)
    if result.get('skipped'):
        print('No website update recipients configured; email skipped.')
        return 0
    if result['success']:
        print('Website update email sent successfully.')
        return 0
    print('WARNING: Website update email failed; check Brevo configuration and server logs.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
