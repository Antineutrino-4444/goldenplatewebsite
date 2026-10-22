"""Side-effect-free samples of the website's current email templates."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


@dataclass(frozen=True)
class EmailSample:
    key: str
    label: str
    subject: str
    html: str
    notification_type: str | None = None


def build_email_samples():
    # Import only when the operator starts a batch, after loading the server env.
    from src.routes.golden_plate_recorder_db.email_service import render_verification_email
    from src.routes.golden_plate_recorder_db.map_routes import (
        render_map_verification_email, render_map_deletion_email,
        render_map_rejection_email, render_pending_map_email,
    )
    from src.routes.golden_plate_recorder_db.password_recovery_routes import render_password_recovery_email
    from .account_lifecycle import _notice_html
    from .signup_notifications import school_signup_content
    from .website_notifications import render_notification

    samples = []

    def add(key, label, content, notification_type=None):
        samples.append(EmailSample(key, label, *content, notification_type))

    for purpose, label in (
        ('school_registration', 'School registration verification'),
        ('account_signup', 'Account signup verification'),
        ('account_email', 'Account email verification'),
    ):
        # SAMPLE is not a verification code and has no stored challenge.
        add(purpose + '_verification', label, render_verification_email('SAMPLE', purpose=purpose))
    add('map_verification', 'Map submission verification', render_map_verification_email('SAMPLE'))
    inactive_link = 'https://example.invalid/email-test'
    add('password_recovery', 'Password recovery', (
        'Golden Plate - Reset your password', render_password_recovery_email(inactive_link)))
    for key, title, summary in (
        ('server_startup', 'Website server started',
         'Sample application initialization announcement. Public website availability has not been checked.'),
        ('school_registration', 'New school registration request',
         'A sample school has requested registration and is awaiting administrator approval.'),
    ):
        add(key, title, ('Golden Plate — ' + title, render_notification(
            title, summary, [('School', 'Sample school (email test)')], url=inactive_link)), key)
    school = SimpleNamespace(name='Sample school (email test)')
    account = SimpleNamespace(display_name='Sample person', username='email-test-sample')
    for invited in (False, True):
        title, summary, details = school_signup_content(school, account, invited=invited)
        key = 'invite_signup' if invited else 'account_signup'
        add(key, title, ('Golden Plate — ' + title, render_notification(
            title, summary, details, url=inactive_link)), key)

    now = datetime.now(timezone.utc)
    submission = SimpleNamespace(
        id='email-test-sample', title='Sample ecological map submission',
        email='sample@example.invalid', submission_display_name='Sample person',
        submitted_display_name='Sample person', submitted_username='email-test-sample',
        submitted_role='user', school_id='sample-school', status='pending',
        text_content='Sample description for email testing.', submitted_at=now,
        approval_token='SAMPLE-INACTIVE',
    )
    add('map_submission', 'Map submission review request', render_pending_map_email(
        submission, pin_label='Sample map location', public_base='https://example.invalid',
        image_descriptions=()), 'map_submission')
    for kind, render in (('rejection', render_map_rejection_email), ('deletion', render_map_deletion_email)):
        add('map_' + kind, 'Map submission ' + kind, render(
            submission=submission, reason='Sample reviewer comment for email testing.',
            reviewer_display_name='Sample reviewer'), 'map_status')

    details = dict(username=account.username, name=account.display_name, school=school.name,
                   manual_admin_deletion=False, disabled_reason='inactivity',
                   disable_at=(now + timedelta(days=14)).isoformat(),
                   delete_at=(now + timedelta(days=44)).isoformat())
    for event, label in (
        ('disable_14', 'Inactivity warning: 14 days'), ('disable_3', 'Inactivity warning: 3 days'),
        ('disabled', 'Account disabled for inactivity'), ('delete_7', 'Deletion warning: 7 days'),
        ('delete_1', 'Deletion warning: 1 day'), ('deleted', 'Account permanently deleted'),
    ):
        title, html = _notice_html(event, details, inactive_link)
        add('lifecycle_' + event, label,
            ('Golden Plate — ' + title, html), 'account_lifecycle')
    for key, label, event, overrides in (
        ('manual_disabled', 'Account disabled by an administrator', 'disabled', {'disabled_reason': 'manual'}),
        ('admin_delete_7', 'Admin deletion review: 7 days', 'delete_7', {'manual_admin_deletion': True}),
        ('admin_delete_1', 'Admin deletion review: 1 day', 'delete_1', {'manual_admin_deletion': True}),
    ):
        title, html = _notice_html(event, {**details, **overrides}, inactive_link)
        add('lifecycle_' + key, label,
            ('Golden Plate — ' + title, html), 'account_lifecycle')
    return samples
