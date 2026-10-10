# Website update notifications

The user requests automatic server startup/reload announcements, new school
registration alerts, account signup alerts (including invite signups), and map
submission alerts. Do not send code-change emails; the user removed that feature.
Website-wide recipients are
configured exclusively by `WEBSITE_UPDATE_NOTIFY_EMAILS` in the root `.env` (or
the hosting environment). Respect additions, removals, and an empty list; never
force a recipient or reinsert a removed address. Additional map reviewers are
configured by `MAP_APPROVAL_NOTIFY_EMAILS` or the Map admin UI. Account signup
alerts also go to the relevant school's stored contact email. Only superadmins
may manage their own school's contact email or see the missing-email reminder.
Do not email secrets, passwords, verification codes, or file contents. Keep
notifications honest about application startup versus public availability. Do not send
real emails from automated tests; mock the email transport. If delivery fails,
report it and preserve the completed website work.

Startup announcements are part of application initialization, including WSGI
imports. Do not add manual notification commands to deployment scripts.
