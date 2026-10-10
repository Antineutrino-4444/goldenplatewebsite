"""Notify a school's contact and configured website recipients of new signups."""

from .website_notifications import get_website_update_recipients, send_notification


def notify_school_signup(school, account, *, invited=False):
    recipients = get_website_update_recipients()
    if school.contact_email:
        recipients.append(school.contact_email)
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
    return send_notification(title, summary, [
        ('School', school.name), ('Name', account.display_name),
        ('Username', account.username),
        ('Status', 'Active (invite signup)' if invited else 'Awaiting approval'),
    ], recipients=recipients)
