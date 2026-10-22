"""Email scenarios that invoke the same send functions as application events."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
from types import SimpleNamespace
from typing import Callable
import os
import secrets
import uuid


@dataclass(frozen=True)
class EmailScenario:
    key: str
    label: str
    send: Callable[[str], dict]
    notification_type: str | None = None


def send_verification_scenario(email, *, purpose):
    from src.routes.golden_plate_recorder_db.email_service import create_verification_code, send_verification_email

    verification = create_verification_code(email, purpose=purpose)
    return send_verification_email(email, verification.code, purpose=purpose)


def send_map_verification_scenario(email):
    from src.routes.golden_plate_recorder_db.map_routes import _create_map_verification_code, _send_map_verification_email

    verification = _create_map_verification_code(email)
    return _send_map_verification_email(email, verification.code)


def build_email_samples():
    # Resolve the same functions the website calls, after loading the server env.
    from src.routes.golden_plate_recorder_db import map_routes, password_recovery_routes
    from . import account_lifecycle, signup_notifications, startup_notifications, website_notifications

    scenarios = []

    def add(key, label, send, notification_type=None):
        scenarios.append(EmailScenario(key, label, send, notification_type))

    for purpose, label in (
        ('school_registration', 'School registration verification'),
        ('account_signup', 'Account signup verification'),
        ('account_email', 'Account email verification'),
    ):
        add(purpose + '_verification', label, partial(send_verification_scenario, purpose=purpose))
    add('map_verification', 'Map submission verification', send_map_verification_scenario)

    base_url = os.environ.get('WEBSITE_PUBLIC_URL', 'https://goldenplate.ca').rstrip('/')
    add('password_recovery', 'Password recovery', lambda email:
        password_recovery_routes.send_password_recovery_email(
            email, password_recovery_routes._recovery_link(secrets.token_urlsafe(32))))
    add('server_startup', 'Website server started', lambda email:
        startup_notifications.send_startup_notification(recipients=[email]), 'server_startup')

    school = SimpleNamespace(name='Example School', contact_email=None)
    account = SimpleNamespace(display_name='Alex Morgan', username='alex.morgan')
    registration = SimpleNamespace(
        id=str(uuid.uuid4()), school_name=school.name, school_slug='example-school',
        admin_display_name=account.display_name, admin_username=account.username,
    )

    def school_registration(email):
        request = SimpleNamespace(**vars(registration), email=email)
        return website_notifications.notify_school_registration(request, recipients=[email])

    add('school_registration', 'New school registration request', school_registration, 'school_registration')
    for invited in (False, True):
        add('invite_signup' if invited else 'account_signup',
            'Invite signup' if invited else 'Account signup request',
            lambda email, invited=invited: signup_notifications.notify_school_signup(
                school, account, invited=invited, recipients=[email]),
            'invite_signup' if invited else 'account_signup')

    def submission(email):
        # An unsaved submission uses the normal sender/attachment collector.
        # Its fresh ID cannot refer to a real submission or its uploaded files.
        return SimpleNamespace(
            id=str(uuid.uuid4()), title='School garden', email=email,
            submission_display_name=account.display_name,
            submitted_display_name=account.display_name, submitted_username=account.username,
            submitted_role='user', school_id=None, pin_id=None, status='pending',
            text_content='Students planted a garden beside the dining hall.',
            submitted_at=datetime.now(timezone.utc), approval_token=secrets.token_urlsafe(32),
            image_data=None,
        )

    add('map_submission', 'Map submission review request', lambda email:
        map_routes._notify_pending_map_submission(submission(email), base_url=base_url,
                                                  recipients=[email]), 'map_submission')
    for kind, send in (('rejection', map_routes._send_rejection_email), ('deletion', map_routes._send_deletion_email)):
        add('map_' + kind, 'Map submission ' + kind, lambda email, send=send: send(
            to_email=email, submission=submission(email),
            reason='Please provide more information about this initiative.',
            reviewer_display_name='Jordan Lee'), 'map_status')

    def lifecycle_email(email, *, event, admin=False, reason='inactivity'):
        now = datetime.now(timezone.utc)
        remaining = {'disable_14': 14, 'disable_3': 3, 'disabled': 0}.get(event, -23 if event == 'delete_7' else -29)
        disable_at = now + timedelta(days=remaining)
        details = dict(username=account.username, name=account.display_name, school=school.name,
                       manual_admin_deletion=admin, disabled_reason=reason,
                       disable_at=disable_at.isoformat(), delete_at=(disable_at + timedelta(days=30)).isoformat())
        # Use the application's URL/token format with an unissued grant ID.
        token = account_lifecycle.grant_token(str(uuid.uuid4()), os.environ.get('SECRET_KEY') or secrets.token_hex(32))
        return account_lifecycle.send_account_lifecycle_email(
            email, event, details, f'{base_url}/account-deletion#token={token}')

    for event, label in (
        ('disable_14', 'Inactivity warning: 14 days'), ('disable_3', 'Inactivity warning: 3 days'),
        ('disabled', 'Account disabled for inactivity'), ('delete_7', 'Deletion warning: 7 days'),
        ('delete_1', 'Deletion warning: 1 day'), ('deleted', 'Account permanently deleted'),
    ):
        add('lifecycle_' + event, label, partial(lifecycle_email, event=event), 'account_lifecycle')
    for key, label, event, overrides in (
        ('manual_disabled', 'Account disabled by an administrator', 'disabled', {'reason': 'manual'}),
        ('admin_delete_7', 'Admin deletion review: 7 days', 'delete_7', {'admin': True}),
        ('admin_delete_1', 'Admin deletion review: 1 day', 'delete_1', {'admin': True}),
    ):
        add('lifecycle_' + key, label, partial(lifecycle_email, event=event, **overrides), 'account_lifecycle')
    return scenarios
