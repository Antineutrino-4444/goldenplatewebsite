# reCAPTCHA v3 setup

The local implementation uses score-based reCAPTCHA v3 for the actions previously
protected by v2, account-email codes (`account_email_code`), and password recovery
requests (`password_recovery`). It does not add CAPTCHA to ordinary password login
or signed-in password management. It retains email verification and administrator
approval workflows.
Google's [v3 guide](https://developers.google.com/recaptcha/docs/v3) describes the
action and score model.

## Public key and server secret

The production public site key supplied by the site owner is saved in
`frontend/.env.production`. This file contains only the public site key, is safe
to include in the repository, and is loaded by Vite's production build.
`VITE_RECAPTCHA_SITE_KEY` exported in the build environment or set in a production
local override takes precedence; remove an obsolete v2 override or replace it
with the same v3 site key.

The corresponding secret stays only in the server's root `.env` or hosting
environment. Configure:

```dotenv
APP_ENV=production
RECAPTCHA_SECRET_KEY=your-matching-v3-legacy-secret
RECAPTCHA_MIN_SCORE=0.5
RECAPTCHA_ALLOWED_HOSTNAMES=goldenplate.ca,www.goldenplate.ca,map.goldenplate.ca
```

Do not copy a secret into a `VITE_` variable, frontend file, chat, or email.
The old v2 secret will not validate tokens from the new v3 site key.
This implementation uses Google's existing SiteVerify endpoint with the matching
v3 **legacy secret key**, rather than a Google Cloud API key. In Google Cloud,
open the key details, choose **Integration**, then **Use Legacy Key** as described
in [Google's key instructions](https://docs.cloud.google.com/recaptcha/docs/create-key-website).

Add every actual production hostname to the backend allowlist. Google must also
allow those domains in the key configuration. Only exact hostnames on the backend
list are accepted; subdomains do not automatically inherit backend authorization.
Use a separate v3 key and allowlist for staging or local testing.

## Deployment

1. Install updated frontend dependencies with `npm ci` inside `frontend/`.
2. Save the matching secret and production settings on the server.
3. Run `npm run build` inside `frontend/`; the public key is embedded in the output
   under `src/static/`.
4. Reload the hosted Flask application and deploy the built frontend together.
5. Check account signup, school email-code sending/registration, and map
   email-code sending/submission on the actual domains.

The secret is required in production: protected requests return a temporary
unavailable error if it is missing. Local development without a secret preserves
the prior optional CAPTCHA behavior; a local frontend without a public key loads
no Google script. Do not run the live website with `APP_ENV=development`.

## Implemented checks and user experience

| Endpoint | Expected v3 action |
| --- | --- |
| `/api/auth/signup` | `account_signup` |
| `/api/auth/send-verification-code` | `school_email_code` |
| `/api/auth/register-school` | `school_register` |
| `/api/map/send-verification-code` | `map_email_code` |
| `/api/map/submissions` | `map_submit` |

One shared browser loader loads Google's `api.js?render=...`. Forms show the
required Google privacy/terms attribution instead of a checkbox or image grid.
Each protected request executes its own fresh token after local validation.
Duplicate clicks are blocked while verification or the protected request runs.
Signup uses the ordinary modal again, since v3 does not open an external image
challenge. No separate React CAPTCHA package is needed.

One shared server validator checks success, Google error codes, the endpoint's
expected action, the hostname allowlist, a finite score, and a fresh timestamp.
v2 or incomplete responses cannot pass these checks. The configured minimum
score defaults to 0.5; observe scores in Google's console and adjust this setting
to the site's traffic. A low score offers retry/contact-administrator guidance.
There is no automatic v2 fallback. Timeouts, malformed responses, and quota/error
responses fail closed, including error codes paired with a successful result.

Map tokens are acquired after creating the pin and finishing image preparation,
immediately before upload. If a slow upload exceeds Google's two-minute expiry,
the server rejects it before saving a submission and asks the user to submit
again. The form retains the files and the created pin; another submit obtains a
fresh token instead of creating a duplicate pin. Uploads are not automatically
repeated. See [Google's token rules](https://developers.google.com/recaptcha/docs/verify).

Automated tests mock Google and email delivery. Run `venv/bin/python -m pytest -q`
from the project root and `npm run test:recaptcha` inside `frontend/`.
These checks do not prove the provided Google key's type, ownership, domain setup,
matching secret, billing status, or actual production score behavior. Those need
verification after deployment with the real key pair.

To roll back, restore the previous v2 application and frontend build together
with its v2 key pair. Changing only the keys cannot switch this implementation
back to v2.
