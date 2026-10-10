# Golden Plate Recorder

## Overview
Golden Plate Recorder is a web application for tracking student attendance and category-based events. The system combines a Flask backend with a modern React frontend and supports barcode scanners, CSV roster uploads, and role-based administration.

## Features
- Multi-role authentication system (Super Admin, Admin, User, Guest)
- Invite-only registration and account deletion workflow
- Session creation and switching with default names
- CSV roster upload with ID and name matching
- CLEAN, DIRTY, and RED category recording with barcode scanner support
- Real-time history display and CSV export
- Administrative panel for user, invite code, and session management

## Architecture
- **Backend:** Flask 3 with SQLAlchemy and SQLite located in `src/`
- **Frontend:** React 19 with Vite and Tailwind CSS located in `frontend/`
- **Tests:** Pytest suite in `tests/`

## Prerequisites
- Python 3.11+
- Node.js 18+
- npm or pnpm

## Installation
```bash
# Clone repository and enter directory
# python -m venv venv
# source venv/bin/activate  # or venv\Scripts\activate on Windows
cp .env.example .env
pip install -r requirements.txt

cd frontend
npm run build
cd ..

# Start the application
python src/main.py
```

## Development
```bash
# Run backend
python src/main.py

# Run frontend in development mode
cd frontend
npm run dev
```

## Testing
```bash
pytest
```

## Password management

Signed-in users open the account menu in the portal or map header and choose **Change password**.
Superadmins and inter-school administrators open the account menu and choose **Manage passwords**, with tabs for
their own password and for resetting another account. Normal users and school
admins can change only their own password. Superadmins can manage passwords for
users and school admins in their own school, but cannot change or reset another
superadmin's password. Inter-school administrators can reset accounts across schools,
including other administrator accounts. Search accounts by username, name, or school.

Administrators can either set a custom password or choose **Reset to default: 114514**
under **Other accounts**. The server chooses the fixed default when this option is
selected. Each action requires the acting user's current password. Custom passwords
must contain 6–256 characters, with confirmation in the form. Passwords are stored as hashes
and are never returned by the account list. Reset passwords must be shared with
the account holder securely. Changing your own password keeps the current device
signed in; other sessions become invalid. An administrator reset invalidates all
of the target account's existing sessions. Sessions created before this feature
was deployed also need to log in again once to establish the password binding.
No database migration is required.

The seeded superadmin password now applies only when creating or migrating the
default account; startup preserves an existing account's changed password even
in development mode. The server-side credential scripts remain available for
recovery if an administrator cannot log in.

## Website update emails

Set all website-wide recipients in the root `.env` file:

```dotenv
WEBSITE_UPDATE_NOTIFY_EMAILS=matthew.jaekel@sac.on.ca,another@example.com
MAP_APPROVAL_NOTIFY_EMAILS=
```

Add, change, or remove comma-separated addresses without editing code, then
restart/reload the server. Hosting environment variables take precedence over
`.env`, so update those instead if configured by your host. These recipients
receive pending school registration requests, map submissions, account signup
alerts (including invite signups), and server startup/reload announcements.
An empty or missing `WEBSITE_UPDATE_NOTIFY_EMAILS`
disables website-wide alerts; no address is included automatically.

`MAP_APPROVAL_NOTIFY_EMAILS` configures additional map reviewers. A non-empty
list saved in the Map admin recipient editor overrides those additional reviewers,
while website-wide recipients still receive map alerts. To remove a recipient
completely, remove it from every configured list, including any saved Map admin
list. The editor shows the active recipients. With both environment lists empty
and no saved map reviewers, no map notifications are sent. Duplicate addresses
receive only one email per notification.
School alerts include the school, applicant email, requested code, and administrator
name/username; passwords and email verification codes are never included.

Notifications use the existing `BREVO_API_KEY` and `BREVO_SENDER_EMAIL` settings.
Set `WEBSITE_PUBLIC_URL` to set the website link in emails. Failed delivery is logged
and does not discard a saved registration request or stop a running website.

Startup announcements now run automatically after the application initializes,
including direct starts of `src/main.py` and WSGI imports after a hosting reload.
No notification command or deployment wrapper is needed. Delivery runs in a
background thread when the host permits threads, otherwise during initialization.
It announces application startup, not a verified build or public availability.
The development reloader parent is skipped; its serving child announces startup.
Each initialized process sends once; multi-worker hosts can send an announcement
per worker. Set `WEBSITE_STARTUP_NOTIFY_ENABLED=false` to disable these announcements.
Code-update emails and the manual notification scripts have been removed.
Automated tests mock
email delivery and never send real messages.

## School contact email and account signup alerts

Each school has a contact email. Approval of a new school registration copies the
verified signup email into that field. Existing approved registrations are matched
to schools during the schema upgrade; only unambiguous matches with valid emails
are copied, and existing contact emails are preserved.

Superadmins whose school has no contact email see an **Add a school contact email**
dialog after signing in (including the map portal). It stays open until they save
an address or explicitly close it. Closing dismisses the current reminder; it can
appear again on the next login/page load until an address is saved. Superadmins
can reopen **School contact email** from the account menu to update it. Users, admins, guests, and inter-school
controllers do not see this dialog and cannot edit school contacts. Each superadmin
can update only their own school, and contact addresses are not exposed in public
school details or ordinary user sessions.

Successful account signup requests notify the school's contact email and the
configured website-wide recipients, deduplicated. The message asks school
superadmins to sign in and open **Account requests** to approve or reject the
request. Invite signups also notify them but correctly state that the account is
already active and needs no approval. Passwords, hashes, and invite codes are never
included. Invalid or duplicate requests send no alert, and delivery failure does
not undo a saved request or account. An empty website-wide recipient list does not
disable signup notifications to an existing school contact.

## reCAPTCHA

The frontend now uses score-based reCAPTCHA v3 for account signup, school
registration/email-code sending, and map submission/email-code sending. Each
request obtains a fresh token. The server verifies its action, hostname, score,
expiry, and Google error codes; ordinary login is unchanged.

The supplied public site key is stored in `frontend/.env.production` and is
included by the production frontend build. Save its matching v3 **legacy secret
key** as `RECAPTCHA_SECRET_KEY` in the server's root `.env` or hosting environment.
Keep that secret out of frontend files. Set `APP_ENV=production`, configure
`RECAPTCHA_ALLOWED_HOSTNAMES`, and optionally adjust `RECAPTCHA_MIN_SCORE`
(default 0.5). A missing secret blocks protected requests in production.

Deploy the new frontend build and server together with the matching v3 key pair.
Existing v2 keys are incompatible with the new code. See the
[v3 setup guide](docs/recaptcha-v3-setup.md) for exact configuration, deployment,
score handling, upload retries, and rollback. The earlier
[migration investigation](docs/recaptcha-v3-migration.md) is retained as historical
background. Production key verification still requires the matching secret and
a deployment on the configured domains.

## Passwords and Environment Mode
The app has a built-in development super admin account for local setup:
- Username: `greenguys`
- Password: `begreendogood`

This default login is only meant for development. Environment mode controls whether it works:
- `APP_ENV=development` enables the built-in development login and shows a warning banner in the site.
- `APP_ENV=production` disables the built-in development login. Set this on the live server.

Before switching a live site to production mode, make sure a real admin account exists with a known strong password. To change an existing account username or password, run:
```bash
venv/bin/python scripts/change_user_credentials.py
```

The `SECRET_KEY` value is separate from user passwords. It secures Flask session cookies and should be a long random string in production. Keep it stable after deployment; changing it logs users out but does not change database passwords.

## License
This project is released under the MIT License.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## Support
For questions or feedback, please open an issue in this repository.

## Optional plate names

Clean, Dirty, Very Dirty, and Faculty Clean all accept an optional name (or student ID for student plates). Leave the field blank to add one unnamed plate to the category count. Repeated blank entries each add one; they appear as “count only” in history and exports and do not earn or reset anyone’s draw tickets. Only named faculty entries can be picked for the faculty draw. Named Dirty entries preserve the student information and contribute to their house statistics, without changing draw tickets.
