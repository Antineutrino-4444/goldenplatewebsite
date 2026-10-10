# Website update notifications

The user requests email notifications to `matthew.jaekel@sac.on.ca` for website
code updates and deployments, as well as new school registration requests and
map submissions.

After completing and checking a set of website code changes, send one concise
summary using the existing Brevo configuration:

```sh
venv/bin/python scripts/notify_website_update.py --kind code-change --summary "Describe the changes and checks. State that they are prepared locally and have not been deployed."
```

Use the environment's Python interpreter if `venv/bin/python` is unavailable.
Do not email secrets, passwords, verification codes, or file contents. Keep
notifications honest about local preparation versus deployment. Do not send
real emails from automated tests; mock the email transport. If delivery fails,
report it and preserve the completed website work.

Both deployment scripts notify after the server responds successfully. For an
external deployment pipeline, call the same notification script with
`--kind deployment` only after its own deployment/readiness checks pass.
