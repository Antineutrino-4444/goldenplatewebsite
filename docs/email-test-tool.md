# Server email test tool

Run from the server's checkout over SSH or its terminal:

```bash
./scripts/test_emails.sh
```

The script asks for a recipient and then requires you to type
`SEND recipient@example.com`, using the exact address displayed, before sending.
It prints each email's result, UTC time, provider message ID or failure reason,
and a final summary. It saves those results on the server. No browser, web port,
reverse proxy, Turnstile keys, or separate access key is needed for terminal mode.

You can also provide the recipient as an argument; confirmation is still required:

```bash
./scripts/test_emails.sh --email recipient@example.com
```

The shell launcher finds the checkout's `venv/bin/python` or `.venv/bin/python`,
falling back to `python3`. You can also run the Python script directly:

```bash
venv/bin/python scripts/test_emails.py
```

Starting the terminal tool does not start the website, a browser form, the
startup-notification worker, or the account lifecycle worker. It does not add a
testing route to the public website. Terminal mode uses the operator's existing
server access plus explicit confirmation. This confirmation is not CAPTCHA;
Cloudflare Turnstile requires a browser and is used only in optional web mode.

Terminal exit codes are `0` for completion (including preference skips), `1` for
delivery failures, an active batch, cancellation, or another run error, `2` for invalid
arguments or recipient input, and `130` for interruption during sending. Failures
do not erase successful sends. Pressing Ctrl+C stops subsequent emails and records
an interrupted in-flight send as unknown, without automatically retrying it.

## Email configuration

The script loads the root `.env` without replacing hosting environment values.
It uses the same `BREVO_API_KEY` and `BREVO_SENDER_EMAIL` as the website.

Only one batch may run at a time. You can start another immediately after the
previous batch finishes, including after failures or an interruption. Terminal
and web mode share the same log. A second process using the same audit database
is refused.

## Optional browser mode

The earlier browser tool remains available explicitly with `--web`:

```bash
./scripts/test_emails.sh --web
```

Only this mode binds to `127.0.0.1:59238`. Enter the recipient and the server
access key printed in the terminal, complete CAPTCHA, and select **Send all test
emails**. The results page updates while the batch runs. Keep the script running
until the batch finishes. A browser on another computer can access a properly
configured HTTPS proxy; the server itself does not need a desktop browser.

For web mode, set `TURNSTILE_SITE_KEY` to the public site key paired with
`TURNSTILE_SECRET_KEY`.
`VITE_TURNSTILE_SITE_KEY` in the root environment is also accepted as a fallback.
The script does not read the frontend's separate build environment files.

In web mode CAPTCHA is mandatory even in development: missing secrets and Cloudflare's dummy
test secrets cannot send mail through this tool. The widget's domain must match
the browser URL and `TURNSTILE_ALLOWED_HOSTNAMES`; the token must have action
`email_test`. Use real Turnstile credentials. A deployment's existing widget can
be used if it allows the hostname used to open this tool.

For a production server, proxy the form over HTTPS on an allowed website
hostname. For example, run:

```bash
./scripts/test_emails.sh --web --url-prefix /email-test --secure-cookie
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

Use `--port` together with `--web` to change the local browser port.

## Email coverage

The current batch exercises 21 email scenarios:

- School registration, account signup, account email, and map verification.
- Password recovery.
- Server startup, school registration requests, account signup requests, and
  invite signups.
- Map review requests, rejections, and deletions.
- Account inactivity warnings at 14 and 3 days, inactivity disabling, deletion
  warnings at 7 and 1 days, and completed deletion.
- Manual disabling and the two admin deletion-review reminders.

Each scenario calls the same email-sending function used by the corresponding
website event. The script leaves the subject, HTML body, formatting, and normal
preferences footer unchanged. It adds no subject prefix, banner, or timing text
to the email. Timing and delivery results stay in the terminal and audit log.

The four verification scenarios call the normal code-creation services and then
pass the generated codes into the normal email senders. Codes are saved in the
website/map verification tables with the usual expiry and attempt rules. The
normal service replaces older matching pending challenges when another code is
created. No fixed verification text is used. These email-level calls do not
create a browser signup or account-email session.

Other events use fictional school/account/submission inputs with the production
send functions. They do not create a school request, change an account's status,
or approve/delete a submission. URLs use the configured website address and the
normal URL format. Recovery, deletion and map-approval tokens in these scenarios
are unissued; they do not authorize changes to a live account or submission.
Map scenarios use the normal attachment collection path for an unsaved submission
with no images. No uploaded files or file contents are emailed.

Delivery goes only to the entered recipient. The tool does not change or send
to `WEBSITE_UPDATE_NOTIFY_EMAILS`, map reviewers, or school contact addresses.
Existing notification preferences remain in effect: opted-out types appear as
**skipped**. Re-enable the desired types using the recipient's existing
notification-preferences link if you want those types delivered. Shared email
delivery may create/update that recipient's preference record and appends the
normal preferences link. Verification records are created; accounts, school
requests and map submissions are not.

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
./scripts/test_emails.sh --history
```

Use the same `--database` option when inspecting a custom log path. Individual
failures do not stop the remaining scenarios. No mail is sent unless the audit
entry can be saved first. If a process stops during delivery, restarting marks
the in-flight message **unknown** and remaining queued messages **cancelled**.
An unknown result may already have been accepted by Brevo; inspect the provider
logs before running another batch. The tool never retries automatically.

## Verification

Automated tests mock Brevo delivery and browser CAPTCHA responses. They cover
terminal prompts, explicit confirmation, recipient arguments, terminal progress,
exit codes, interrupted sends, immediate repeat runs, preference skips, and saved history.
Browser mode tests cover mandatory CAPTCHA and action/hostname checks, access
keys and form tokens, and cross-session privacy. Shared tests cover recipient
isolation, all current categories, timestamp persistence, partial failures, and
concurrent batch reservations. They send no real email.

For every scenario, tests also check that the production sender is called and
that its complete outgoing payload matches a direct call with the same inputs.
Verification tests check calls to the real generators and confirm the emailed
codes match the saved verification records. Only the external mail transport is
mocked for these checks.
