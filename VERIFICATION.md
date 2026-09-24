# Claim verification (experimental)

DevTime is evolving into the verification layer for repository understanding:
the layer developers and coding agents use to know whether a statement about a
repository is actually supported by evidence.

A claim is a statement about the repository. Verification evaluates it against
scanned evidence and answers with a status, evidence, both-sided contradictions,
missing evidence, coverage limitations, and freshness.

## Try it

```bash
dtc init
dtc scan
dtc verify
```

List built-in claims and their freshness:

```bash
dtc verify --list
```

Machine-readable output:

```bash
dtc verify billing-webhook-signature --json
```

## Statuses

Statuses describe what the repository evidence supports, per DevTime's
verification rules. They are not formal proof, runtime certainty, or a security
guarantee.

| Status | Meaning |
|--------|---------|
| SUPPORTED | Required behavior evidence exists in the current scan. |
| WEAK | The claim's surface exists, but the proving evidence is missing. |
| CONTRADICTED | Credible evidence conflicts with the claim. Both sides are always shown. |
| UNKNOWN | The surface exists, but coverage cannot responsibly decide. |
| NOT_APPLICABLE | The repository has no surface this claim is about. |

## Freshness

Freshness is separate from truth. A claim can be SUPPORTED and STALE at the
same time: the last verification supported it, but its evidence changed since.

| Freshness | Meaning |
|-----------|---------|
| FRESH | Every dependency is unchanged since the last verification. |
| STALE | A dependency changed, disappeared, or the claim's surface set changed. |
| NEEDS_VERIFICATION | Never verified here, or nothing was recorded to justify it. |

Freshness is computed from a claim's **dependencies**, which are not the same as
the evidence displayed to you. Displayed evidence is a bounded selection; the
dependency set is complete and includes the test files, guards, and helpers that
justified the conclusion. A claim about a set (for example "all routes") also
depends on that set, so a newly added route invalidates it even though no
recorded file changed.

Only a claim's own dependencies participate, so unrelated edits never mark it
stale. A result that recorded no dependencies is reported as
NEEDS_VERIFICATION rather than assumed fresh.

NOT_APPLICABLE matters as much as the others. A repository with no billing code
is not "unknown" for a billing claim; the claim simply does not apply, and saying
so plainly is more useful than an ominous UNKNOWN.

## Built-in claims

- **route-test-coverage** (id kept for compatibility; now presented as *Route
  Test Association*) - "HTTP routes are referenced by tests that request or
  import them." Two evidence levels are accepted: a test that requests the exact
  route path (supertest, FastAPI TestClient), or a test that imports the route's
  implementation module, matched on exact module stems so `users` does not match
  `superusers`. Route identity keeps the HTTP method, so a GET test establishes
  nothing about POST on the same path. A test that merely shares a word with a
  route path is reported as an unverified suggestion and can never raise the
  status. Routes declared relative to an unresolved mount prefix are reported as
  unresolved rather than untested. Routes defined in test, example, or fixture
  files are excluded from the inventory. A static association is not execution
  coverage.
- **admin-authorization** (v0.5) - "Administrative routes require an
  authorization check." Authorization is established only from a guard applied at
  the route's own call site. Authentication is not authorization: `requireAuth`
  establishes identity, not permission. Guards that are imported but unused,
  named in a comment, named in a string, or applied to a different route in the
  same file are not evidence. Guards applied by a router mount or a server-wide
  middleware are reported as unresolved, never as protected. A missing signal is
  WEAK, never CONTRADICTED.
- **billing-webhook-signature** - "Incoming billing webhooks verify the payment
  provider's signature." Verification is connected per handler: a signature call
  must appear in the handler's own file. A helper elsewhere in the repository -
  even one nothing calls - does not protect a handler, and a call inside a test
  file does not protect production code. Mixed repositories report per-handler
  counts.
- **jwt-authentication** (v0.3) - "Authentication uses JWT access tokens."
  Includes the documentation-vs-implementation detector: documentation claiming
  JWT while the only JWT usage found is invitation/verification tokens is a
  both-sided contradiction. Documentation with no usage at all is WEAK, not
  contradicted: absence is not positive conflicting evidence.

Example contradiction, found in the wild: Cal.com's community edition ships
`pages/api/stripe/webhook.ts` as a handler that always returns 404 ("not
available in community edition"). The file name claims webhook handling; the
implementation is a disabled stub. `dtc verify` reports CONTRADICTED with both
sides and exact paths.

## Diff impact (v0.4)

`dtc risk --diff` now reports which verified claims a diff destabilizes:

```
Claim impact:
  - billing-webhook-signature (previous status: SUPPORTED)
      changed evidence: src/billing/stripe-webhook.ts
      re-verify: dtc verify billing-webhook-signature
```

Only a claim's recorded evidence files count. A diff touching unrelated files
never flags a claim, and nothing is printed when no verified claim is affected.

## The report card (v0.5)

`dtc verify` leads with what it can actually say about your repository:
findings first (contradictions before everything else), then a compact list of
claims that do not apply and why.

When no claim applies, DevTime does not dead-end. It reports what it scanned,
what evidence it collected, what would make a claim verifiable, and states
plainly that this is a coverage limit rather than a verdict on your code.

## Scan freshness (v0.6)

Verification recomputes conclusions from the last persisted scan, which is not
the same thing as your working tree. When the two disagree, DevTime says so
before showing any result:

```text
These results were computed from a scan that no longer matches your working tree.
  changed since the scan: src/billing/stripe-webhook.ts
Run dtc scan to verify against current code.
```

JSON output carries the same facts under `evidence_snapshot` (scan id, scan
time, files scanned, and the working-tree relationship), and the MCP
`verify_claim` tool adds an explicit `staleness_warning` so an agent that cannot
see your files is told which snapshot it is reasoning about.

## Change review (v0.7)

`dtc review` answers the question a reviewer actually has: what did this change
do to what the repository can support?

```bash
dtc review --base origin/main
```

```text
DevTime review
  base   origin/main  (merge base 579e524da402)
  head   HEAD  (ea436921979e)
  scope  .   2 file(s) changed

Regression: admin-authorization  SUPPORTED -> WEAK
  base: 1 of 1 administrative route(s) have an authorization guard at their own call site.
  head: 1 of 2 administrative route(s) have an authorization guard at their own call site.
  changed evidence: src/admin/panel.ts
  missing now: Authorization evidence for: GET /admin/export (src/admin/panel.ts)
```

How it works:

- It compares **merge-base..head**, the same range a pull request's "Files
  changed" tab shows. Commits added to the base branch after the head branched
  are not attributed to the change.
- Both commits are extracted with `git archive` into a temporary directory that
  DevTime creates and removes. Your working tree, index, branch, worktree list,
  and `.devtime/` are never touched. No repository code is executed.
- Every built-in claim is verified at both commits, and each claim gets one
  transition: `regression`, `newly_applicable`, `no_longer_applicable`,
  `improvement`, `evidence_changed`, or `unchanged`. Unchanged claims are only
  counted, so a review does not repeat itself on every run.
- Run from a subdirectory, it reviews that subdirectory, just as `dtc scan`
  scans the current directory.
- Each commit is scanned with the ignore rules committed at that commit. When
  the change itself edits `.devtimeignore` or `.gitignore`, the review says so
  (`scan_policy_changed` in JSON, plus a warning): a transition may then reflect
  a change in what DevTime scans rather than in what the code does.

Output formats: `--format text` (default), `--format json`, and
`--format markdown` for a GitHub job summary. `--json-out PATH` writes the JSON
report as well, whatever format is printed.

Exit codes:

| Code | Meaning |
|------|---------|
| 0 | The review ran. Findings do not change this: reviews are advisory. |
| 1 | The review could not run (unknown ref, shallow clone, failed snapshot scan). |
| 7 | A claim regressed, only when `--fail-on-regression` is passed. |

A review that could not run never looks clean: it exits 1 and says why. The
most common cause in CI is a shallow clone, which cannot provide the merge base.

### Using it in GitHub Actions

```yaml
name: devtime-review
on:
  pull_request:
permissions:
  contents: read
jobs:
  devtime:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install "devtime-ei==0.7.0"
      - run: |
          dtc review --base "origin/${GITHUB_BASE_REF}" \
            --format markdown --json-out devtime-review.json >> "$GITHUB_STEP_SUMMARY"
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: devtime-review
          path: devtime-review.json
```

Pin the version so a DevTime upgrade cannot change results between two runs of
the same pull request. Use `pull_request`, not `pull_request_target`: DevTime
needs only read access and no secrets.

## Trust model

- Deterministic and rule-driven. No AI, no network, no code execution.
- A contradiction always shows both sides with provenance.
- Missing evidence is reported explicitly, with coverage limitations.
- Verification results are stored locally in `.devtime/` with evidence
  fingerprints so staleness can be detected.
- The MCP tool `verify_claim` computes results without persisting anything;
  the MCP server stays read-only.

## Limitations

- Heuristic scanner: evidence comes from static patterns, not execution.
- Signature verification is recognized for known provider patterns
  (e.g. Stripe `constructEvent`); custom schemes may not be detected.
- Four built-in claims. User-defined claims are deliberately not
  supported yet: the claim model must earn trust before it grows a
  configuration language.
- Coverage follows scanner language support; see [LIMITATIONS.md](LIMITATIONS.md).

## Where this is going

Next candidates, in order: language coverage beyond the current TypeScript and
Python focus (Go repositories currently produce no routes at all), more built-in
claims over well-covered domains, and machine-readable claim impact in risk
output. User-defined claims come after built-in claims prove trustworthy on real
repositories.
