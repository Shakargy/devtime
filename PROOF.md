# DevTime - PROOF

Evidence that DevTime V0 does what it claims, on a demo repo and on real
repositories - plus an honest account of where it is still weak. Everything here is
local: AI off, cloud off, telemetry off, no code execution, no network.

## 1. Current version

- Version `0.0.7` (private prerelease; `0.1.0` is reserved for the first public
  release). Tag timeline: `v0.0.1-proof` → `v0.0.2-reality` →
  `v0.0.3-public-candidate` → `v0.0.4-private-review-candidate` →
  `v0.0.5-private-review-ready` → `v0.0.6-trust-repair` →
  `v0.0.7-evidence-precision` (this one).
- Tests: **passing** (`pytest`) - unit, integration, and fixture suites (count grows
  each precision patch; see the suite for the current number).

### Trust Repair (v0.0.6) - from private reviewer feedback

Private reviewers ran DevTime on large real repos (Langfuse, Cal.com, Open WebUI,
Plane, Twenty) and found trust-breaking output. v0.0.6 makes DevTime *more honest*,
not larger:

- **Risk review never lies.** Explicit states `review_failed` / `no_findings` /
  `unsupported_change_class` / `finding`. A git failure is `review_failed`. A known
  file changed with no matching rule is `unsupported_change_class` (manual review),
  not "no findings". Comment-only diffs are not behavior changes.
- **JWT algorithm weakening** (`HS256`/`ES256` → `none`) in an auth file is flagged
  **high** severity.
- **Billing Webhooks false positives fixed** by file-local provider/billing evidence:
  calendar subscriptions, generic webhooks, credential webhooks, and repo-wide Stripe
  deps no longer become Billing Webhooks.
- **Word-sense gates**: `session_id` traces, `NEXTAUTH_URL`, invitation JWTs, job
  *titles*, avatar *URLs*, and model *downloads* no longer inflate concepts.
- **Strength-aware claims**: low-confidence concepts say "Possible … signals detected"
  instead of contradicting themselves with "is present" + "presence not confirmed".
- **Decisions must be corroborated** to clear uncertainty/raise the score.
- **Understanding Score** (higher = better) is shown as a number; **Understanding
  Debt** is a label. Unsupported freshness points were removed.
- **Context Packs** refuse to be authoritative for weak concepts and cap/rank/justify
  recommended tests.
- **Closed ontology disclosed** (six families). **Framework coverage warnings** for
  Django/NestJS. **MCP `start`** no longer pretends to start a server. Bracketed paths
  render literally. Scan prints progress and a boundary report.

> The Billing false-positive *class* is reduced and fixture-guarded, not declared
> universally solved - heuristics can still err on unseen patterns.

### Evidence Precision (v0.0.7) - after the v0.0.6 re-review

Narrow precision patch (no new features); package version moved to `0.0.7` (still
private; `0.1.0` reserved for public release):

- **Billing Webhooks now needs a local payment provider.** Calendar subscriptions,
  cron cleanup, connector/credential webhooks, and generic triggers are negative
  contexts - they do not become Billing Webhooks without local Stripe/PayPal/payment
  evidence. (Cal.com-style false positives.)
- **High-confidence Authentication requires direct auth evidence.** `session_id`
  traces, `NEXTAUTH_URL` permalink tests, and authorship/capitalization words are
  filtered out as word-sense pollution before they can drive headline evidence.
  (Langfuse-style.)
- **Context Pack reasons are truthful.** "Same module" is now "same directory" and
  only shown with real path locality; tests that import the implementation say so
  ("imports or tests the implementation"); weak keyword candidates are labeled weak.
- **Employment job-title/role taxonomy never becomes Background Jobs** (Twenty-style).
- **Direct `bg_tasks` tests attach to Background Jobs** with an import-based reason,
  instead of "no behavior-specific tests found" (Plane-style).

After a Codex narrow re-review found the first pass overfit to synthetic fixtures,
v0.0.7 was hardened with **real-path regression fixtures** and stricter evidence
sense-filters:

- Billing evidence itself is sense-filtered: calendar/credential/connector/cron/
  generic-trigger webhook signals are dropped from Billing Webhooks unless a local
  payment provider (Stripe/PayPal) is present - verified with the exact Cal.com paths
  (`api/cron/calendar-subscriptions`, `api/cron/webhookTriggers`,
  `api/webhook/app-credential`, `api/webhooks/calendar-subscription/[provider]`).
- Authentication drops weak/unrelated signals (e.g. an `s3SigningDiagnostics.test.ts`)
  and routes that match only via a `[token]` path segment on a non-auth domain (e.g.
  `app-upload/[token]`), so headline evidence is direct auth only.
- Context Pack recommends a test only when the relation is provable (import or true
  same-directory) and **omits** it otherwise - no invented "same module"/"same
  directory" reasons across packages.

## 2. What works

CLI: `dtc init`, `dtc scan`, `dtc concepts`, `dtc explain`, `dtc evidence`,
`dtc context`, `dtc risk --diff`, `dtc decision add`, `dtc debt`, `dtc status`,
`dtc doctor --privacy`, `dtc export`, `dtc reset`.

Trust laws enforced as executable gates: *no claim without evidence*, *usage is not
decision*, *uncertainty is output*, and *ignored secrets never become evidence*.

## 3. Demo repo proof (`examples/demo-saas`)

`dtc scan` detects Authentication, Billing Webhooks, Background Jobs, Data Export, and
Admin Permissions in `38 signals` across `15 files` in ~0.1s.

- **Authentication scores higher because an ADR exists** (`docs/decisions/0001-use-jwt.md`):
  its "why" is documented.
- **Billing Webhooks scores lower because no decision exists**: strong behavior
  evidence (route + Stripe signature verification + test) but Understanding Score
  `58/100` (debt medium) with explicit uncertainty "No decision was found explaining
  key choices".

## 4. Real repo validation proof

Validated against three real repositories (reports in `reports/reality-validation/`):
API Graveyard (FastAPI + TS), Snapilio (Next.js/SST), SaaSVoice (Next.js/SST).

| Repo | Files | Signals | Headline finding |
|------|-------|---------|------------------|
| API Graveyard | 355 | ~1.4k | False "Billing Webhooks" on a generic webhook system; migration mis-used as Background Jobs evidence |
| Snapilio | 186 | 649 | Next.js App Router routes invisible → everything degraded to weak evidence |
| SaaSVoice | 125 | 508 | NextAuth + all API routes missed |

## 5. Before / after examples

**Snapilio - Authentication:** before `confidence: medium` (dependency/doc only);
after **`confidence: high`** with real `app/api/.../route.ts` route evidence.

**API Graveyard - Billing Webhooks:** before, a generic webhook delivery system was
**mislabelled** Billing Webhooks; after the file-local evidence gate, it is **no
longer detected** (its only billing association was an e2e spec path). Real billing
webhooks (Snapilio PayPal, demo Stripe) are still correctly detected.

**Demo - the decision loop:** `dtc explain "Billing Webhooks"` → Understanding Score
`58/100` (debt medium) with uncertainty. After a **corroborated** `dtc decision add`
("Use Stripe for billing"), the uncertainty clears and the Understanding Score
improves to **`79/100`** (debt low). An *uncorroborated* decision (e.g. claiming retry
behavior the code lacks) leaves the uncertainty in place.

**Demo - risk review:** with retry behavior changed and no duplicate-delivery test
touched, `dtc risk --diff` flags **high severity**: "Retry behavior changed without
duplicate-delivery test changes."

## 6. Fixture learning loop

Every real failure became a fixture so it cannot silently regress:

- **Next.js App Router was initially missed**, then fixed and locked in by fixtures
  (`nextjs-data-export-route`, `nextauth-authentication`, `paypal-webhook-is-billing`,
  `nextjs-file-upload-route`, `nextjs-admin-route`).
- **False Billing Webhooks detection was fixed by file-local evidence gating**, locked
  in by `generic-webhook-not-billing`, `stripe-dep-alone-not-billing`,
  `generic-webhook-plus-unrelated-billing-dep`, and the positive
  `billing-webhook-local-stripe`.
- Migration exclusion, e2e down-weighting, weak-only concepts, and named Express
  routers each have fixtures too.

Fixtures grew the suite from 13 → **33 tests**.

## 7. Performance hardening

The scanner now prunes ignored directories before traversal (`os.walk` +
`PRUNE_DIRS`). **API Graveyard scan time improved from ~27.3s to ~0.48s (≈56×)**, with
identical privacy behavior (secrets under ignored paths are never visited).

## 8. Trust laws covered by tests

- *No claim without evidence* - `tests/unit/test_claims.py`.
- *Usage is not decision* - `tests/unit/test_claims.py`.
- *Uncertainty is output* - scoring/claims tests assert missing-decision uncertainty.
- *Ignored secrets never become evidence* - `tests/fixtures/test_privacy_fixtures.py`,
  `tests/unit/test_walker_prune.py`.
- *Risk review fires on the right change* - `tests/integration/test_risk_review.py`.

## 9. What DevTime still does not do

Heuristic scanner (not a compiler); limited framework coverage (strongest on
TS/Next.js/Express/FastAPI); no git-history signals; MCP transport unwired; no AI
provider; risk review advisory only; local-first with no cloud/team/UI. Full list in
**[LIMITATIONS.md](LIMITATIONS.md)**.

## 10. Next validation targets

A standalone open-source FastAPI repo and a random open-source TypeScript repo, plus
larger-repo performance profiling. Each new wrong output should become a fixture.

---

## Clean-install verification

A fresh `git clone` was installed and exercised end to end:

| Field | Result |
|-------|--------|
| OS | Windows 11 (Git Bash) |
| Python | 3.11.9 |
| Install command | `pip install -e ".[dev]"` |
| Test result | **33 passed** |
| Demo result | `dtc init` / `dtc scan` / `dtc concepts` / `dtc explain "Billing Webhooks"` all produced expected output from a clean clone |
| Issue found & fixed | `dtc risk --diff` produced no findings when the scan root is a subdirectory of the git repo (path mismatch). Fixed with `git diff --relative`; the demo risk step now works. |
