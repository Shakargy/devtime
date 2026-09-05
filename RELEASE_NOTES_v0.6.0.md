# DevTime v0.6.0 - freshness you can rely on, and honest scan state

v0.5.1 fixed results that were wrong. This release fixes results that were
*stale while claiming to be current*, which is the same failure wearing a
timestamp.

## A verified claim now goes stale when its real dependencies change

Verification recorded only the bounded list of evidence shown to a user, and
used that as the invalidation set. The two are not the same thing. Consequences,
all reproduced before being fixed:

- Editing the **test** that established a route/test association left the result
  reported as FRESH. Only route files were fingerprinted.
- **Deleting** an evidence file left the result FRESH, because the old row
  survived in the scan database and its hash still matched.
- Adding a **new route** left a claim about "all routes" FRESH, because no
  previously recorded file had changed.

Results now record a complete dependency set, separate from displayed evidence:
the handler files, the tests, the guards and helpers that justified the
conclusion, and a fingerprint of the claim's surface set. A dependency that
changed, disappeared, or was not seen by the latest scan marks the claim STALE
and names the file. A result that recorded nothing to justify it is reported as
NEEDS_VERIFICATION instead of being assumed fresh.

Precision is preserved: unrelated edits still do not invalidate anything.

## dtc verify says which snapshot it used

Verification recomputes from the last persisted scan. That is not your working
tree, and stamping a fresh evaluation timestamp on old evidence implies work
that never happened. DevTime now checks and reports the relationship:

```text
These results were computed from a scan that no longer matches your working tree.
  changed since the scan: src/billing/stripe-webhook.ts
Run dtc scan to verify against current code.
```

- JSON output gains `evidence_snapshot`: scan id, scan time, files scanned, and
  the working-tree relationship (`matches_scan`, `changed_since_scan`,
  `partially_checked`, `never_scanned`).
- The MCP `verify_claim` tool adds an explicit `staleness_warning`, because an
  agent cannot see the user's files and must be told which snapshot it is
  reasoning about and how to refresh.
- The working-tree check is read-only and bounded, so verification never turns
  into a second full scan.

## Route test association is useful again, legitimately

v0.5.1 removed the false positives but could only see imports, so it abstained
on the most common real pattern: a test that drives a running app by URL. It now
accepts a test that **requests the exact route path** (supertest,
FastAPI TestClient) as well as one that imports the implementation.

Route identity still keeps the HTTP method, so a test requesting `GET /users`
establishes nothing about `POST /users`. Name similarity remains a suggestion
that can never raise the status.

## Unresolved is not the same as untested

Routes declared relative to a router mount prefix (`APIRouter()` with
`include_router(..., prefix=...)`) have no knowable full URL. Reporting them as
"no test found" blames the repository for a gap in DevTime's analysis. They are
now reported separately:

```text
10 route(s) are declared relative to a router mount prefix that DevTime did not
resolve, so their full URL is unknown. That is a gap in this analysis, not
evidence that they lack tests.
```

## Compatibility

- The `verifications` table gains `inventory_fingerprint`, added by an
  idempotent migration. Existing rows keep NULL and are re-verified rather than
  assumed fresh. Recorded decisions and scan history are untouched.
- JSON stays `schema_version: 2`; `evidence_snapshot` and `dependency_count` are
  additive.
- No command, claim id, or MCP tool was renamed or removed.
- Test signals gain `requests` metadata; existing databases are re-scanned
  normally.

## Notes

- 173 passing tests (16 new), including every reproduction above: test edited,
  evidence deleted, new route added, unrelated change ignored, empty dependency
  set, idempotent migration, stale CLI output, stale MCP disclosure, supertest
  and TestClient association, method separation, and non-URL `.get()` calls that
  must not be mistaken for requests.
- Known gaps, reported rather than assumed: router-level and application-level
  guards, verification reached through an imported helper, dynamic request URLs,
  and unresolved mount prefixes.

## Names

- PyPI distribution: `devtime-ei`. Python import: `devtime`. CLI: `dtc`.
