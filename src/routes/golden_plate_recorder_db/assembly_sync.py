"""Maintain each teacher's dedicated school deck while its cloud grant is active."""

import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import uuid
from datetime import timedelta, timezone

from flask import current_app, has_app_context
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import case, or_
from sqlalchemy.exc import IntegrityError

from .db import AssemblyDeck, SessionFactory, User, _now_utc

logger = logging.getLogger(__name__)
CHECK_INTERVAL = timedelta(seconds=60)
LEASE_DURATION = timedelta(minutes=10)
PROVIDERS = ('google', 'microsoft')
# Only refresh files for the provider whose export changed.
ASSEMBLY_DESIGN_REVISIONS = {'google': 15, 'microsoft': 33}
_start_lock = threading.Lock()
_UNSET = object()


def _cipher():
    secret = os.environ.get('SECRET_KEY', '')
    if secret in ('', 'dev-only-change-me', 'replace-with-a-long-random-secret'):
        raise ValueError('Configure a private Flask signing key for connected assembly decks.')
    key = os.environ.get('ASSEMBLY_SYNC_ENCRYPTION_KEY', '').strip()
    if key:
        return Fernet(key.encode('ascii'))
    # Separate the token-encryption key from the Flask cookie-signing key.
    derived = hmac.digest(secret.encode(), b'Golden Plate assembly refresh tokens v1', 'sha256')
    return Fernet(base64.urlsafe_b64encode(derived))


def credentials_configured():
    try:
        _cipher()
    except (ValueError, UnicodeError):
        return False
    return True


def _public(row):
    if row is None or row.status == 'disconnected':
        return None
    def timestamp(value):
        if value and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat() if value else None
    return {'id': row.id, 'provider': row.provider, 'theme': row.theme, 'school_label': row.school_label,
            'url': row.web_url, 'status': row.status, 'message': row.message,
            'last_synced_at': timestamp(row.last_synced_at), 'next_check_at': timestamp(row.next_check_at),
            'lease_until': timestamp(row.lease_until), 'attempts': row.attempts}


def _binding(store, school_id, user_id, provider, theme):
    return store.query(AssemblyDeck).filter_by(school_id=school_id, owner_id=user_id, provider=provider, theme=theme)


def get_deck(school_id, user_id, provider, theme):
    with SessionFactory() as store:
        return _public(_binding(store, school_id, user_id, provider, theme).one_or_none())


def list_decks(school_id, user_id):
    with SessionFactory() as store:
        rows = store.query(AssemblyDeck).filter_by(school_id=school_id, owner_id=user_id).filter(
            AssemblyDeck.status != 'disconnected').order_by(AssemblyDeck.provider, AssemblyDeck.theme)
        return [_public(row) for row in rows]


def list_school_decks(school_id):
    with SessionFactory() as store:
        rows = store.query(AssemblyDeck, User).join(User, User.id == AssemblyDeck.owner_id).filter(
            AssemblyDeck.school_id == school_id, AssemblyDeck.status != 'disconnected',
        ).order_by(AssemblyDeck.provider, AssemblyDeck.theme, User.username).all()
        return [{**_public(deck), 'owner_name': owner.display_name or owner.username,
                 'owner_username': owner.username} for deck, owner in rows]


def request_deck_sync(deck_id, school_id, *, owner_id=None):
    """Persist a manual refresh without uploading inside the web request."""
    with SessionFactory() as store:
        query = store.query(AssemblyDeck).filter_by(id=deck_id, school_id=school_id)
        if owner_id is not None:
            query = query.filter_by(owner_id=owner_id)
        changed = query.filter(AssemblyDeck.status.in_(('ready', 'pending', 'retry')),
                               AssemblyDeck.encrypted_refresh_token.is_not(None)).update({
            'status': 'pending', 'message': None, 'snapshot_hash': None, 'next_check_at': _now_utc(),
        }, synchronize_session=False)
        store.commit()
        result = _public(query.one_or_none())
    if changed:
        wake_assembly_sync()
    return result


def queue_school_decks(store, school_id):
    """Queue connected decks in the same transaction as a finalized winner."""
    return store.query(AssemblyDeck).filter(
        AssemblyDeck.school_id == school_id,
        AssemblyDeck.status.in_(('ready', 'pending', 'retry')),
        AssemblyDeck.encrypted_refresh_token.is_not(None),
    ).update({'status': 'pending', 'message': None, 'next_check_at': _now_utc()},
             synchronize_session=False)


def wake_assembly_sync():
    """Wake this process's worker after the winner and queue have committed."""
    if has_app_context():
        wake = current_app.extensions.get('assembly_sync_wake')
        if wake is not None:
            wake.set()


def set_school_label(school_id, user_id, provider, theme, label):
    with SessionFactory() as store:
        query = _binding(store, school_id, user_id, provider, theme)
        query.filter(AssemblyDeck.status.notin_(('disconnected', 'reconnect')),
                     AssemblyDeck.school_label.is_distinct_from(label)).update(
            {'school_label': label, 'status': 'pending', 'message': None, 'next_check_at': _now_utc()},
            synchronize_session=False)
        store.commit()
        return _public(query.one_or_none())


def bind_deck(school_id, user_id, provider, theme, refresh_token, *, school_label=_UNSET):
    if not refresh_token or provider not in PROVIDERS or theme not in ('light', 'dark'):
        raise ValueError('A valid provider, theme and offline grant are required.')
    encrypted = _cipher().encrypt(refresh_token.encode()).decode('ascii')
    with SessionFactory() as store:
        query = _binding(store, school_id, user_id, provider, theme)
        if query.first() is None:
            try:
                with store.begin_nested():
                    store.add(AssemblyDeck(school_id=school_id, owner_id=user_id, provider=provider, theme=theme))
                    store.flush()
            except IntegrityError:
                if query.one_or_none() is None:
                    raise
        # An in-flight operation can finish, but cannot replace this newer grant.
        # Preserve file_id on reconnect so the teacher's existing link survives.
        changes = {'encrypted_refresh_token': encrypted, 'status': 'pending', 'message': None,
                   'generation': AssemblyDeck.generation + 1, 'snapshot_hash': None,
                   'attempts': 0, 'next_check_at': _now_utc()}
        if school_label is not _UNSET:
            changes['school_label'] = school_label
        query.update(changes, synchronize_session=False)
        store.commit()
        return _public(query.one())


def disconnect_deck(school_id, user_id, provider, theme):
    with SessionFactory() as store:
        changed = _binding(store, school_id, user_id, provider, theme).filter(
            AssemblyDeck.status != 'disconnected').update({
                'status': 'disconnected', 'encrypted_refresh_token': None, 'message': None, 'school_label': None,
                'generation': AssemblyDeck.generation + 1, 'next_check_at': None,
            }, synchronize_session=False)
        store.commit()
        return bool(changed)


def _update_claim(row, changes):
    """Fence token rotation, file links and status against a newer owner or grant."""
    with SessionFactory() as store:
        updated = store.query(AssemblyDeck).filter_by(
            id=row.id, lease_owner=row.lease_owner, generation=row.generation,
        ).update(changes, synchronize_session=False)
        store.commit()
        return bool(updated)


def _retry(row, message, *, reconnect=False):
    attempts = row.attempts + 1
    if reconnect:
        _update_claim(row, {'status': 'reconnect', 'message': message, 'encrypted_refresh_token': None,
                            'attempts': attempts, 'next_check_at': None})
    else:
        delay = timedelta(seconds=min(3600, 15 * 2 ** min(attempts, 8)))
        _update_claim(row, {'status': 'retry', 'message': message, 'attempts': attempts,
                            'next_check_at': _now_utc() + delay})


def _sync_claim(row):
    from src.services import assembly_cloud
    from .presentation_routes import assembly_snapshot_for_owner

    snapshot = assembly_snapshot_for_owner(row.school_id, row.owner_id, with_winners=True)
    if snapshot is None:
        _retry(row, 'School access changed. Reconnect with an authorized school account.', reconnect=True)
        return
    snapshot['school_label'] = row.school_label
    content = {key: value for key, value in snapshot.items() if key != 'generated_at'}
    content['design_revision'] = ASSEMBLY_DESIGN_REVISIONS[row.provider]
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    # Retain new file IDs and rotated tokens, but do not mark an old upload ready
    # if a winner or school label changed while it was running.
    unchanged = (AssemblyDeck.school_label.is_not_distinct_from(row.school_label)
                 & AssemblyDeck.next_check_at.is_not_distinct_from(row.next_check_at))
    now = _now_utc()
    success = {'status': case((unchanged, 'ready'), else_='pending'), 'message': None, 'attempts': 0,
               'next_check_at': case((unchanged, now + CHECK_INTERVAL), else_=now)}
    if row.file_id and row.snapshot_hash == digest:
        _update_claim(row, success)
        return
    try:
        cipher = _cipher()
        token = cipher.decrypt(row.encrypted_refresh_token.encode()).decode()
    except (InvalidToken, ValueError):
        _retry(row, 'The stored cloud connection could not be opened. Reconnect this deck.', reconnect=True)
        return
    try:
        tokens = assembly_cloud.refresh_access(row.provider, token)
        # Save a rotated refresh token before uploading. If upload fails, retry
        # with the new token, including when another process resumes this work.
        changes = {'lease_until': _now_utc() + LEASE_DURATION}
        if tokens.get('refresh_token'):
            changes['encrypted_refresh_token'] = cipher.encrypt(tokens['refresh_token'].encode()).decode('ascii')
        if not _update_claim(row, changes):
            return
        file_id, url = assembly_cloud.upsert_deck(row.provider, tokens['access_token'], row.id,
                                                 row.file_id, snapshot, row.theme)
    except assembly_cloud.CloudDeckError as error:
        _retry(row, str(error), reconnect=error.reconnect)
        return
    success.update(file_id=file_id, web_url=url, snapshot_hash=digest, last_synced_at=_now_utc())
    _update_claim(row, success)


def sync_deck(deck_id, *, force=False):
    """Check a binding now or when due, returning its current public status."""
    from src.services.assembly_cloud import provider_configured

    owner = str(uuid.uuid4())
    now = _now_utc()
    with SessionFactory() as store:
        row = store.get(AssemblyDeck, deck_id)
        if not row or not provider_configured(row.provider) or not credentials_configured():
            return _public(row)
        query = store.query(AssemblyDeck).filter(
            AssemblyDeck.id == deck_id, AssemblyDeck.encrypted_refresh_token.is_not(None),
            or_(AssemblyDeck.lease_until.is_(None), AssemblyDeck.lease_until <= now))
        if not force:
            query = query.filter(AssemblyDeck.next_check_at <= now)
        claimed = query.update({'lease_owner': owner, 'lease_until': now + LEASE_DURATION}, synchronize_session=False)
        store.commit()
        row = store.get(AssemblyDeck, deck_id)
        if not claimed or row is None:
            info = _public(row)
            # A simultaneous native-file update owns the lease. Do not signal
            # that the previously synced URL already contains today's results.
            if info and force and row.lease_owner and info['status'] == 'ready':
                info['status'] = 'pending'
            return info
        store.refresh(row)
        if row.lease_owner != owner or not row.encrypted_refresh_token:
            store.query(AssemblyDeck).filter_by(id=deck_id, lease_owner=owner).update(
                {'lease_owner': None, 'lease_until': None}, synchronize_session=False)
            store.commit()
            return _public(row)
        store.expunge(row)
    try:
        _sync_claim(row)
    except Exception as error:
        # Never log arbitrary provider exceptions or database parameters containing tokens.
        logger.warning('Assembly synchronization failed for %s (%s)', deck_id, type(error).__name__)
        _retry(row, 'The presentation could not be updated. Golden Plate will retry.', reconnect=False)
    finally:
        with SessionFactory() as store:
            store.query(AssemblyDeck).filter_by(id=deck_id, lease_owner=owner).update(
                {'lease_owner': None, 'lease_until': None}, synchronize_session=False)
            store.commit()
    return get_deck(row.school_id, row.owner_id, row.provider, row.theme)


def run_due_decks():
    from src.services.assembly_cloud import provider_configured
    providers = [name for name in PROVIDERS if provider_configured(name)]
    if not providers or not credentials_configured():
        return
    now = _now_utc()
    with SessionFactory() as store:
        due = store.query(AssemblyDeck.id).filter(
            AssemblyDeck.provider.in_(providers), AssemblyDeck.next_check_at <= now,
            or_(AssemblyDeck.lease_until.is_(None), AssemblyDeck.lease_until <= now),
        ).order_by(AssemblyDeck.next_check_at).limit(100).all()
    for (deck_id,) in due:
        sync_deck(deck_id)


def start_assembly_sync(app, *, reloader_parent=False):
    if app.testing or reloader_parent or os.getenv('ASSEMBLY_SYNC_WORKER_ENABLED', 'true').lower() in {'0', 'no', 'false', 'off'}:
        return
    from src.services.assembly_cloud import provider_configured
    if not credentials_configured() or not any(provider_configured(name) for name in PROVIDERS):
        return

    def ensure_worker():
        # With a preloaded WSGI app, a forked process needs its own thread.
        if app.extensions.get('assembly_sync_pid') == os.getpid():
            return
        with _start_lock:
            if app.extensions.get('assembly_sync_pid') == os.getpid():
                return
            stop = threading.Event()
            wake = threading.Event()

            def work():
                while not stop.is_set():
                    # Clear before checking: a finalization during an upload
                    # must cause another pass without waiting for the timer.
                    wake.clear()
                    try:
                        with app.app_context():
                            run_due_decks()
                    except Exception as error:
                        logger.warning('Assembly maintenance will retry (%s)', type(error).__name__)
                    wake.wait(15)

            thread = threading.Thread(target=work, name='assembly-sync', daemon=True)
            try:
                thread.start()
            except RuntimeError:
                logger.error('Assembly updates require a WSGI host with background threads enabled')
                return
            app.extensions['assembly_sync_pid'] = os.getpid()
            app.extensions['assembly_sync_stop'] = stop
            app.extensions['assembly_sync_wake'] = wake

    ensure_worker()
    if not app.extensions.get('assembly_sync_hook'):
        app.before_request(ensure_worker)
        app.extensions['assembly_sync_hook'] = True
