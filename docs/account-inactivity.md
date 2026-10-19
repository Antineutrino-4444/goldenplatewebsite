# Inactive accounts

Tracking begins November 1, 2026 at midnight in America/New_York. Older login
history is clamped to this baseline. Accounts created later start at creation;
successful sign-in or recovery restarts their clock. Mere page activity does
not count as a fresh sign-in.
Existing installations with the earlier October baseline move forward to this
date automatically on application startup.

* Without a verified email: disable after 60 days without sign-in.
* With a verified email: disable after 120 days without sign-in.
* Disabled ordinary members are deleted after 30 days in the disabled box.
* Admins can be disabled but are never automatically deleted. Their 30-day date
  is a review date; the owner or a school superadmin must explicitly confirm.
* School superadmins and the inter-school control account are protected from
  this cleanup. Manually disabled ordinary accounts also get 30 days in the box;
  historical disabled accounts start that window when first processed.

School admins and superadmins can recover accounts in their own school's
disabled box, including admin accounts. Recovery revokes existing deletion
links and restarts the full 60/120-day clock. Disabled owners cannot open the
portal. They can use a deletion-only sign-in to delete themselves.

Verified owners receive reminders 14 and 3 days before disablement, on
disablement, 7 and 1 day before deletion/review, and after deletion. For an
unverified account, only disablement, the one-day warning, and deletion are sent
to school superadmins with verified addresses and WEBSITE_UPDATE_NOTIFY_EMAILS.
The configured website list is respected, including an empty list. No reminder
backlog is sent if the server was offline through earlier milestones.

Every notice has a deletion link. Links require the owner's username and
password, then two distinct confirmation buttons. Visiting the page or an
email scanner opening a link cannot delete an account. A superadmin can start
the same confirmation workflow from the disabled box using their own credentials.
Ordinary members and admins can also start self-deletion from their account menu.
No approval is needed for an owner deleting their own account.

Login credentials and account signup data are deleted. School sessions, plate
records, and their audit history remain, with the former author labelled
"(deleted)" through a non-login record identity. A later account with the same
username is distinct and cannot be targeted by an old deletion link.

The application starts an hourly maintenance worker during initialization,
including WSGI imports, with a database lease to coordinate multiple workers.
The worker checks its persistent notification queue each minute. Failed mail is
recorded and retried; it does not undo completed account work. Hosts must allow
background threads and keep an application process running. No deployment
notification or cleanup command is required. ACCOUNT_LIFECYCLE_WORKER_ENABLED=false
disables the worker for isolated tests; tests mock mail delivery.

## Interface direction

Options considered: a task-first disabled box beside account management, an
explanation-first timeline of upcoming milestones, and a school overview with
account totals. The disabled box was selected because staff need to identify a
person, see the recovery/deletion deadline, and recover the account in one place.
Following the October 19 layout request, Disabled Accounts is a button beside
Export All Sessions, Generate Invite Code, Delete Requests, Manage Accounts, and
Account Requests. It opens a dedicated scrollable dialog with recovery actions.
Compared with an inline expansion or separate navigation page, the dialog matches
the existing account-management flow and keeps the main administration page compact.
It uses the existing administration forms and typography; no invented totals,
decorative charts, cards, or marketing copy are needed. Rows stack on narrow
screens; the deletion page uses a readable form width with explicit step labels,
credential fields, cancellation, and a final destructive action.

## Verification and visual review

The actual disabled box and deletion credential screen were reviewed at 390,
768, and 1440 pixels using isolated synthetic accounts. An independent screenshot
review rated the archive A/B/C/D/E = 0/0/0/0/0 (0/10) at all three widths, and the
deletion form 0/0/0/0/1 (1/10) at all three widths: its narrow credential form uses
familiar account-screen conventions. Scores describe visual patterns, not authorship.
The review identified missing timezone labels; these were added and checked at
all three widths. No layout blockers remained. Existing green controls, restrained
borders, and typography were retained for consistency; no decorative metrics,
stock imagery, or generic marketing sections were added. The account names in
preview screenshots are synthetic test fixtures, not production users.

Browser checks covered admin recovery, account-menu self-deletion, fresh credential
entry, and both confirmation screens. Automated tests perform final deletion with
synthetic accounts and real foreign-key enforcement, verify retained sessions and
plate records, fixed deadlines, protected roles, cross-school permissions, reminder
deduplication, failed-mail retries, recipient removal, stale-login races, password
changes, schema upgrades, and baseline persistence. All test email delivery is mocked.

Final validation: 830 backend tests passed, the production frontend build passed,
and the new deletion/archive components passed lint. The backend suite retains an
existing Requests dependency-version warning. Automatic maintenance requires a
running application process with background-thread support, as described above.

October 19 follow-up: the production build and all 76 frontend tests pass after
moving the disabled list into its own dialog. The updated dialog and button-grid
screenshots are unverified: automatic approval review could not run due to model
capacity, preventing local backend preview startup and browser testing. The scores
above refer to the earlier inline layout, not the new dialog.

The separate school entrance animation now uses a 1,400-ms accelerating dive to
zoom 18, native map dots and the restored fade into the portal.
The HTTP playback preview has since been checked in the browser at phone, tablet
and desktop widths. See [school-arrival.md](school-arrival.md)
for its current timing, loading safeguards, visual review and validation; those
animation checks do not change the admin-dialog review status described above.
