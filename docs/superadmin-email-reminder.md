# Superadmin email reminder

Purpose: invite superadmins to verify their personal account email without blocking
school administration. Reuse the existing account-email verification endpoint,
six-digit code form and account menu. School contact email remains a separate
address and reminder.

Considered: opening the verification form directly, showing an explanatory prompt
before the form, and a persistent banner linking to settings. The direct form is
chosen: it meets the requested pop-up behavior and avoids an extra step. It keeps
optional personal verification distinct from the school's contact-address task.

Use existing dialog typography, green/gold theme, borders, spacing and responsive
width. One column at narrow widths; actions may sit together on wider screens.
No new imagery or decorative assets. Native email and numeric code inputs retain
labels, loading/error/status states, focus management and Escape dismissal.

Show only for superadmins without a verified account email. Show the existing
school contact reminder first if needed, then the personal verification reminder.
Closing it dismisses it for this login in this browser tab; changing routes or
reloading does not immediately reopen it. A new login may remind again. Verified
superadmins and other roles do not receive this optional prompt. The account menu
continues to provide manual access.

Validation (October 19, 2026): the two changed components pass lint and the
production frontend build passes. Real browser checks with a synthetic superadmin
confirmed automatic opening, Not now dismissal, no reopening after reload in the
same login, manual reopening from the account menu, and successful verification
using the existing six-digit-code endpoints. Email delivery was mocked; no real
verification email was sent.

Actual screenshots were reviewed at 390, 768 and 1440 pixels wide. An independent
reviewer rated each A/B/C/D/E = 0/0/0/0/1, total 1/10 (target <=4). The one point
reflects the intentionally conventional account-verification form. No clipping or
layout blockers appeared; mobile actions stack, desktop actions share a row,
labels and keyboard focus remain visible. Existing colors and dialog conventions
were retained for continuity; decorative badges, illustrations, marketing copy
and extra confirmation steps were avoided. The close icon is visually small, but
the separate Not now button provides a clear dismissal target. Screenshots cannot
establish measured contrast or every assistive-technology interaction.
