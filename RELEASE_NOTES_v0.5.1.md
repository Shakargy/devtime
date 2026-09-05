# DevTime v0.5.1 - three false SUPPORTED results, fixed

An external review of v0.5.0 reproduced three cases where `dtc verify` reported
SUPPORTED with no justifying evidence. All three reproduced against the released
code. This release fixes them.

A reproducible false reassurance is still a product failure, and these were the
exact failure DevTime exists to catch: a file's *name* being treated as evidence
about the file's *behavior*.

## What was wrong

**Administrative routes reported as protected when nothing checked them.**
`src/admin/permissions.ts` containing `router.get("/admin/permissions", handler)`
reported "1 of 1 administrative route(s) show an authorization check". The
evaluator matched a combined text that included the file path, so the word
"permissions" in the filename satisfied its "permission" token. No guard existed
anywhere in the repository. This was security-adjacent and is the reason this
release exists.

**Any test sharing a word with a route counted as testing it.**
A route `GET /users` and an unrelated test named "formats users display names"
produced SUPPORTED. Imports were matched by substring, so `superusers` counted as
`users`, and different HTTP methods on one path were merged.

**A signature helper anywhere in the repository protected every webhook.**
A billing webhook handler with no verification, plus an unrelated helper that
nothing called, reported SUPPORTED.

## What changed

**Authorization must be at the route's own call site.** The route extractor now
captures each route's own arguments, so a guard is attributed to the route it
actually wraps. Guards that are imported but never applied, named in a comment,
named in a string, or applied to a different route in the same file are no
longer evidence. Authentication is distinguished from authorization:
`requireAuth` establishes identity, not permission, and is reported as such.
Guards applied by a router mount or a server-wide middleware are reported as
unresolved, never as protected. A missing signal stays WEAK, never CONTRADICTED.

**Test association requires an import.** Only a test importing a route's
implementation module can support the claim, matched on exact module stems.
Route identity keeps the HTTP method. Name similarity is now reported as an
explicit unverified suggestion that can never raise the status. The claim is
renamed in output to **Route Test Association** and its statement no longer says
"exercised by tests", because a static association is not execution coverage.

**Webhook verification is connected per handler.** A signature call must appear
in the handler's own file. Verification in an unrelated module, or inside a test
file, no longer protects production code. Mixed repositories report per-handler
counts ("1 of 2 handlers verify a provider signature").

**Routes in test, example, and fixture directories are not application
surface.** They are excluded from the route inventory rather than counted as
untested. On the Express repository this changed the inventory from 142 routes,
nearly all of them from its own `test/` and `examples/` directories, to 9.

## An honest trade-off

Removing the false positives means `route-test-association` now abstains far more
often. On three real repositories it reports zero associated routes, because
their tests exercise routes through a running server (supertest, TestClient)
rather than by importing route modules. That is the correct trade - "I cannot
establish this" is better than a false "your routes are tested" - but the claim
is less useful than its v0.5.0 numbers suggested. Those numbers were mostly
name collisions. Resolving request-based association is the next step.

## Compatibility

- The claim id `route-test-coverage` is unchanged. Only its display name and
  statement changed.
- JSON output stays `schema_version: 2`.
- No command, concept, or MCP tool was renamed or removed.
- Route signals gain `handlers` metadata and a line number; existing databases
  are re-scanned normally with no migration.

## Notes

- 157 passing tests (16 new). Every reproduction above is now a permanent
  regression test, including the adversarial cases: commented guards, unused
  imports, guards inside strings, authentication-only guards, two routes in one
  file with only one guarded, import stem collisions, and signature calls in
  test files.
- The legitimate patterns still resolve: a guard at the call site is SUPPORTED,
  a test importing its route is SUPPORTED, and a handler verifying signatures in
  its own file is SUPPORTED.
- Known gaps, unchanged by this release: router-level and application-level
  guards, verification through an imported helper, and request-based test
  association are all reported as unresolved rather than assumed.

## Names

- PyPI distribution: `devtime-ei`. Python import: `devtime`. CLI: `dtc`.
