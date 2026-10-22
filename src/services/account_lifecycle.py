"""Inactivity archiving and durable, retryable account notices."""

import hashlib
import json
import logging
import os
import threading
import uuid
from datetime import timedelta, timezone
from html import escape

from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import or_

from src.routes.golden_plate_recorder_db.db import (
    AccountCreationRequest, AccountDeletionGrant, AccountLifecycleControl,
    AccountLifecycleNotice, Base, EmailVerification, PasswordRecovery, SessionFactory,
    SchoolInviteCode, User, UserInviteCode, _now_utc,
)
from .email_delivery import send_email_via_brevo
from .website_notifications import get_website_update_recipients

logger = logging.getLogger(__name__)
EXEMPT_ROLES = {'superadmin', 'inter_school'}


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def policy_start(store):
    return aware(store.get(AccountLifecycleControl, 'default').started_at)


def activity_anchor(user, baseline):
    return max(aware(value) for value in (
        baseline, user.created_at, user.last_login_at, user.inactivity_restored_at,
    ) if value is not None)


def disable_deadline(user, baseline):
    return activity_anchor(user, baseline) + timedelta(days=120 if user.email_verified_at and user.email else 60)


def cycle_key(user, baseline):
    value = f'{activity_anchor(user, baseline).isoformat()}|{user.email_verified_at}|{user.email or ""}'
    return hashlib.sha256(value.encode()).hexdigest()


def grant_token(grant_id, secret):
    return URLSafeSerializer(secret, salt='account-deletion-v1').dumps(grant_id)


def read_grant_token(token, secret):
    try:
        value = URLSafeSerializer(secret, salt='account-deletion-v1').loads(token)
        return value if isinstance(value, str) else None
    except (BadSignature, TypeError):
        return None


def _recipients(store, user, event):
    if user.email and user.email_verified_at:
        return [user.email]
    if event not in {'disabled', 'delete_1', 'deleted'}:
        return []
    recipients = get_website_update_recipients()
    recipients.extend(row.email for row in store.query(User).filter(
        User.school_id == user.school_id, User.role == 'superadmin', User.status == 'active',
        User.email_verified_at.isnot(None), User.email.isnot(None),
    ).all())
    return list({value.strip().lower(): value.strip() for value in recipients if value and value.strip()}.values())


def queue_notice(store, user, event, now, baseline):
    cycle = cycle_key(user, baseline)
    recipients = _recipients(store, user, event)
    if event in {'disabled', 'delete_1', 'deleted'} and not recipients:
        logger.warning('No configured or verified recipients for account lifecycle event %s (%s)', event, user.id)
    for recipient in recipients:
        key = hashlib.sha256(f'{user.id}|{cycle}|{event}|{recipient.lower()}'.encode()).hexdigest()
        if store.query(AccountLifecycleNotice.id).filter_by(dedupe_key=key).first():
            continue
        grant = AccountDeletionGrant(
            id=str(uuid.uuid4()), user_id=user.id, school_id=user.school_id,
            cycle=cycle, recipient=recipient, permission='owner',
            expires_at=max(aware(user.inactivity_delete_at) or disable_deadline(user, baseline) + timedelta(days=30), now) + timedelta(days=30),
        )
        store.add(grant)
        store.add(AccountLifecycleNotice(
            id=str(uuid.uuid4()), dedupe_key=key, user_id=user.id, event=event,
            recipient=recipient, grant_id=grant.id, details=json.dumps({
                'username': user.username, 'name': user.display_name,
                'school': user.school.name, 'role': user.role,
                'disable_at': disable_deadline(user, baseline).isoformat(),
                'delete_at': aware(user.inactivity_delete_at).isoformat() if user.inactivity_delete_at else None,
                'manual_admin_deletion': user.role == 'admin',
                'verified_owner': bool(user.email and user.email_verified_at),
                'disabled_reason': user.disabled_reason or 'inactivity',
            }), status='pending', attempts=0, next_attempt_at=now,
        ))


def revoke_account_links(store, user_id):
    store.query(AccountDeletionGrant).filter_by(user_id=user_id).update(
        {AccountDeletionGrant.revoked_at: _now_utc()}, synchronize_session=False,
    )
    store.query(AccountLifecycleNotice).filter(
        AccountLifecycleNotice.user_id == user_id,
        AccountLifecycleNotice.status.in_(['pending', 'failed']),
    ).update({AccountLifecycleNotice.status: 'cancelled'}, synchronize_session=False)


def permanently_delete_account(store, user, now, *, explicit=False):
    """Remove credentials; preserve school records through a non-login actor."""
    if user.role in EXEMPT_ROLES or user.is_record_actor:
        raise ValueError('This account is exempt from inactivity deletion.')
    if user.role == 'admin' and not explicit:
        raise ValueError('Admin deletion requires explicit confirmation.')
    claimed = store.query(User).filter(
        User.id == user.id, User.status == user.status, User.role == user.role,
        User.updated_at == user.updated_at, User.password_hash == user.password_hash,
    ).update({User.updated_at: now}, synchronize_session=False)
    if claimed != 1:
        raise ValueError('The account changed during deletion. Review its current status and try again.')
    baseline = policy_start(store)
    # Cancel obsolete notices before enqueueing the truthful final notice.
    revoke_account_links(store, user.id)
    queue_notice(store, user, 'deleted', now, baseline)
    actor_id = f'deleted-{uuid.uuid4()}'
    actor = User(id=actor_id, school_id=user.school_id, username=actor_id,
                 password_hash='', display_name=f'{user.display_name} (deleted)',
                 role='user', status='disabled', is_record_actor=1,
                 created_at=now, updated_at=now)
    store.add(actor)
    store.flush()
    store.query(UserInviteCode).filter_by(user_id=user.id).delete(synchronize_session=False)
    store.query(UserInviteCode).filter_by(issued_by=user.id, status='unused').update(
        {UserInviteCode.status: 'revoked'}, synchronize_session=False,
    )
    store.query(SchoolInviteCode).filter_by(issued_by=user.id, status='unused').update(
        {SchoolInviteCode.status: 'revoked'}, synchronize_session=False,
    )
    # Every User FK, including non-null historical record authors, stays valid.
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if any(foreign.target_fullname == 'users.id' for foreign in column.foreign_keys):
                store.execute(table.update().where(column == user.id).values({column.name: actor_id}))
    store.query(EmailVerification).filter_by(user_id=user.id).delete(synchronize_session=False)
    store.query(PasswordRecovery).filter_by(user_id=user.id).delete(synchronize_session=False)
    store.query(AccountCreationRequest).filter_by(school_id=user.school_id, username=user.username).delete(synchronize_session=False)
    store.delete(user)


def restore_account(store, user, now):
    if user.is_record_actor or user.role in EXEMPT_ROLES:
        raise ValueError('This account cannot be recovered from this box.')
    user.status = 'active'
    user.inactivity_disabled_at = None
    user.inactivity_delete_at = None
    user.inactivity_restored_at = now
    user.disabled_reason = None
    user.updated_at = now
    revoke_account_links(store, user.id)


def enforce_inactivity_for_login(store, user, now):
    if user.role in EXEMPT_ROLES or user.is_record_actor or user.status != 'active':
        return False
    baseline = policy_start(store)
    if now < disable_deadline(user, baseline):
        return False
    claimed = store.query(User).filter(
        User.id == user.id, User.status == 'active', User.role == user.role,
        User.updated_at == user.updated_at,
    ).update({User.status: 'disabled', User.inactivity_disabled_at: now,
              User.inactivity_delete_at: now + timedelta(days=30),
              User.disabled_reason: 'inactivity', User.updated_at: now}, synchronize_session=False)
    store.refresh(user)
    if not claimed:
        return user.status != 'active'
    queue_notice(store, user, 'disabled', now, baseline)
    return True


def plan_lifecycle(store, now):
    baseline = policy_start(store)
    for user in store.query(User).filter(User.is_record_actor == 0, User.role.notin_(EXEMPT_ROLES)).all():
        if user.status == 'active':
            if enforce_inactivity_for_login(store, user, now):
                continue
            remaining = disable_deadline(user, baseline) - now
            if user.email_verified_at and user.email:
                event = 'disable_3' if remaining <= timedelta(days=3) else 'disable_14' if remaining <= timedelta(days=14) else None
                if event:
                    queue_notice(store, user, event, now, baseline)
        elif not user.inactivity_disabled_at or not user.inactivity_delete_at:
            # Historical manually-disabled accounts get a fresh full month.
            user.inactivity_disabled_at = now
            user.inactivity_delete_at = now + timedelta(days=30)
            user.disabled_reason = 'manual'
            user.updated_at = now
            queue_notice(store, user, 'disabled', now, baseline)
        else:
            remaining = aware(user.inactivity_delete_at) - now
            if remaining <= timedelta(0) and user.role == 'user':
                permanently_delete_account(store, user, now)
            elif remaining <= timedelta(days=1):
                queue_notice(store, user, 'delete_1', now, baseline)
            elif remaining <= timedelta(days=7) and user.email_verified_at and user.email:
                queue_notice(store, user, 'delete_7', now, baseline)


def _notice_html(event, details, link):
    admin = details['manual_admin_deletion']
    descriptions = {
        'disable_14': 'This account will be disabled within 14 days unless its owner signs in.',
        'disable_3': 'This account will be disabled within 3 days unless its owner signs in.',
        'disabled': 'This account has been disabled for inactivity. Its owner can no longer sign in to the school portal. A school admin or superadmin can recover it.',
        'delete_7': 'This disabled account is approaching its 30-day deletion deadline.',
        'delete_1': 'This disabled account is within one day of its deletion deadline.',
        'deleted': 'This login account has been permanently deleted. School records and sessions have been preserved.',
    }
    summary = descriptions[event]
    if event == 'disabled' and details.get('disabled_reason') == 'manual':
        summary = 'This account has been disabled by school administration. Its owner can no longer sign in to the school portal. A school admin or superadmin can recover it.'
    if admin and event in {'delete_7', 'delete_1'}:
        summary = 'This disabled admin account is approaching or has reached its 30-day review date.'
    if admin and event != 'deleted':
        summary += ' Admin accounts are never automatically deleted: deletion requires explicit confirmation by the owner or a school superadmin.'
    title = 'Account deleted' if event == 'deleted' else 'Account disabled' if event == 'disabled' else 'Account inactivity reminder'
    fields = [('School', details['school']), ('Account', details['username']), ('Name', details['name'])]
    if event != 'deleted':
        fields.append(('Disable deadline (UTC)', details['disable_at']))
        if details['delete_at']:
            fields.append(('Deletion review date (UTC)' if admin else 'Deletion deadline (UTC)', details['delete_at']))
    rows = ''.join(f'<tr><th align="left">{escape(label)}</th><td>{escape(value)}</td></tr>' for label, value in fields)
    html = f'<h1>{title}</h1><p>{escape(summary)}</p><table>{rows}</table>'
    html += f'<p><a href="{escape(link, quote=True)}">Permanently delete this account</a></p>'
    html += '<p>The owner must enter their username and password and complete two confirmation steps. Opening this link does not delete anything. If the account was already deleted, the page will say so.</p>'
    return title, html


def send_account_lifecycle_email(recipient, event, details, link):
    title, html = _notice_html(event, details, link)
    return send_email_via_brevo(recipient, f'Golden Plate — {title}', html, notification_type='account_lifecycle')


def deliver_pending_notices(secret, now=None):
    now = now or _now_utc()
    with SessionFactory() as store:
        ids = [row.id for row in store.query(AccountLifecycleNotice).filter(
            AccountLifecycleNotice.status.in_(['pending', 'failed', 'sending']),
            or_(AccountLifecycleNotice.next_attempt_at.is_(None), AccountLifecycleNotice.next_attempt_at <= now),
            or_(AccountLifecycleNotice.claimed_until.is_(None), AccountLifecycleNotice.claimed_until <= now),
        ).limit(100).all()]
    for notice_id in ids:
        with SessionFactory() as store:
            claimed = store.query(AccountLifecycleNotice).filter(
                AccountLifecycleNotice.id == notice_id,
                AccountLifecycleNotice.status.in_(['pending', 'failed', 'sending']),
                or_(AccountLifecycleNotice.claimed_until.is_(None), AccountLifecycleNotice.claimed_until <= now),
            ).update({AccountLifecycleNotice.status: 'sending', AccountLifecycleNotice.claimed_until: now + timedelta(minutes=5),
                      AccountLifecycleNotice.attempts: AccountLifecycleNotice.attempts + 1}, synchronize_session=False)
            if not claimed:
                continue
            store.commit()
            notice = store.get(AccountLifecycleNotice, notice_id)
            event, recipient, details, grant_id, attempts = notice.event, notice.recipient, json.loads(notice.details), notice.grant_id, notice.attempts
            grant = store.get(AccountDeletionGrant, grant_id)
            target = store.get(User, notice.user_id)
            if not details['verified_owner']:
                allowed = {value.strip().lower() for value in get_website_update_recipients()}
                allowed.update(row.email.strip().lower() for row in store.query(User).filter(
                    User.school_id == grant.school_id, User.role == 'superadmin', User.status == 'active',
                    User.email_verified_at.isnot(None), User.email.isnot(None),
                ).all() if row.email and row.email.strip())
                if recipient.lower() not in allowed:
                    notice.status = 'cancelled'
                    store.commit()
                    continue
            if event != 'deleted' and (not target or grant.revoked_at or cycle_key(target, policy_start(store)) != grant.cycle
                                      or (event.startswith('disable_') and target.status != 'active')):
                notice.status = 'cancelled'
                store.commit()
                continue
        base = os.environ.get('WEBSITE_PUBLIC_URL', 'https://goldenplate.ca').rstrip('/')
        link = f'{base}/account-deletion#token={grant_token(grant_id, secret)}'
        try:
            result = send_account_lifecycle_email(recipient, event, details, link)
        except Exception:
            logger.exception('Account lifecycle email delivery failed')
            result = {'success': False, 'error': 'Email delivery failed'}
        with SessionFactory() as store:
            notice = store.get(AccountLifecycleNotice, notice_id)
            notice.claimed_until = None
            if result.get('success'):
                notice.status = 'skipped' if result.get('skipped') else 'sent'
                notice.sent_at = now
                notice.last_error = None
            else:
                notice.status = 'failed'
                notice.last_error = 'Email delivery failed; automatic retry pending.'
                notice.next_attempt_at = now + timedelta(minutes=min(60, 2 ** min(attempts, 6)))
                logger.warning('Account lifecycle email to %s failed; queued for retry', recipient)
            store.commit()


def run_account_lifecycle(secret, now=None, *, force=False):
    now = now or _now_utc()
    owner = str(uuid.uuid4())
    with SessionFactory() as store:
        claimed = store.query(AccountLifecycleControl).filter(
            AccountLifecycleControl.id == 'default',
            or_(AccountLifecycleControl.lease_until.is_(None), AccountLifecycleControl.lease_until <= now),
        ).update({AccountLifecycleControl.lease_owner: owner, AccountLifecycleControl.lease_until: now + timedelta(minutes=10)}, synchronize_session=False)
        store.commit()
        if not claimed:
            return False
        try:
            control = store.get(AccountLifecycleControl, 'default')
            if force or not control.next_run_at or aware(control.next_run_at) <= now:
                plan_lifecycle(store, now)
                control.next_run_at = now + timedelta(hours=1)
                store.commit()
            deliver_pending_notices(secret, now)
        finally:
            store.rollback()
            store.query(AccountLifecycleControl).filter_by(id='default', lease_owner=owner).update({
                AccountLifecycleControl.lease_owner: None, AccountLifecycleControl.lease_until: None,
            }, synchronize_session=False)
            store.commit()
    return True


def start_account_lifecycle(app, *, reloader_parent=False):
    enabled = os.environ.get('ACCOUNT_LIFECYCLE_WORKER_ENABLED', 'true').strip().lower()
    if app.testing or reloader_parent or enabled in {'false', '0', 'no', 'off'}:
        return None
    if app.extensions.get('account_lifecycle_pid') == os.getpid():
        return None
    app.extensions['account_lifecycle_pid'] = os.getpid()
    stop = threading.Event()
    app.extensions['account_lifecycle_stop'] = stop
    def work():
        while not stop.is_set():
            try:
                run_account_lifecycle(app.secret_key)
            except Exception:
                logger.exception('Account lifecycle maintenance failed; retrying next minute')
            stop.wait(60)
    worker = threading.Thread(target=work, name='account-lifecycle', daemon=True)
    try:
        worker.start()
    except RuntimeError:
        logger.error('Account lifecycle worker could not start: this host must enable background threads for automatic cleanup')
        return None
    return worker
