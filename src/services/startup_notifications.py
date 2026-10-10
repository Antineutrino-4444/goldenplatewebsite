"""Announce application startup without a deployment command or email on requests."""

import logging
import os
import threading

from .website_notifications import notify_website_update

logger = logging.getLogger(__name__)


def start_startup_notification(app, *, reloader_parent=False):
    """Send one announcement per initialized process, in the background if possible.

    The Werkzeug reloader parent does not serve requests, so only its child
    announces startup. WSGI imports also call this after configuring the app.
    """
    enabled = os.environ.get('WEBSITE_STARTUP_NOTIFY_ENABLED', 'true').strip().lower()
    if app.testing or reloader_parent or enabled in {'0', 'false', 'no', 'off'}:
        return None
    process_id = os.getpid()
    if app.extensions.get('startup_notification_pid') == process_id:
        return None
    app.extensions['startup_notification_pid'] = process_id

    def send():
        try:
            notify_website_update(
                'Website server started',
                'The website application has initialized after a server start or reload. '
                'This announcement does not verify public website availability.',
                [('Environment', os.environ.get('APP_ENV', 'development'))],
            )
        except Exception:
            logger.exception('Unable to send server startup announcement')

    worker = threading.Thread(target=send, name='startup-notification', daemon=True)
    try:
        worker.start()
    except RuntimeError:
        # Some WSGI hosts disallow background threads. They still get an
        # automatic announcement; mail failure must not prevent app startup.
        logger.warning('Background threads unavailable; sending startup announcement directly')
        send()
        return None
    return worker
