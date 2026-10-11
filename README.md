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

### House rankings and current roster

Named clean, dirty, and very dirty plates count toward the student's house. House rankings default to the original simple **Score**, alongside Count, Clean Rate, and an optional **Estimates** tab. Simple scores use observed house-attributed plates: each clean plate earns +2 points, each dirty plate deducts 2 points, and each very dirty plate deducts 10 points by default. Count-only entries and records without a house contribute no simple-score points. Superadmins can set each reward or deduction to a whole number from 0 to 20 in the Admin Panel's House score settings; values are saved per school and recalculate scores for all existing sessions. Count and Clean Rate use recorded house-attributed plates; Clean Rate is clean plates divided by all recorded student plates in that house. Exact two-part house names such as `Macdonald - Flavelle` use `Macdonald`. Startup automatically updates existing student and plate house fields; uploads and new records follow the same rule. Other separators and labels with three or more sections remain unchanged.

Student CSV uploads replace the current roster for that school. Omitted students are marked inactive, hidden from roster suggestions and excluded from weighted draws and winner overrides. Historical plate records, ticket balances and draw history remain stored. Re-uploading a student restores their membership with the same ID and history. The draw and house panels refresh after an upload.

### Estimated house scores, dirty plates, and absences

The optional **Estimates** tab in House Data uses a session's saved student roster to allocate plates without house attribution. Named clean, dirty, and very dirty plates keep their observed house assignments. Those students are removed from the unresolved population before estimating the remaining outcomes, so known dirty plates strengthen the predictions directly. The model assumes that unresolved students are equally likely to have each remaining outcome across houses; named dirty entries are not automatically treated as a representative sample of house-specific dirty rates.

For house `h`, let `U_h` be its saved population minus all its named student plates. For any category, allocate its school-wide unattributed total in proportion to `U_h / sum(U_h)`. Add the observed category count to obtain the house's expected count. School absences equal the saved student population minus all recorded student plates. These calculations assume complete counts for one meal, one plate per present student, and no duplicate anonymous plates. Faculty records are excluded. If clean or very dirty plates are count-only, their known totals are allocated using the same conditional multivariate hypergeometric model rather than being mistaken for absences.

Only named student plate records with no resolvable house are classified as unassigned. If the saved roster supplies a missing plate house, or a linked plate supplies a missing roster house, the model uses that evidence without altering the saved roster or plate. Unassigned named records contribute to school totals, with their observed category counts exposed separately in `unassigned_record_counts`; they never appear as house entries or participate in rankings. Count-only entries remain a separate anonymous pool and are allocated across remaining students with actual houses, never to an unassigned house. Missing-house roster students without a known recorded house are excluded from house allocations; school population, recorded plate counts, clean rate, and absences still use the full saved roster. Consequently, school absences may exceed the sum of house absences. If there are no actual houses, or anonymous plate counts cannot fit the remaining population with known houses, the report retains school totals and explains why house estimates cannot be calculated rather than assigning count-only plates to a fictitious house.

Each house in Estimates shows its expected dirty count, observed and estimated components, expected absences, individual 95% model-based count ranges, and possible bounds allowed by the totals alone. Its estimated score is a range with at least **95% simultaneous model coverage across all houses**. With `H` actual houses, each score interval uses coverage `1 - 0.05/H` (a Bonferroni adjustment), so the collection has at least 95% coverage without assuming houses are independent. Estimated scores use the school's configured point values and include estimated plates. For dirty-only uncertainty, the score range transforms the adjusted dirty-count interval, reversing its endpoints because dirty plates deduct points. With other unattributed categories, the joint multivariate score distribution is calculated exactly when feasible; larger problems use conservative category projections that preserve the coverage guarantee and the dependence between outcomes. Possible score bounds are also shown separately.

In Estimates, a house has a clear ranking advantage over another house only if its score range's lower endpoint is **strictly greater** than the other range's upper endpoint. Touching, overlapping, or identical ranges confer no advantage. Each house displays a rank range: `1 + number of houses clearly ahead` through `H - number of houses clearly behind`. These are partial ranks, not a forced order based on mean scores. Houses with the same minimum rank appear alphabetically. This preserves valid pairwise advantages even when overlaps are not transitive. Estimated clean rates divide expected clean plates by expected total plates. Fractional expected counts are retained internally; the display rounds to one decimal place. All model coverage statements are conditional on the model's assumptions.

New sessions save an immutable roster snapshot, and uploads retain roster membership history. Empty active sessions follow the latest roster until student recording begins; populated sessions retain their saved version, including historical populations and houses. Re-uploading identical membership retains the same version. If additional student plates are recorded in a populated session after its roster version changes, estimates become unavailable because the session mixes roster versions. Use a new session for the new roster. Existing populated sessions without a saved historical roster show an explicit unavailable reason rather than using today's population. Mismatched membership, conflicting known houses, and counts exceeding the saved population also produce explanatory unavailable messages. Roster snapshots contain student database identifiers and house membership; public estimate responses expose only aggregate results.

School admins and superadmins can select **Use current roster** in Estimates to explicitly match the selected session (including an archived session) to their school's current student roster. This can restore estimates when historical roster data is missing or the session was flagged as mixing roster versions. The action validates the current roster against recorded students, their houses, and plate totals before saving; an inconsistent or missing roster produces an error and preserves the previous match. A successful match persists the chosen roster snapshot, the acting account, and the time, clears the mixed-roster flag, and recalculates estimated score ranges, absences, and rankings. The estimate report identifies a manual match. It does not change recorded plates, simple scores, or draw results. Later uploads preserve that matched population once the session has student records; empty active sessions still follow the latest roster. Users, guests, and inter-school accounts cannot perform manual matches, and school admins cannot match another school's sessions.

Student CSV columns may appear in any order and header matching is case-insensitive. Only `Student ID`, `Last`, and either `Preferred` or `First` are required. If the `Preferred` column exists, its values are always used; `First` is used only when the entire `Preferred` column is absent. Rows missing an ID, last name, or the selected first name are skipped. `Grade`, `Advisor`, `House`, and `Clan` can be blank or omitted. Files must be UTF-8 (with or without a BOM); surrounding header whitespace is ignored. Duplicate recognized headers, including duplicates with different capitalization, are rejected.

Teacher CSV uploads require only `Last` and `Preferred` (or `First` when there is no `Preferred` column). Headers are case-insensitive and can appear in any order; other columns are ignored. Teachers are stored as the selected first name followed by their last name, preserving name capitalization. Rows missing either name are skipped. Teacher TXT uploads still accept one full name per line without a header. Teacher names are matched and deduplicated case-insensitively.

Both student and teacher uploads display the loaded filename, or a database-loaded label for legacy rosters without a filename. Replacing a loaded database requires confirmation before choosing a file and a second, irreversible-replacement warning before upload. Teacher CSV/TXT uploads replace only that school's teacher name list; historical plate records and draw logs stay stored. Filenames and upload metadata survive restarts, and both database previews support searching names across the whole roster.

### Draw finalization and email preferences

Faculty winners can be finalized separately from student winners. Finalization persists across restarts. Repeating a finalized student or faculty draw requires confirmation, and all selections and finalizations remain in the public draw log. Superadmin overrides use the explicit `override` method and log type.

Every outgoing email includes a private **Unsubscribe or manage notification preferences** link. No login is required. Recipients can choose server restart announcements, school registration requests, account requests, invite signups, map review alerts, and map decisions, or unsubscribe from all notifications. Preferences persist in the database and are enforced by the shared email delivery service. Requested verification codes remain deliverable and include the same management link. Links use `WEBSITE_PUBLIC_URL` from the environment; recipient lists remain controlled by the existing environment settings and school contact/map settings.

## Live clean-plate counter

Open `/live-counter` (or use **Live counter** in the main portal) to see a school's clean-plate count, clean percentage, and total plates for a saved time range. A large numbered progress bar tracks the animated count toward the school's milestone, with the goal, progress percentage, and remaining plates shown together. Without a milestone, the main bar shows clean plates out of total plates. A separate bar shows the clean-plate percentage. After a milestone is exceeded, the goal portion compresses as the scale grows with the count. A contrasting segment shows extra plates, separated by a clear milestone line and labeled with the exact excess. The counter always includes both students and faculty, including count-only entries. Clean percentage is student clean plus faculty clean plates divided by all clean, dirty, very dirty, and faculty records in the range. Active, archived, and extra sessions count, with each plate counted once. Discarded sessions are excluded from both the clean count and total count, so the percentage and milestone progress update too.

Admins and superadmins can use **Manage time ranges** to choose a calendar year, reporting timezone, and up to three custom ranges. Custom names are optional; unnamed ranges display their dates. Only superadmins can change the default time range. The configured default is always the leftmost tab and is selected when the page opens. Viewers can switch among saved ranges but cannot edit them or change the student/faculty scope. Settings are stored separately for each school.

Guests must enter a school code first and see only public sessions for that school. Signed-in school users can view all their school's recorded sessions. The page refreshes automatically every five seconds, retries temporary connection failures, and shows when its data is stale.

Superadmins can choose **Count** or **Percentage** as the default main view in **Manage time ranges**. Its tab opens selected on the left; viewers can switch locally. Each view has its own school-specific celebration milestone: a whole clean-plate count or a percentage from 0.1 to 100 with one decimal place. Leaving a goal blank disables celebrations for that view. The main bar and celebration follow the selected view; percentage excess is labeled in percentage points. The selected range's main number animates from zero on load, moving quickly at first and slowing toward the total. Crossing the milestone launches confetti and a dismissible celebration banner, including on every reload after the goal is reached and when live updates reach it. Unchanged updates do not replay the celebration. Reduced-motion preferences skip the count animation and confetti while keeping the milestone banner.

Only superadmins can customize their school's celebration banner title, message, and closing line in **Manage time ranges**. Blank fields restore the default wording. The optional `{milestone}` placeholder inserts the formatted goal number, including % for percentage goals. Banner text is plain text; messages can include line breaks. Admin range edits preserve these settings.

**Full screen** fills the screen with the selected main progress panel, an enlarged number and bar, and its school and time range. Live updates and celebrations continue. The exit control is hidden until the pointer comes within 64 pixels of any screen edge (or the control receives keyboard focus). Use **Exit full screen** or Escape to return. Browsers without native fullscreen support use a full-window display.

Live changes animate the clean count, total count, and percentage toward their new values, with a subtle upward motion on each update. Main numbers stay bright white during updates and turn gold with a brief pulse and glow when the selected goal is reached. The main panel, goal badge, goal card, and bar gradually shift from deep blue through teal to green as animated progress approaches the selected milestone, keeping the reached colour after exceeding it. The progress bars move alongside the animated numbers. Reduced-motion preferences display the updated values immediately.

Date ranges include both endpoints and use each plate's saved recording timestamp, converted to the reporting timezone (Eastern Time by default). Day boundaries handle daylight saving time. For historical imports, results depend on the recording timestamps preserved by the import; a missing original timestamp may have been replaced with the import time.

Superadmins can exclude a session using **Discard Session** beside **Switch Session** in the main portal. Discard and restore both show a confirmation popup describing their effect. **Restore Session** includes it again. Discard status is saved in the database and also applies to sessions discarded previously. Records, exports, and draw history remain stored. Each session, including an extra session, uses its own discard status; merging does not change that status. The live counter reflects discard/restore changes on its next automatic update.
