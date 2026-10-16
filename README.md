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
- Optional school guest privacy with persistent, unique student labels

School admins and superadmins can enable **Admin Panel → Guest privacy → Anonymize
student details for guests**. Guest history, draw candidates, winners, and draw logs
then use saved labels such as **Student 1** and **Student 2**, with separate labels
for students who share a real name. Labels follow the school's student identifiers
across sessions, roster name changes, and switching privacy off and back on.
Unlinked manual entries follow the recorder's existing identity keys.

Guest privacy hides personal IDs, grade/advisor details, individual house/clan
details, staff names, free-text notes, and session titles before sending session
data to the browser. Aggregate house scores and plate totals remain visible.
Signed-in school accounts retain their normal access. The setting starts on for
new schools and schools upgrading without a saved privacy setting. Previously
saved choices are preserved, and database upgrades happen during initialization.

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

Production builds copy Mapbox's precompiled ES modules and workers into a
versioned local asset directory. This preserves the map features while avoiding
the memory cost of bundling Mapbox again on small deployment servers. Run
`node --test frontend/tests/build/mapbox-build.test.js` from the repository root
to verify a production build with a 384 MB JavaScript heap limit.

## Development
```bash
# Run backend
python src/main.py

# Run frontend in development mode
cd frontend
npm run dev
```

## Geographic world map

The public school map is available at `/map` on the main site or `/` on the
map subdomain. For local development, use the local server address plus `/map`
(for example `http://localhost:59237/map`), or `http://map.localhost:59237/` with
the same port. The public domain continues to use its deployed build.

Mapbox GL JS renders the school map with a **Globe / Flat map**
switch. The display preference is saved in the browser and shared across map
views. Drag to move, scroll or pinch to zoom, use + / −, or reset the view.
The distance scale uses English metric units (`m` / `km`) independently of map labels.
School pins grow and turn more golden relative to the highest public session
count across all participating schools (including schools in Others). The leader
gets the largest, richest gold pin; ties share that appearance. A square-root
scale and minimum pin size keep smaller schools readable, with no fixed session
threshold. Counts include active and archived public sessions, exclude
discarded/private sessions, and appear in school lists and popups. A teal outline
marks the selected school without changing its activity colour or size. Refresh
schools to fetch updated counts and rescale the pins.
Search, school details, and Others are public. School superadmins can change
their own school's location or unmapped preference; interschool admins can
manage these choices for any active school.

Set `VITE_MAPBOX_ACCESS_TOKEN` to your Mapbox **public** token (`pk.`) in the
project's root `.env`. The frontend reads this public map token during development
and production builds. An exported build-environment value takes precedence;
root mode-specific and local environment files follow Vite's normal precedence.
If the root files omit this variable, existing `frontend/.env*` settings remain
the fallback. An explicitly empty root value disables the map. Restart Vite
after changing it; rebuild the frontend for the Python server or production
deployment. Other frontend settings, including reCAPTCHA's public site key, keep
using their existing frontend files; backend secrets stay on the server.
Without a token, the map shows a setup message while school search, lists and
details remain public. Never use a secret (`sk.`) token in the frontend.

The map explicitly uses Mapbox's **China (`CN`) worldview** and **English
labels (`en`)** worldwide. Places without an English name fall back to their
local name, rather than globally translating the map into Chinese. It uses
Mapbox Standard for Street and Standard Satellite for Hybrid/Satellite, retaining
their native boundary presentation and attribution. These settings persist
across style/projection changes and apply to location pickers too. Satellite
keeps place names and administrative boundaries while hiding roads and POIs.
The CN setting is the selected audience portrayal, not a claim of government
approval or full conformity with the supplied map-content standard; see
`docs/map-boundary-reference-review.md` for the review and its limits.
The former `VITE_MAP_STYLE_URL`, `VITE_MAP_SATELLITE_TILE_URL`,
`VITE_MAP_SATELLITE_ATTRIBUTION`, and `VITE_MAP_TILE_URL` settings are not used.

The public **Layers** menu offers **Street map**, **Satellite**, and **Hybrid**
(satellite imagery with roads and labels), plus a school-pin overlay toggle.
Every newly opened map starts in **Hybrid**, regardless of previous layer choices.
Visitors can switch layers during their visit; the school-pin visibility preference
persists in the browser. All layers work in both globe and flat mode, and switching
layers preserves the current camera and school selection without constructing
another Map object. Satellite imagery is supplied by Mapbox; the previous
Esri/OpenFreeMap layers are no longer loaded.

Get a token from the [Mapbox Access Tokens page](https://console.mapbox.com/account/access-tokens/).
Card-free trial accounts have a smaller monthly allowance and do not include
all APIs. In particular, Mapbox lists Raster Tiles API access as requiring a
payment method; check satellite access for the actual account. A payment method
enables usage beyond the free tier, which can generate charges. See the current
[trial limits](https://docs.mapbox.com/accounts/guides/signup/) and
[pricing](https://www.mapbox.com/pricing). For production, use a dedicated public
token with the public `styles:read` and `fonts:read` scopes and URL restrictions
for the site origins, including any development hostname/port where it is used.
Mapbox's CN worldview is separate from its premium Boundaries analytics product;
the latter is not needed by this implementation.

**Street View** in the Layers menu opens Google Maps for the selected school or
place, or lets anyone choose a spot on the map. It opens in a separate tab using
[Google's documented Maps URL](https://developers.google.com/maps/documentation/urls/get-started#street-view-action)
and requires no Google API key. Panorama availability is determined by Google;
there is no embedded panorama viewer or coverage overlay. Choosing a Street View
spot never changes the school's saved location. Unmapped schools are not assigned
coordinates for Street View.

The old ecological image map, submissions, photos, backgrounds, and leaderboard
are disabled, including their API endpoints, while their stored data is preserved.
`MAP_LEGACY_FEATURES_ENABLED=true` enables the archived API for maintenance and
regression tests; it does not restore the old interface on the public map route.
The new map never fetches the old image-map content.

Search a school code such as **SAC** first, or use a school name, city, or
address. Registered schools are searched before the external place database.
Schools without coordinates open in Others; their locations are never guessed.
The school-location editor resolves a known code to its school name for address search. Place search uses [Photon](https://github.com/komoot/photon) with OpenStreetMap
data, without requiring a Google or Apple API account. Searches run only when
submitted. The server caches results for 24 hours and limits uncached requests
across workers to one per second, with a longer backoff if the provider is busy.
The public Photon service has no availability guarantee; set `MAP_PLACE_SEARCH_URL`
in the backend environment to use another Photon-compatible instance.

School superadmins see a location reminder when signing in or returning to the
portal or map if their school has not made a location choice. The email reminder
appears first when both are needed. **Not now** leaves the choice pending, so
reminders continue on future visits. **Remain unmapped** saves an explicit choice
and stops location reminders. Both pending and explicitly unmapped schools appear
under **Others**, along with their approved updates, without a school location pin.

Signed-in school members can reopen **Account menu → School location** to search
and preview a location. Their school's superadmins can save a location or
choose to remain unmapped. Interschool admins use **Account menu → School
locations → School to manage**, or open **School locations** from a selected
school's public map details. Changing the selected school clears the previous
school's unsaved draft. Saving a location adds one persistent school marker;
choosing to remain unmapped removes any previously saved school coordinates.
School superadmins and interschool admins can change either choice later within
their permitted school scope. Only active schools appear, and contact
details and account information are excluded from the school-marker response.
School result pages and replacement of guest mode are subsequent steps.

The location API requires interschool admins to explicitly target an active
school with `school_id` in the query string on both reads and writes. School
accounts cannot use that parameter to access another school's editor. These
changes record the acting user and time, update the same public marker
and unmapped preference, and do not generate location reminders for interschool
admins. School contact-email permissions remain limited to school superadmins.

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

House Data shows rankings first. Scoring explanations, model assumptions, roster summaries, and calculation notes are at the bottom under **Notes and details**, collapsed by default. Superadmin record review and admin/superadmin roster matching are also at the bottom under optional **Review or exclude records** and **Match session roster** buttons. The Upper School Estimate tab shows predicted CLEAN percentages, individual 90% prediction intervals, and the probability of zero recorded participants. The main cards show the percentage estimate, individual percentage interval, rank confidence range, and a brief uncertainty label. Model limitations, category breakdowns, participation probabilities, and the separating-coverage calculation are in the collapsed notes.

Named clean, dirty, and very dirty plates count toward the student's house. House rankings default to **Estimates**, alongside Score, Count, and Clean Rate. All four views use compact house cards, with supplemental statistics under **Notes and details**. Simple scores use observed house-attributed plates: each clean plate earns +2 points, each dirty plate deducts 2 points, and each very dirty plate deducts 10 points by default. Count-only entries and records without a house contribute no simple-score points. Superadmins can set each reward or deduction to a whole number from 0 to 20 in the Admin Panel's House score settings; values are saved per school and recalculate scores for all existing sessions. Count and Clean Rate use recorded house-attributed plates; Clean Rate is clean plates divided by all recorded student plates in that house. Exact two-part house names such as `Macdonald - Flavelle` use `Macdonald`. Startup automatically updates existing student and plate house fields; uploads and new records follow the same rule. Other separators and labels with three or more sections remain unchanged.

Student CSV uploads replace the current roster for that school. Omitted students are marked inactive, hidden from roster suggestions and excluded from weighted draws and winner overrides. Historical plate records, ticket balances and draw history remain stored. Re-uploading a student restores their membership with the same ID and history. The draw and house panels refresh after an upload.

### Upper School Estimate tab

For St. Andrew's College (`default-school`), Estimates uses the saved Grades 9–12 roster for each lunch. Roster snapshots save grades alongside membership, so later uploads cannot change a populated session's eligibility. Explicitly excluded students leave that session's population once per student; excluded anonymous records remove only their observations. Faculty and identifiable records outside Grades 9–12 are omitted from this analysis. Other schools retain their existing estimate behavior without new configuration.

Identified plates and records with a known house are directly attributed. Remaining CLEAN, DIRTY, RED, and assumed-absence outcomes are allocated jointly using a multivariate hypergeometric model, preserving category totals and available house capacities. Macdonald combinations with equivalent spacing or separators normalize only within Estimates; stored houses and other ranking views are not changed. Unexpected house labels are preserved, and a plate house without an eligible population produces an explanation rather than an invented population. Missing eligibility or houses, duplicate linked students, mixed rosters, and counts exceeding population also produce unavailable messages.

A house's sole Estimate performance measure is the exact expected CLEAN percentage **conditional on at least one participant**, calculated from possible joint allocations. It is not the ratio of separately expected counts. Participants include CLEAN, DIRTY, and RED plates, excluding absences. A house with positive participation probability is ranked; impossible participation yields an unavailable percentage and no rank. Every card shows the probability of zero recorded participants. Category counts remain expected values and distinguish directly recorded from allocated plates.

Percentages use three-decimal, exact half-up rounding for ties and display. Ranking is descending by those rounded percentages, with competition ranks (1, 1, 3) and alphabetical order within ties. Overlapping intervals do not alter the expected-percentage order. A higher expected percentage does not necessarily mean a greater probability of finishing first.

Rank confidence ranges use at least **90% simultaneous model coverage** for participating houses. Each potentially participating house gets a conditional percentage interval with coverage at least 1 − 0.10/n, rounded upward on the existing 0.1% grid. A union bound covers all participating houses together without independence assumptions. The best rank counts only certainly participating houses with strictly higher intervals; the worst counts all houses whose upper endpoint exceeds the house’s lower endpoint. Exact outcome ties share competition ranks. Zero-participation houses are unranked. Coverage is unconditional across allocations, not conditional on every house participating. Ranges are conservative and do not quantify the probability that the expected-percentage order is correct.

Default percentage intervals are equal-tail **90% model-based prediction intervals**, conditional on participation, individually for each house. Exact combinatorial probabilities determine expectations and quantiles; no simulation affects ties. Discrete distributions can yield coverage exceeding the nominal level. These marginal intervals do not promise 90% simultaneous coverage across houses. Anonymous outcomes and absences are assumed exchangeable across remaining students; intervals do not cover systematic attendance, behavior, or recording biases.

**Calculate highest separating coverage** tests the 0.1% to 100% grid in 0.1 percentage-point increments, using the same conditional equal-tail distributions. Each higher-ranked house's lower endpoint must strictly exceed the next house's upper endpoint. Touching intervals overlap; ties prevent complete separation. Comparisons use exact endpoints before display rounding. Nested intervals permit a binary search equivalent to evaluating the whole grid. With fewer than two ranked houses, or no separating grid level, the control explains why a result is unavailable. This coverage is neither ranking accuracy nor probability of the ranking being correct. The control does not change the default 90% intervals, and session changes clear its result.

The updated estimator's first application startup saves a persistent activation boundary in `estimate_system_activations` for version `upper-school-clean-percentage-v1`. Sessions created before that boundary show **Estimates unavailable — this session was recorded before the updated estimation system was implemented.** Restarts do not move the boundary. Existing authorized **Use current roster** overrides remain exceptions; the override action and its access rules are unchanged. Older manual snapshots without saved grades use linked student profiles and disclose that source. Automatic sessions never reconstruct historical eligibility from later profiles.

The Estimate tab refreshes every five seconds while visible and after the existing session-change actions. During counting, unrecorded students are modeled as assumed lunch absences; the interface explains that results can change as records arrive. There is no finalization requirement or cross-session aggregation. Existing Score, Count, Clean Rate, exclusions, draw results, and session access permissions remain unchanged. Public estimate responses expose aggregate statistics only.

Superadmins can select **Review or exclude records** in House Data to review roster conflicts and exclude individual records from that session's calculations. Review uses the saved session roster when available and otherwise previews the current roster, explicitly identifying which roster is being checked. **Compare with → Current roster** previews a replacement roster without changing the session's saved match. A failed **Use current roster** attempt automatically refreshes the review against the current roster so conflicting students can be found and excluded before retrying the match. Reviewing or excluding records does not itself attest a missing historical roster; the user must retry **Use current roster**. Exclusions apply to Estimates, the original Score/Count/Clean Rate views, session and live totals, CSV exports, and student or faculty draw eligibility. A linked excluded student is also removed from that session's estimation population, rather than becoming an artificial absence. Count-only exclusions remove only that count. The student remains in the school's roster and can participate in other sessions. Ticket balances are recalculated from plate outcomes and independent ticket actions, respecting later resets and preserving balances predating ticket-event history. Affected draw selections are cleared, including a selected draw for the corrected session or its merged main session; existing public draw events and previously finalized ticket consumption remain historical records. Exclusions never delete plate records, and scan history marks them as excluded. **Restore record** includes a record again and recalculates the same values; it does not reinstate a cleared draw selection. Each change saves its superadmin, time, and optional reason. These controls are limited to the superadmin's own school, including archived sessions. Active sessions with only excluded student records follow the current roster until student recording resumes; excluded entries do not create a false mixed-roster warning.

Student CSV columns may appear in any order and header matching is case-insensitive. Only `Student ID`, `Last`, and either `Preferred` or `First` are required. If the `Preferred` column exists, its values are always used; `First` is used only when the entire `Preferred` column is absent. Rows missing an ID, last name, or the selected first name are skipped. `Grade`, `Advisor`, `House`, and `Clan` can be blank or omitted. Files must be UTF-8 (with or without a BOM); surrounding header whitespace is ignored. Duplicate recognized headers, including duplicates with different capitalization, are rejected.

Teacher CSV and TXT uploads require comma-separated columns with `Last` and `Preferred` (or `First` when there is no `Preferred` column). Headers are case-insensitive and can appear in any order. Files without these name headers are rejected without changing the roster. Include the optional `Faculty ID` column to match the same person across name changes; if included, every named row needs a nonblank ID. IDs are case-insensitive and scoped to a school. Conflicting rows for one ID are rejected. Without Faculty ID, unique full names are matched case-insensitively; ambiguous names are rejected. Separate people may have identical names when their Faculty IDs differ. Teachers retain exact first/preferred and last names, including spaces. Admins can also use **Edit name** in the teacher preview to rename an existing person without changing their permanent internal ID.

The identity migration uses the active database connection from `DATABASE_URL` (with the usual local SQLite fallback). Every initialization, including WSGI imports, checks for missing faculty identity fields and links from plate records and draws. It removes the old name uniqueness constraint so different people can share a name. Existing record, person, and draw IDs are preserved. A transactional migration marker ensures historical faculty records are linked once, only where a name uniquely identifies one person within the same school. Ambiguous or unmatched legacy records stay unlinked; later arrivals with matching names cannot claim those old records. The original recorded names, dates, plate categories, draw outcomes, and ticket figures are retained. Repeated initialization is safe. Deploying and restarting applies the migration to the configured database without a separate command or development-computer access.

Both student and teacher uploads display the loaded filename, or a database-loaded label for legacy rosters without a filename. Replacing a loaded database requires confirmation before choosing a file and a second replacement warning before upload. Faculty missing from the replacement roster are marked inactive instead of deleted, preserving their identity and historical links. They are omitted from new name suggestions and can return with the same ID. Filenames and upload metadata survive restarts, and both previews support searching the roster.

Records and draw results resolve displayed names through their linked person's permanent internal ID. Renaming a student or faculty member updates names in past history and exports without rewriting original recording snapshots or changing the winner, counts, or ticket calculations. Historical grade, house, and other recording-time facts remain unchanged; detailed export roster notes retain name changes. New named faculty recordings always link to a permanent identity, including manual entries outside the active roster. If multiple people share a name, the recorder must select a person from the suggestions rather than relying on text alone. Unlinked manual student entries and ambiguous historical names remain unresolved rather than being assigned a guessed identity. Internal faculty IDs are passed between the UI and API for selection but are not shown as names or exposed in anonymized guest views.

### Record entry and mobile navigation

Record entry appears near the top of the session page in a two-column grid. Section links jump to records, house rankings, and history. Student and teacher database administration is collapsed below the main panels. Ranking view controls and notes buttons have larger touch targets.

Closing a record dialog restores focus to its original category button without scrolling and restores the page position captured when it opened. Successful submissions refresh existing ranking and draw panels in the background without replacing them with loading placeholders. Repeated clicks or Enter presses during an active submission send only one request. A failed submission keeps the input available; uncertain network responses direct the recorder to check history before retrying. Manual entries are identified as lacking a unique roster match. Duplicate feedback identifies the plate category already saved in this session and confirms that no new plate was added. Persisted records determine duplicates; session caches update only after the database save succeeds, so failed writes cannot leave phantom entries.

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

Open **Dashboard** in the main portal to access the selected session's export controls. Signed-in users can export food waste data or the detailed record list. Session owners, draw activity authors, roster uploaders, and record authors in detailed exports display readable usernames, including for older records restored from the database. Internal account IDs remain stored for relationships and access checks; passwords remain hashed.

Admins and superadmins can open **Admin Panel → Export All Sessions** to download detailed records for any combination of their school's sessions. All sessions start selected; use individual checkboxes, **Select all**, **Select none**, or **Exclude all discarded sessions** to choose the export. Extra sessions contribute only their own records, so merged sessions are not counted twice. Individually excluded records are omitted. Choose **One CSV with session sections** for a combined file with a heading and table for each session, or **ZIP with one CSV per session** for separate files. Empty sessions retain their section or a header-only CSV; legacy count-only dirty totals appear as a count row.

Choose any combination of columns to anonymize, including first/preferred name, last name, grade, advisor, house, clan, session name/status, category, recording time, recorder, and manual-entry status. **Anonymize names**, **Anonymize all columns**, and **Keep all readable** provide shortcuts. An anonymous **Person** column groups the same student across selected sessions and distinguishes roster students with identical names. Selected name columns use person-specific labels; other selected columns preserve equal-value groups. A fresh random key creates keyed labels for each download (shared across all CSV files in a ZIP); the key and original student IDs are never exported or saved. Labels are consistent across all sessions in one export and change between downloads. Anonymizing session names also masks section headings and ZIP filenames. Blank values remain blank. Unmasked columns can still identify someone; anonymization affects only the downloaded CSV and leaves stored data unchanged.

Superadmins can exclude a session using **Discard Session** in the **Session Dashboard**. Discard and restore both show a confirmation popup describing their effect. **Restore Session** includes it again. Discard status is saved in the database and also applies to sessions discarded previously. Records, exports, and draw history remain stored. Each session, including an extra session, uses its own discard status; merging does not change that status. The live counter reflects discard/restore changes on its next automatic update.

## Future product ideas

The lightweight globe login transition is implemented. See
[landing-page.md](docs/landing-page.md) for public routes, media sources, and the
transition’s accessibility and fallback behavior.


## Public landing page and navigation

The main domain now opens the public Golden Plate landing page at `/`, including
case-study photos, initiative information, platform features, public school pins,
and YouTube, Spotify, and Instagram media. The public pages are `/about`,
`/how-it-works`, `/getting-started`, and `/stories`. Existing map subdomains keep
their map at `/`.

How it works introduces the initiative, school routine and recognition model.
Getting started is a separate, detailed website guide covering registration,
account approval, roles, student/teacher roster formats, lunch sessions, plate
recording, result review, draws, guest access and displays. It includes fictional
student and teacher CSV templates. Both pages offer initiative/website help via
Matthew Jaekel and SAC's published office contacts, with professional profile and
source links. Promotional student quotations come from owner-supplied formal
writing; the private writing archive is not published.

School accounts sign in at `/login`. `/signup` opens the account request form;
`/register` opens school registration. The school workspace lives at `/portal`,
with full-page session insights at `/portal/dashboard` and school administration
at `/portal/admin`. Inter-school accounts use `/interschool`. `/map` and
`/live-counter` remain public. Session operations and confirmations retain their
existing controls. Authentication redirects accept supported local destinations
only; guests and school roles retain the server's existing access checks.

The product preview renders the actual dashboard metrics for a random public,
non-discarded session with at least 44 total records, with a read-only guest link
to that exact session. Its
privacy rules apply even without a login. The compact community counter shows
all-time clean plates and session totals across **all schools**, including private
sessions in the aggregate, with discarded sessions excluded. It refreshes every
five seconds and opens the larger `/live-counter/community` display. Its
logarithmic ruler keeps earlier scale marks compressed at the left. The animation
resets fully offscreen and replays once the bar is comfortably back in view. No rates or
goals appear in this community counter; the existing `/live-counter` school view
retains its settings. Public destinations share a persistent header and a return
link to their source page, with reduced-motion-aware page transitions.

School pin popups, the selected-school details, and the landing globe's school
callout link to `/guest/schools/:schoolId`. This entry uses the existing
`/api/auth/guest` sign-in and post-auth initialization, then opens the normal
`/portal` as that school's Guest User. It uses the established session switcher,
guest privacy settings and read-only controls. As with guest sign-in from the
login form, this switches the browser's current account into guest mode. The
portal's School map link provides the return path.

On a fresh school-account login to the recorder, the full-screen Mapbox satellite
globe travels from the visitor's approximate IP location to the school's saved
public pin. It uses the same Hybrid basemap, English labels, and CN worldview as
the school map. The whole globe fits the viewport during a 2.8-second spherical
turn with a slow start and finish; a separate 2.4-second accelerating zoom then
fades into the recording page, already loaded underneath. The animation skips
unknown/unmapped locations, guests, inter-school accounts, reduced motion, and
deep links to other destinations. Restored sessions do not replay it. Continue or
Escape skips immediately; unavailable Mapbox configuration/WebGL also bypasses it.
Map loading has a 6.5-second deadline and the entire optional arrival is bounded
by an independent 14-second timeout.

IP orientation uses [IPWho.is](https://ipwhois.io/documentation) over HTTPS with
only success/latitude/longitude requested, credentials omitted, and no referrer.
It requests no GPS permission and sends no account information. Rounded
coordinates are cached only in page memory. A 1.2-second timeout or blocked lookup
falls back to the normal world view. The provider currently allows 1,000 free
requests per domain per day; failure or rate limiting never blocks login. The
lightweight landing-page globe continues to use local Natural Earth outlines.

Run `cd frontend && npm run build` to rebuild the Flask-served frontend, including
its public media assets. See [landing-page.md](docs/landing-page.md) for source
attribution and media verification notes.
