# Cloudflare Turnstile migration assessment

Assessed October 20, 2026. This document records the initial investigation before
implementation. The integration has since been implemented; use the
[current setup guide](turnstile-setup.md) for configuration and deployment.

## Recommendation

Turnstile is a suitable candidate for Golden Plate. Start with a staging pilot
using **Managed** mode and `appearance: 'interaction-only'`. This normally keeps
verification out of the way while allowing an in-form checkbox when Cloudflare
requires interaction. Keep existing email verification and approval workflows.

The strongest concrete benefits are a free service with unlimited verification
requests and removing this integration's dependence on Google's score threshold
and key setup. Current reCAPTCHA v3 already runs in the background: switching is
not automatically a speed improvement or an improvement in bot detection.
Measure completion rates and verification failures before deciding to deploy.

[Cloudflare's free plan](https://developers.cloudflare.com/turnstile/plans/)
currently permits 20 widgets per account and 10 hostnames per widget, with seven
days of analytics. It can be used independently of other Cloudflare services;
changing DNS, nameservers, hosting, or enabling Cloudflare's proxy is unnecessary.
The site's three configured production hostnames fit within one widget.

## Existing implementation

The React frontend shares `frontend/src/lib/recaptcha-client.js`, exposed through
`frontend/src/lib/recaptcha.js`. It loads Google once and obtains a fresh token
for each protected request. `RecaptchaNotice.jsx` preloads the script and shows
Google attribution. Flask shares the validator in
`src/routes/golden_plate_recorder_db/recaptcha.py`.

The current protected endpoints are:

| Endpoint | Action |
| --- | --- |
| `/api/auth/signup/send-verification-code` | `account_email_code` |
| `/api/auth/account-email/send-verification-code` | `account_email_code` |
| `/api/auth/signup` | `account_signup` |
| `/api/auth/send-verification-code` | `school_email_code` |
| `/api/auth/register-school` | `school_register` |
| `/api/auth/password-recovery/request` | `password_recovery` |
| `/api/map/send-verification-code` | `map_email_code` |
| `/api/map/submissions` | `map_submit` |

Ordinary password login currently has no CAPTCHA. Adding protection there would
be separate scope. The existing validator rejects missing production secrets,
provider failures, unexpected actions/hostnames, and low or malformed scores.

## Changes required

Cloudflare's [reCAPTCHA compatibility mode](https://developers.cloudflare.com/turnstile/migration/recaptcha/)
supports up to v2. This application uses v3's `execute(siteKey, { action })`
interface, so changing the script URL and keys alone will not work.

1. **Browser client and form integration.** Replace the Google loader with the
   native Turnstile API and explicitly render widgets in React form containers.
   Resolve token requests from the success callback; handle error, expiry,
   interaction timeout, retry, unmount, and widget cleanup. Keep the existing
   action identifiers and double-submit protection. Put any interactive widget
   inside the active dialog so keyboard focus and clicks remain usable.
2. **Server validator.** Send tokens to Cloudflare, keep strict success/action/
   hostname checks, and remove Google's score validation and minimum-score
   setting. Return recoverable errors for expired tokens and fail closed for
   missing configuration, malformed responses, or provider/network failures.
3. **Naming and configuration.** Use provider-neutral helpers, errors and a
   `captcha_token` request field across JSON requests and multipart map uploads.
   Update both sides together. If old browser sessions require a transition,
   accept the old field name temporarily, but do not automatically try a second
   provider after failed verification.
4. **Attribution and deployment settings.** Replace the Google notice, update
   setup documentation, and allow Cloudflare in any hosting-level script/frame
   policy. This review found a restrictive CSP on a separate notification page,
   not a global frontend CSP; hosting headers still need checking.

[Cloudflare recommends explicit rendering](https://developers.cloudflare.com/turnstile/get-started/client-side-rendering/)
for dynamic pages and SPAs. Fetch its API script directly from Cloudflare rather
than bundling or proxying it.

The [widget options](https://developers.cloudflare.com/turnstile/get-started/client-side-rendering/widget-configurations/)
support deferred execution for multi-step forms. Give each protected action its
own widget lifecycle/action value and obtain a new token for each request. An
email-code token cannot also be used to finish signup or submit a map entry.

The [Siteverify API](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)
uses `POST https://challenges.cloudflare.com/turnstile/v0/siteverify`. Tokens
are single-use, expire after five minutes, and have a maximum length of 2,048
characters. The response includes `success`, `hostname`, and `action`; there is
no reCAPTCHA v3 score to tune. Validate the action against the endpoint's fixed
expected value and the hostname against the server allowlist.

For map submissions, retain the current order: finish image preparation and pin
creation, then acquire the token immediately before upload. Five minutes gives
more room than Google's current two-minute token window, but slow uploads can
still expire. Preserve files and the created pin on failure; a deliberate retry
must request a fresh token without duplicating the pin or upload.

## Setup needed for a pilot

Create a Turnstile widget in the owner's Cloudflare account. Authorize the actual
production hostnames (`goldenplate.ca`, `www.goldenplate.ca`, and
`map.goldenplate.ca`) and use a separate widget/configuration for staging.

Proposed configuration, not currently implemented:

```dotenv
# Frontend production build environment / frontend/.env.production
VITE_TURNSTILE_SITE_KEY=public-site-key

# Root .env or server hosting environment only
TURNSTILE_SECRET_KEY=private-secret-key
TURNSTILE_ALLOWED_HOSTNAMES=goldenplate.ca,www.goldenplate.ca,map.goldenplate.ca
```

The public key is embedded during the frontend build. The secret remains on the
server. Preserve the existing distinction between local development and production;
missing production configuration must never silently disable verification.

[Invisible mode](https://developers.cloudflare.com/turnstile/concepts/widget/)
is another option if verification must never display a checkbox. Cloudflare
requires a reference to its Turnstile Privacy Addendum in the site's privacy
policy when enabling that mode. Managed mode allows an interaction when needed;
test its behavior with the site's actual school users and browsers.

## Validation and rollout

Adapt the existing backend and browser-client tests. Cover all eight protected
endpoints, action/hostname mismatch, malformed responses, network timeout,
missing production keys, expired/replayed tokens, repeated email-code requests,
and submit retries. Mock both provider requests and the email transport so
automated tests cannot deliver real messages.

Cloudflare provides [dummy keys](https://developers.cloudflare.com/turnstile/troubleshooting/testing/)
for passing, failing, interactive, and already-spent scenarios. Use them in
isolated browser testing, with realistic mocked verification responses for the
application's exact actions and hostname rules. Do not weaken production checks
to accommodate dummy responses.

Manually verify dialogs, keyboard access, mobile Safari/Chrome, school networks,
long-open forms, and slow map uploads. Keep entered data when verification fails.
Compare completed submissions and verification failures in staging and the
initial production rollout. Better real-user completion or bot resistance has
not yet been established by this investigation.

Build and deploy the frontend with the matching server implementation and key
pair. Keep the prior reCAPTCHA build, configuration, and keys available for a
coordinated rollback. Existing tabs may need a refresh during the provider
change; request-field compatibility alone cannot validate an old Google token
with Cloudflare. Notification recipients and delivery rules remain governed by
the existing application settings.

Estimated engineering effort: **one to two focused working days**, including
automated coverage and browser QA, assuming account access and working keys.
This is a code-review estimate, not a measured implementation time. No runtime
code, environment settings, keys, or hosting configuration were changed, and no
application startup or email was triggered during the investigation.
