"""Queue and deliver published release notes during application initialization."""

import logging
import os
import re
import threading
import time
from html import escape

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from src.routes.golden_plate_recorder_db.db import ReleaseEmailBatch, ReleaseEmailDelivery, SessionFactory, User

from .email_delivery import send_email_via_brevo
from .release_notes import read_release_notes, version_key
from .website_notifications import get_website_update_recipients

logger = logging.getLogger(__name__)

# Releases through this version were already published when email was introduced.
INITIAL_RELEASE_KEY = version_key('1.2.1.1')
EMAIL_ENTRY_LIMIT = 3
DELIVERY_LEASE_SECONDS = 300


def _render_body(markdown):
    blocks = []
    for block in re.split(r'\n\s*\n', markdown):
        lines = block.splitlines()
        if all(line.startswith(('- ', '* ')) for line in lines):
            items = ''.join(f'<li>{escape(line[2:])}</li>' for line in lines)
            blocks.append(f'<ul>{items}</ul>')
        else:
            blocks.append(f'<p>{escape(" ".join(lines))}</p>')
    return ''.join(blocks)


def send_release_email(email, entries):
    """Send a single digest, with entries ordered from newest to oldest."""
    latest = entries[0][0]
    history_url = os.environ.get('WEBSITE_PUBLIC_URL', 'https://goldenplate.ca').rstrip('/') + '/release-notes'
    sections = ''.join(
        f'<h2>Version {escape(version)}</h2>{_render_body(body)}'
        for version, body in entries[:EMAIL_ENTRY_LIMIT]
    )
    if len(entries) > EMAIL_ENTRY_LIMIT:
        history_url += f'#version-{entries[EMAIL_ENTRY_LIMIT][0]}'
        link_label = 'Check out more'
    else:
        link_label = 'View release history'
    html = (
        f'<h1>Golden Plate release notes</h1>{sections}'
        f'<p><a href="{escape(history_url, quote=True)}">{link_label}</a></p>'
    )
    return send_email_via_brevo(email, f'Golden Plate — Version {latest}', html,
                               notification_type='release_notes')


def get_release_recipients(session):
    account_emails = session.scalars(select(User.email).where(
        User.role.in_(('superadmin', 'admin')), User.email.is_not(None),
    ))
    return {
        email.strip().lower() for email in [*get_website_update_recipients(), *account_emails]
        if email.strip()
    }


def _queue_release(session, newest_key, recipients):
    while True:
        previous_key = session.scalar(
            select(ReleaseEmailBatch.version_key).order_by(ReleaseEmailBatch.version_key.desc()).limit(1)
        ) or INITIAL_RELEASE_KEY
        if newest_key <= previous_key:
            return

        session.add(ReleaseEmailBatch(version_key=newest_key, previous_key=previous_key))
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            # Another worker may have queued this release or an intermediate one.
            if session.scalar(select(ReleaseEmailBatch.version_key).where(
                ReleaseEmailBatch.previous_key == previous_key,
            )) is None:
                raise
            continue

        session.add_all(ReleaseEmailDelivery(version_key=newest_key, email=email) for email in recipients)
        session.commit()
        return


def _deliver(session, key, email, entries):
    now = int(time.time())
    claim_until = now + DELIVERY_LEASE_SECONDS
    delivery = update(ReleaseEmailDelivery).where(
        ReleaseEmailDelivery.version_key == key, ReleaseEmailDelivery.email == email,
    )
    claimed = session.execute(delivery.where(
        ReleaseEmailDelivery.completed.is_(False), ReleaseEmailDelivery.claim_until <= now,
    ).values(claim_until=claim_until)).rowcount
    session.commit()
    if not claimed:
        return

    # The claim is committed before calling email delivery, which opens its own
    # database session for preferences. An interrupted claim expires for retry.
    try:
        result = send_release_email(email, entries)
    except Exception:
        logger.exception('Release email failed for %s', email)
        result = {'success': False}
    if not result.get('success'):
        logger.warning('Release email for version %s to %s failed: %s', entries[0][0], email, result.get('error'))
    session.execute(delivery.where(ReleaseEmailDelivery.claim_until == claim_until).values(
        completed=bool(result.get('success')), claim_until=0,
    ))
    session.commit()


def notify_new_releases():
    notes = read_release_notes()
    if not notes:
        return
    entries = sorted(((version_key(version), version, body) for version, body in notes.items()), reverse=True)
    published_keys = {key for key, _, _ in entries}
    with SessionFactory() as session:
        recipients = get_release_recipients(session)
        _queue_release(session, entries[0][0], recipients)
        pending = session.execute(
            select(ReleaseEmailDelivery.version_key, ReleaseEmailBatch.previous_key, ReleaseEmailDelivery.email)
            .join(ReleaseEmailBatch, ReleaseEmailDelivery.version_key == ReleaseEmailBatch.version_key)
            .where(ReleaseEmailDelivery.completed.is_(False))
            .order_by(ReleaseEmailDelivery.version_key)
        ).all()
        session.commit()

        for key, previous_key, email in pending:
            if email in recipients and key in published_keys:
                digest = [(version, body) for entry_key, version, body in entries if previous_key < entry_key <= key]
                _deliver(session, key, email, digest)


def start_release_notifications(app, *, reloader_parent=False):
    enabled = os.environ.get('WEBSITE_RELEASE_NOTIFY_ENABLED', 'true').strip().lower()
    if app.testing or reloader_parent or enabled in {'0', 'false', 'no', 'off'}:
        return None
    process_id = os.getpid()
    if app.extensions.get('release_notification_pid') == process_id:
        return None
    app.extensions['release_notification_pid'] = process_id

    def send():
        try:
            notify_new_releases()
        except Exception:
            logger.exception('Unable to process release emails')

    worker = threading.Thread(target=send, name='release-notifications', daemon=True)
    try:
        worker.start()
    except RuntimeError:
        logger.warning('Background threads unavailable; checking for new releases directly')
        send()
        return None
    return worker
