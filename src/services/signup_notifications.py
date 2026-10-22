"""Notify a school's contact and configured website recipients of new signups."""

from .website_notifications import get_website_update_recipients, send_notification


def notify_school_signup(school, account, *, invited=False, recipients=None):
    if recipients is None:
        recipients = get_website_update_recipients()
        if school.contact_email:
            recipients.append(school.contact_email)
    title, summary, details = school_signup_content(school, account, invited=invited)
    return send_notification(title, summary, details, recipients=recipients,
                             notification_type='invite_signup' if invited else 'account_signup')


def school_signup_content(school, account, *, invited=False):
    """Shared content for real signups and sample email previews."""
    if invited:
        title = 'New account created using an invite'
        summary = ('Someone signed up for your school using an invite code. '
                   'Their account is already active; no approval is needed. '
                   'Sign in to the website to review your school’s accounts.')
    else:
        title = 'New account signup request'
        summary = ('Someone requested an account at your school. '
                   'Sign in to the website and open Account requests to review '
                   'and approve or reject the request.')
    return title, summary, [
        ('School', school.name), ('Name', account.display_name),
        ('Username', account.username),
        ('Status', 'Active (invite signup)' if invited else 'Awaiting approval'),
    ]
