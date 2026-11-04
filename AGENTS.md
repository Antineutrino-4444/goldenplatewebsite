# Website update notifications

The user requests new release note emails, new school registration alerts,
account signup alerts (including invite signups), and map submission alerts.
Send release notes to admin and superadmin account email addresses and the
addresses in `WEBSITE_UPDATE_NOTIFY_EMAILS`. Deduplicate those addresses
case-insensitively. That setting in the root `.env` or hosting environment
configures all additional website-wide recipients. Respect additions, removals,
and an empty list. Additional map reviewers are
configured by `MAP_APPROVAL_NOTIFY_EMAILS` or the Map admin UI. Account signup
alerts also go to the relevant school's stored contact email. Only superadmins
may manage their own school's contact email or see the missing-email reminder.
Keep notification content to the applicable event or published release entries.
Do not email secrets, passwords, verification codes, or unpublished file contents.
Mock the email transport in automated tests. If delivery fails, report it and
preserve the completed website work.

Check for new releases as part of application initialization, including WSGI
imports. Keep the complete release history public. Do not send startup or
code-change emails or add manual notification commands to deployment scripts.
