# Email login and password recovery

Superadmins retain their existing exemption from school email domain restrictions.
School rules apply to ordinary users. Account email login accepts only verified
addresses, case-insensitively, with the account's password. Exact usernames remain
supported; a shared email needs the username to identify one account. Development
seed-password restrictions, inactive-account handling and session binding still
apply through either identifier. No verification code authenticates a login.

Password recovery starts from Forgot password on the login screen. Considered a
single form with implicit sending, a separate explanatory screen, and a compact
dialog with explicit confirmation. The confirmation dialog is chosen because the
user requested a pause before sending and wants users to consider a superadmin's
existing password-reset ability first. It provides that advice, the account field,
an explicit checkbox, and an alternative exit. It uses existing labels, typography,
colors and responsive dialog/actions; no decorative imagery or new visual system.
The reset-link page is a plain password/confirmation form, followed by a login link.

Only active accounts with an already verified email receive a recovery link.
Requests require explicit confirmation and the password_recovery reCAPTCHA action.
Unknown, unverified, disabled and ambiguous accounts receive the same response.
Each account can receive one message per minute, at most three per hour. The link
expires after 20 minutes and is single-use. Tokens use 32 random bytes; only their
SHA-256 hashes are stored. The URL token stays in a fragment and is posted to the
API, rather than sent in a query string. WEBSITE_PUBLIC_URL determines the link
origin (HTTPS except local previews); the request Host header is never used.

The reset is bound to the verified address and current password fingerprint.
Changing the address/password, disabling/deleting the account, or using/replacing
the link invalidates it. Token consumption and password replacement share one
transaction with conditional updates. Existing sessions lose their password token.
Recovery never creates a session: the owner must sign in with the new password.
Recovery records are removed during permanent account deletion.

## Review and validation

The actual confirmation dialog and reset-link form were reviewed at 390, 768 and
1440 pixels wide on October 19, 2026. Independent screenshot scores (A/B/C/D/E)
were 0/0/0/0/0 for each confirmation viewport, and 0/0/0/0/1 for each reset-form
viewport; the conventional reset form is intentionally reusable. Both meet the
<=4/10 target, with no visual blockers. Labels and actions fit, mobile dialog
actions stack, and the superadmin alternative is visible. No decorative badges,
marketing cards, fake metrics or invented visual assets were introduced. Existing
branding and dialog/form conventions were retained for continuity and recognition.
The initial viewport captures were taken during resizing and were replaced with
settled captures before the final review. Screenshot review cannot establish
measured contrast or every assistive-technology behavior.

Browser checks confirmed verified-email/password login into the actual portal,
the explicit recovery confirmation, mocked email dispatch, and a real reset link
opening the password form. Automated tests complete the credential change, verify
old-session revocation, password-only login, expired/used/replaced links, email and
password changes, disabled/deleted accounts, ambiguous email addresses, cooldowns,
reCAPTCHA, delivery/commit failures, and concurrent password changes. Browser
checks do not change passwords; automated tests use isolated synthetic accounts.
No real email is sent by either test workflow. Production delivery uses the
existing mail transport and production reCAPTCHA configuration.

The three changed login/recovery UI components pass lint. The production frontend
build passes; App.jsx retains two existing hook-dependency lint warnings. All 80
frontend tests pass. The full backend run exposed an existing map-notification
test that omitted the now-required legacy-map feature flag; its fixture now sets
that flag explicitly without changing runtime map access policy.

Final result: all 871 backend tests pass, including 41 new email-login/recovery
checks; all 80 frontend tests and the production build pass. The backend retains
an existing Requests dependency-version warning. No runtime map feature flag was
changed by the test-fixture correction.
