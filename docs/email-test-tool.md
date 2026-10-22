# Server email test tool

Run from the server's checkout:

```bash
venv/bin/python scripts/test_emails.py
```

Open the browser form using the address printed by the script. Enter the
recipient email and the server access key printed in the terminal, complete
CAPTCHA, and select **Send all test emails**. The results page updates while
the batch runs. Keep the script running until the batch finishes.

The tool binds to `127.0.0.1:59238` and uses a separate process from the website.
Starting it does not start the website's startup-notification or account
lifecycle workers. It does not add a testing route to the public website.

## Configuration and browser access

The script loads the root `.env` without replacing hosting environment values.
It uses the same `BREVO_API_KEY` and `BREVO_SENDER_EMAIL` as the website. Set
`TURNSTILE_SITE_KEY` to the public site key paired with `TURNSTILE_SECRET_KEY`.
`VITE_TURNSTILE_SITE_KEY` in the root environment is also accepted as a fallback.
The script does not read the frontend's separate build environment files.

CAPTCHA is mandatory even in development: missing secrets and Cloudflare's dummy
test secrets cannot send mail through this tool. The widget's domain must match
the browser URL and `TURNSTILE_ALLOWED_HOSTNAMES`; the token must have action
`email_test`. Use real Turnstile credentials. A deployment's existing widget can
be used if it allows the hostname used to open this tool.

For a production server, proxy the form over HTTPS on an allowed website
hostname. For example, run:

```bash
venv/bin/python scripts/test_emails.py --url-prefix /email-test --secure-cookie
```

An Nginx location can preserve that prefix:

```nginx
location /email-test/ {
    proxy_pass http://127.0.0.1:59238;
    proxy_set_header Host $host;
}
```

Then open `https://goldenplate.ca/email-test/`. Adapt the hostname to your own
deployment. An SSH tunnel to localhost alone is insufficient for production
CAPTCHA because the production verifier rejects localhost hostnames. Do not
change the production application's environment to development to work around
this. On a local development installation, a real widget that allows localhost
can be used with development hostname settings.

The server access key is generated on each launch. To use a fixed key, set
`EMAIL_TEST_ACCESS_KEY` to a long random value. It is entered in the form, never
included in URLs or emails, and is not the website login password. Another
browser cannot read your batch results without the session that started it.

Only one batch may run at a time, with a five-minute minimum between starts
across recipients and restarts. A second script process using the same audit
database is refused. Use `--port` to change the local port.

## Email coverage

The current batch has 21 samples:

- School registration, account signup, account email, and map verification.
- Password recovery.
- Server startup, school registration requests, account signup requests, and
  invite signups.
- Map review requests, rejections, and deletions.
- Account inactivity warnings at 14 and 3 days, inactivity disabling, deletion
  warnings at 7 and 1 days, and completed deletion.
- Manual disabling and the two admin deletion-review reminders.

These use the website's shared renderers. Subjects start with `[TEST]` and each
body has a test banner. Names and records are explicitly sample data. Verification
templates contain `SAMPLE`, not a valid code. Action links use `example.invalid`;
they cannot reset passwords, approve maps, or delete accounts. Samples do not
include attachments, uploaded images, real account data, secrets, or file contents.
This tests template rendering and email delivery; it does not exercise the real
registration and account workflows or attachment delivery.

Delivery goes only to the entered recipient. The tool does not change or send
to `WEBSITE_UPDATE_NOTIFY_EMAILS`, map reviewers, or school contact addresses.
Existing notification preferences remain in effect: opted-out types appear as
**skipped**. Re-enable the desired types using the recipient's existing
notification-preferences link if you want those samples delivered. Shared email
delivery may create/update that recipient's preference record and appends the
normal preferences link. No accounts, requests or submissions are created.

## Saved send times and outcomes

The private SQLite audit file defaults to `data/email_test_runs.sqlite3`. Use
`--database /persistent/path/email-tests.sqlite3` if the hosting filesystem is
ephemeral. The log records the recipient, batch ID, email type, attempt time,
completion time, accepted/sent time, status, and provider message ID. All times
include a UTC timezone offset. It does not store email bodies, CAPTCHA tokens,
access keys, passwords, or provider response bodies.

**Accepted** means Brevo accepted the request; `sent_at` records when the server
received that acceptance. It does not certify delivery into the inbox. Failed
and skipped messages have no `sent_at`. Review the inbox/spam folder or Brevo's
delivery logs to investigate subsequent delivery or bouncing.

Print the latest 50 saved batches and their individual results without sending:

```bash
venv/bin/python scripts/test_emails.py --history
```

Use the same `--database` option when inspecting a custom log path. Individual
failures do not stop the remaining samples. No mail is sent unless the audit
entry can be saved first. If a process stops during delivery, restarting marks
the in-flight message **unknown** and remaining queued messages **cancelled**.
An unknown result may already have been accepted by Brevo; inspect the provider
logs before running another batch. The tool never retries automatically.

## Verification

Automated tests mock Brevo delivery and CAPTCHA responses. They cover recipient
isolation, all current categories, mandatory CAPTCHA and action/hostname checks,
access keys and form tokens, timestamp persistence, partial failures, disabled
notification types, cross-session privacy, concurrent cooldown reservations,
and interrupted runs. They send no real email.
