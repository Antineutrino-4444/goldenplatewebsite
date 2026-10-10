# reCAPTCHA v3 migration investigation

Investigated October 9, 2026. This document preserves the original migration
proposal. The v3 implementation has since been prepared locally, including the
provided production public key. See [v3 setup](recaptcha-v3-setup.md) for the
implemented behavior and required server configuration. Production has not been
deployed or verified with the matching secret key.

## Finding

A migration is feasible and would remove checkbox/image challenges from the
protected forms. v3 returns a risk score, so the application must decide what to
do with suspicious requests. It is not a package-version upgrade. Google's
[v3 integration guide](https://developers.google.com/recaptcha/docs/v3) describes
the token execution and score/action checks.

The installed `react-google-recaptcha` package explicitly implements v2. Its
`size="invisible"` option is still v2 and can still display image challenges.
Use a shared v3 script loader/token helper instead of that widget. Calling the
hosted Google JavaScript API directly would avoid adding another React dependency.

## Scope in this repository

| Form | Frontend | Backend endpoint | Proposed action |
| --- | --- | --- | --- |
| Account signup | `frontend/src/components/LoginView.jsx` | `/api/auth/signup` | `account_signup` |
| School email verification | `frontend/src/components/SchoolRegistration.jsx` | `/api/auth/send-verification-code` | `school_email_code` |
| School registration | `frontend/src/components/SchoolRegistration.jsx` | `/api/auth/register-school` | `school_register` |
| Map email verification | `frontend/src/components/MapPortal.jsx` | `/api/map/send-verification-code` | `map_email_code` |
| Map submission | `frontend/src/components/MapPortal.jsx` | `/api/map/submissions` | `map_submit` |

Normal account login currently has no captcha. Adding login protection would be
additional scope, separate from migrating existing protection.

The three server validators live in `auth_routes.py`, `interschool_routes.py`,
and `map_routes.py` under `src/routes/golden_plate_recorder_db/`. Each sends a
token to SiteVerify and accepts its `success` field. None currently checks a v3
score or action. Merely changing the keys would therefore leave the intended
v3 risk policy unenforced.

## Proposed implementation

1. Replace widget refs and reset calls with one shared asynchronous token helper.
   Generate a new token for each protected request, after local form validation.
   Disable repeated submission while obtaining a token, and give a recoverable
   error if the Google script cannot load.
2. Consolidate the three server validators. Each endpoint supplies its expected
   action; do not trust an action or score supplied by the browser. Check token
   validity, expected action, an allowed hostname, and a configurable score
   threshold. Handle invalid responses, timeouts, and quota errors explicitly.
3. Remove checkbox UI and keep the required reCAPTCHA branding visible. The
   signup dialog can resume ordinary modal behavior when running v3 because
   there is no external image challenge to interact with.
4. Configure matching frontend/backend modes so a v2 token cannot accidentally
   be evaluated as v3. Keep separate v2 and v3 key settings during rollout and
   retain a tested rollback path. Public site keys belong in the frontend build;
   secret keys or Google Cloud credentials stay on the server.

In the map flow, token acquisition currently precedes pin creation and loading
the updated pin list. Move acquisition immediately before uploading the completed
submission. Files can be large, so slow uploads also need explicit expired-token
handling. Google tokens expire after two minutes and cannot be reused; a retry
needs a fresh token. See [token restrictions](https://developers.google.com/recaptcha/docs/verify).

Vite runs from `frontend/`; the deployment scripts currently do not explicitly
load the root `.env` into its build environment. Supply the public key through
the frontend environment or an exported build variable, and verify the deployed
bundle actually enables captcha. The Flask backend loads the root `.env` separately.

## Google setup and verification API

Create a new **Score based (v3)** key, enable domain validation for the production
hosts, and use a separate staging key. Keep the working v2 key for rollback.
Google's [key creation instructions](https://docs.cloud.google.com/recaptcha/docs/create-key-website)
describe this setup and retrieving the corresponding legacy secret key.

Two integration paths are available:

- **Smaller migration:** retain the existing SiteVerify endpoint with the new
  v3 key and matching legacy secret; extend its result checks. Google continues
  to support existing integrations after [Cloud migration](https://docs.cloud.google.com/recaptcha/docs/migration-overview).
- **Modern Cloud integration:** load `enterprise.js` and use server-side
  [CreateAssessment](https://docs.cloud.google.com/recaptcha/docs/create-assessment-website).
  This adds Google Cloud project/authentication setup but supports the current
  assessment API and its explicit quota failures.

The first path involves fewer infrastructure changes for this Flask app. Decide
the path after confirming which Google Cloud project owns the site's keys and
whether the server already has suitable Cloud credentials. Account/project
configuration and production traffic were not inspected in this investigation.

## Rollout and user experience

Start by observing scores while keeping effective existing protection during
the transition. Choose thresholds using production traffic, rather than treating
one cutoff as universally correct. Keep the existing email verification and
administrator approval workflows; they provide useful additional checks.

A low score needs a defined recovery path. Possible responses include additional
email verification or a separate v2 fallback. Blocking every low score without
recovery could prevent legitimate users from registering. Email-send endpoints
also need an appropriate abuse policy; approval after registration does not
prevent abusive email sends.

Before switching production, test every action for accepted scores, low scores,
wrong action/hostname, missing or expired tokens, repeated requests, Google
failures, and rollback. Test map upload expiry separately. No browser was opened
for this investigation.

## Cost

Google currently provides 10,000 free assessments per calendar month, aggregated
per organization across accounts and sites. With billing enabled, 10,001–100,000
assessments cost a flat US$8; usage above 100,000 costs US$1 per 1,000 additional
assessments. See [current billing information](https://docs.cloud.google.com/recaptcha/docs/billing-information).
Sending an email code and submitting its form are separate assessments. The
site's actual usage is unknown, so its expected bill cannot yet be determined.

The legacy SiteVerify API can return a successful result even when the free quota
is exceeded, as documented in the [migration overview](https://docs.cloud.google.com/recaptcha/docs/migration-overview).
The shared validator should inspect error information rather than accepting
`success` alone, and quota behavior should be part of the rollout checks.
