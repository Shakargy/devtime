# DevTime v0.1.3 - the Cal.com fixtures

A fixture-driven release. DevTime was run against Cal.com (5,736 files scanned in
about 5 seconds), and every wrong or missing output from that run became a
regression fixture and a fix. No cloud, no telemetry, no AI, no code execution
added.

## What the Cal.com run found

- **Background Jobs was under-called.** Cal.com's custom Tasker (InternalTasker,
  RedisTasker, task-processor) is real background-job behavior, but only
  BullMQ-style patterns were recognized. Fixed: custom task-runner infrastructure
  (task-runner classes, enqueue and task-processing verbs) now produces behavior
  evidence. Cal.com: low -> medium with worker evidence.
- **Admin Permissions was missed entirely.** Next.js Pages Router API files
  (`pages/api/**`) produced no route signals, so Cal.com's admin surface was
  invisible. Fixed: Pages Router API routes are now extracted. Cal.com: not
  detected -> medium with route evidence.
- **The honest refusal is now guarded by a fixture.** Cal.com's community edition
  ships `pages/api/stripe/webhook.ts` as a handler that always returns 404
  ("not available in community edition"). DevTime correctly refused to confirm
  Billing Webhooks there. New rule: a disabled-endpoint stub (a handler whose only
  behavior is a 404/501 response) is not route behavior and cannot confirm a
  concept. Billing Webhooks on Cal.com stays hedged, as it should.

## New fixtures

- `tasker-is-background-jobs` - a custom task runner earns Background Jobs with
  behavior evidence (and never the weak "not established" wording).
- `pages-api-admin-is-admin-permissions` - Pages Router admin API routes earn
  Admin Permissions with route evidence.
- `stub-404-webhook-not-billing` - a 404-stub webhook named stripe/webhook.ts must
  NOT confirm Billing Webhooks.

## Also in this release

- Fixed a scan performance regression found during development: a backtracking
  regex took the Cal.com scan from ~4s to 135s; final scan time is ~5s.
- 107 passing tests (3 new fixtures).

## Names

- The PyPI distribution is `devtime-ei`. The Python import package remains
  `devtime`, and the CLI command remains `dtc`.

## Try it

```bash
pipx install devtime-ei
cd your-repo
dtc init
dtc scan
dtc concepts
```

If DevTime gets something wrong on your repository, open an issue: wrong outputs
become fixtures, and fixtures are how this tool earns trust.
