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
| FRESH | Evidence files are unchanged since the last verification. |
| STALE | At least one evidence file changed or disappeared. Re-verify. |
| NEEDS_VERIFICATION | The claim has never been verified in this repository. |

Freshness only tracks files that were evidence for the claim. Unrelated changes
never mark a claim stale.

NOT_APPLICABLE matters as much as the others. A repository with no billing code
is not "unknown" for a billing claim; the claim simply does not apply, and saying
so plainly is more useful than an ominous UNKNOWN.

## Built-in claims

- **route-test-coverage** (id kept for compatibility; now presented as *Route
  Test Association*) - "HTTP routes have tests that import their
  implementation." Association is established from test imports only, matched on
  exact module stems so `users` does not match `superusers`. Route identity keeps
  the HTTP method. A test that merely shares a word with a route path is reported
  as an unverified suggestion and can never raise the status. Routes defined in
  test, example, or fixture files are not application surface and are excluded
  from the inventory. A static association is not execution coverage.
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
