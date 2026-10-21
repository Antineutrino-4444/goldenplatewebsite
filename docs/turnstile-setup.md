# Cloudflare Turnstile setup

Golden Plate uses native Cloudflare Turnstile verification for account signup,
signup and account email-code sending, school registration/email-code sending,
password recovery requests, and the archived map submission/email-code flows.
Ordinary password login is unchanged. Email verification and administrator
approvals remain required where they were required previously.

## Cloudflare widget

In the [Cloudflare dashboard](https://dash.cloudflare.com/), open Turnstile and
create a widget named **Golden Plate Production** with:

- Hostname: `goldenplate.ca`. Cloudflare also authorizes its subdomains.
- Mode: **Managed**.
- Pre-clearance: disabled for this form-verification integration.

See [widget setup](https://developers.cloudflare.com/turnstile/get-started/widget-management/dashboard/)
and [hostname rules](https://developers.cloudflare.com/turnstile/additional-configuration/hostname-management/).
The application separately checks exact hostnames; authorize every deployment
hostname in the server configuration as well. Use separate widgets for staging
and production, and Cloudflare's dummy keys only in isolated development/tests.

## Keys and environment

The owner-provided public site key is stored in `frontend/.env.production` as
`VITE_TURNSTILE_SITE_KEY`. An exported frontend build variable or a frontend
production-local override can replace it. Public-key changes require a rebuild.
The root `.env` is not a source for this frontend variable.

Save the matching secret only in the root `.env` or server hosting environment:

```dotenv
APP_ENV=production
TURNSTILE_SECRET_KEY=your-matching-widget-secret
TURNSTILE_ALLOWED_HOSTNAMES=goldenplate.ca,www.goldenplate.ca,map.goldenplate.ca
```

Keep secrets out of frontend files, `VITE_` variables, chat, and email. Existing
Google settings are no longer read by this implementation. Keep the old Google
key pair available separately if rollback is needed.

Protected requests fail closed in production if the secret is missing, invalid,
or an official dummy secret. Local development with no server secret keeps the
existing development bypass; a frontend with no public key loads no provider
script. Never use `APP_ENV=development` on the live server. Production rejects
localhost/loopback hostnames even if accidentally added to the allowlist.

## Form and server behavior

The browser loads Cloudflare's script directly once per page and explicitly
renders a fresh widget for every protected request. Widgets stay inside the
active form or dialog, use Managed mode with `appearance: 'interaction-only'`,
and can show a checkbox when Cloudflare requires it. There is no floating Google
badge or Google attribution. Narrow form containers use the compact widget.

Rendering uses deferred execution. The success callback returns a token; failure,
expiry, cancellation, script timeout, or challenge timeout releases the form for
retry. Closing a dialog cancels its pending verification and removes the widget.
Each request gets a fresh token, including repeated email-code requests and the
separate signup/registration submit. A pending check cannot be replaced by a
second submit in the same form. Cloudflare's
[widget documentation](https://developers.cloudflare.com/turnstile/get-started/client-side-rendering/widget-configurations/)
describes these options.

The server submits `captcha_token` to Cloudflare's
[Siteverify endpoint](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)
and checks strict success, error codes, exact expected action, allowed hostname,
and timestamp format. Cloudflare enforces five-minute expiry and single use.
There is no Google score threshold or automatic fallback to another provider.

| Endpoint | Expected action |
| --- | --- |
| `/api/auth/signup/send-verification-code` | `account_email_code` |
| `/api/auth/account-email/send-verification-code` | `account_email_code` |
| `/api/auth/signup` | `account_signup` |
| `/api/auth/send-verification-code` | `school_email_code` |
| `/api/auth/register-school` | `school_register` |
| `/api/auth/password-recovery/request` | `password_recovery` |
| `/api/map/send-verification-code` | `map_email_code` |
| `/api/map/submissions` | `map_submit` |

Map submissions acquire their token after image preparation and pin creation,
immediately before upload. Failed/expired uploads preserve files and the created
pin. A deliberate retry gets a new token; uploads are not automatically repeated.

## Deployment and checks

1. Configure the matching secret and exact hostname allowlist on the server.
2. Build the frontend with `npm run build` inside `frontend/`.
3. Deploy the built frontend and updated Flask application together, then reload
   the hosted application normally. Startup announcements remain part of normal
   application initialization; no manual notification command is needed.
4. Test signup, school registration, account email updates, password recovery,
   and map workflows if the archived map feature is enabled. Verify actual
   production hostnames, retries, mobile layouts, dialogs, and school networks.
5. Check Cloudflare analytics for token validations and errors. Automated mocks
   do not establish widget ownership, hostname settings, a matching live secret,
   or real-browser verification behavior.

If hosting enforces a Content Security Policy, allow the Cloudflare script and
frames from `https://challenges.cloudflare.com` as described in the
[CSP guide](https://developers.cloudflare.com/turnstile/reference/content-security-policy/).

Run `venv/bin/python -m pytest -q` from the project root and `npm run test:captcha`
inside `frontend/`. Tests mock provider verification and email delivery; they
must never send real email. Browser-client coverage includes fresh tokens,
concurrent forms, duplicate clicks, retries, late callbacks, unmount cleanup,
action registration, and narrow form sizing.

For rollback, restore the previous Google frontend and server code together with
their matching Google key pair. An old browser tab's Google token cannot be
verified with Cloudflare; refresh existing tabs after the provider change.
