# Email test tool interface review

This visual review records the initial browser interface. The tool now defaults
to the terminal, calls production email senders without modifying their messages,
and generates verification codes through the normal services. The earlier
screenshots show historical copy and should not be used as current behavior
documentation; see [Email test tool](email-test-tool.md).

## Direction

This is an operator tool for one recipient, a CAPTCHA check, and a durable log
of 21 email samples. The important domain details are notification preferences,
UTC acceptance timestamps, provider message IDs, and partial delivery failures.

Three layout directions were considered: a form first with a separate results
page; a log first with the send form beside it; and a template catalogue with
the recipient form below it. The form-first direction was selected because the
operator must enter one recipient and complete CAPTCHA before any results exist.
A dedicated results page then gives the full batch room without mixing completed
delivery records with an active send form.

The system uses Golden Plate's green and gold, system text at 16px, restrained
3px form corners, visible focus outlines, and simple row dividers. Desktop logs
use a table; phone logs stack email type, outcome and the two timestamps for
each entry. There are no decorative assets, gradients, repeated feature cards,
oversized hero text, stock photos, or fabricated activity metrics. Familiar
form controls and a table are intentionally retained for this operator task.
All example names and delivery records in preview screenshots are sample data.

## Screenshot review

Reviewed October 22, 2026 against the actual standalone Flask tool running with
temporary databases and a disabled email transport. Screenshots cover both the
form's missing-CAPTCHA configuration state and a results page with simulated
accepted, failed and skipped outcomes. No real email or real CAPTCHA completion
was used in the browser preview.

Saved screenshots are `email-test-form-{390,768,1440}.png` and
`email-test-results-{390,768,1440}.png` in the chat's visualization directory.

| Viewport | A: layout /3 | B: visual /2 | C: decoration /1 | D: copy /2 | E: specificity /2 | Total /10 |
| --- | --- | --- | --- | --- | --- | --- |
| 390px | 1 | 0 | 0 | 0 | 0 | 1 |
| 768px | 1 | 0 | 0 | 0 | 0 | 1 |
| 1440px | 1 | 0 | 0 | 0 | 0 | 1 |

The nonzero layout score reflects the conventional single-column form. Colors
follow the existing project; there is no ornamental residue. Copy and structure
address actual email categories, CAPTCHA setup and acceptance semantics. These
are subjective self-review scores, not evidence of human authorship. No separate
visual reviewer was used.

The initial review identified cramped timestamps on phone screens, internal
event keys in sample labels, and empty CAPTCHA space when configuration was
missing. Those were revised and the screenshots reviewed again. Final phone
rows show labeled timestamps side by side; tablet timestamps wrap at the date
boundary; desktop logs retain the full table. The branding-swap and decoration
checks found no marketing sections or visual additions unrelated to testing
email delivery. The page remains a focused email-operations form.

## Verification and limits

Targeted automated checks cover the send workflow, recipient isolation, access
key and form validation, mandatory CAPTCHA, hostname and action validation,
timestamp persistence, provider failures, preferences, consecutive runs, concurrency,
restart handling, proxy mounting, history output, and existing mail behavior.
The browser review checked responsive layout, labels, visible status text and
timestamps. Form controls have associated labels, keyboard focus styles, and
48px primary buttons; outcomes have visible text in addition to color.

Live Turnstile validation and real inbox delivery require the server's real
credentials and the recipient entered by the operator. Attachments and real
account/map mutations are deliberately excluded from the sample batch. Real
map-decision attachment forwarding is covered separately with a mocked mail
transport. The existing requests dependency warning remains unrelated to this
change.
