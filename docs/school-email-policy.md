# School email rules

Admins and superadmins manage their own school's email rules from the account
menu. Rules are off by default. When enabled, an address must match an allowed
domain or an exception. Exceptions can be individual addresses or domains.
Domain matches are exact: allowing `school.edu` does not also allow
`students.school.edu`. Entries ignore case; domains are normalized to IDNA.
Exceptions permit an address but never skip email verification.

Signup requires a school code or invitation before a verification email can be
sent. Both sending and submitting check the current school rules. Verification
is tied to that school and browser, expires after five minutes, and works once.

Existing regular users need a verified, acceptable email while rules are enabled.
The required-email screen replaces the portal and offers verification or logout.
Protected server requests are also blocked until the requirement is satisfied.
Admins and superadmins are exempt from domain rules and automatic prompts.
They can voluntarily verify their own account email in the account menu.
School contact email remains a separate setting managed only by superadmins.

A superadmin can require an admin in the same school to verify their email.
This takes effect at that admin's next login, including for admins who already
have a verified address. The admin must verify again after the requirement was
issued. Existing sessions continue until their next login; superadmins cannot
use this action on other superadmins or on another school's accounts.

## Interface decisions

The three layout options considered were a task-first settings dialog, an
explanation-first section in the administration page, and a school-identity-first
panel showing the rules beside school details. The task-first dialog keeps the
three concrete controls—enable, domains, exceptions—together and matches the
existing account menu. It also keeps email verification separate from the
school's signup-notification contact address.

Use the site's existing text sizes, amber actions, borders, and dialog spacing.
Labels and examples explain exact domains and exceptions; no decorative cards,
metrics, stock images, or invented school identities are needed. On small screens,
forms and actions stack with scrollable dialogs; wider screens retain readable
form widths. The mandatory screen is a normal page with a heading and explicit
logout action, avoiding a dismissible modal and preserving keyboard navigation.

## Visual review

Reviewed local test-account screenshots at 390, 768, and 1440 pixels wide, all
900 pixels tall. The required-email page and school email rules dialog fit each
viewport, including the verification field, exception entries, and footer
actions. A separate reviewer inspected all six screenshots without the design
rationale and found no blocking layout issue.

| Screen | Width | Layout A /3 | Language B /2 | Decoration C /1 | Copy D /2 | Specificity E /2 | Total /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Required email | 390 | 0 | 0 | 0 | 0 | 1 | 1 |
| Required email | 768 | 0 | 0 | 0 | 0 | 1 | 1 |
| Required email | 1440 | 0 | 0 | 0 | 0 | 1 | 1 |
| School email rules | 390 | 0 | 0 | 0 | 0 | 0 | 0 |
| School email rules | 768 | 0 | 0 | 0 | 0 | 0 | 0 |
| School email rules | 1440 | 0 | 0 | 0 | 0 | 0 | 0 |

These subjective scores measure generic template appearance. The required-email
page uses a familiar verification form (E=1); the rules dialog directly reflects
school domains, exceptions, and administrator exemptions. Existing typography,
colors, borders, and dialog conventions were intentionally retained. Decorative
cards, gradients, badges, and fabricated claims were avoided.

Minor observations were repeated inbox guidance (subsequently condensed), the
existing small dialog close icon, and the site's standard compact controls.
Labels and keyboard controls were checked in the browser; automated routes
cover verification, logout, rule changes, permissions, and school isolation.
Screenshots use explicitly named preview accounts and illustrative example
addresses; no real school claims, testimonials, or image assets were invented.

## Validation

The full backend suite passed (801 tests, with legacy-map tests explicitly
enabled for that run). After final changes, 209 focused checks passed, including
two additional tests for internationalized domains and cross-account challenge
isolation. The frontend production build, ten reCAPTCHA client tests, and lint
for the new interface components passed.

The browser preview used isolated databases, synthetic accounts, and mocked
email delivery. It verified the member's logout option, saving school rules,
requiring an admin's email at their next login, and returning that admin to the
administration page after successful verification. No real emails were sent.
