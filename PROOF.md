# DevTime — PROOF

Evidence that DevTime V0 does what it claims, on a demo repo and on real
repositories — plus an honest account of where it is still weak. Everything here is
local: AI off, cloud off, telemetry off, no code execution, no network.

## 1. Current version

- Version `0.1.0`. Tags: `v0.0.1-proof`, `v0.0.2-reality`, and this `v0.0.3-public-candidate`.
- Tests: **33 passing** (`pytest`) — unit, integration, and 16 fixtures.

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
  evidence (route + Stripe signature verification + test) but Understanding Debt
  `56/100` with explicit uncertainty "No decision was found explaining key choices".

## 4. Real repo validation proof

Validated against three real repositories (reports in `reports/reality-validation/`):
API Graveyard (FastAPI + TS), Snapilio (Next.js/SST), SaaSVoice (Next.js/SST).

| Repo | Files | Signals | Headline finding |
|------|-------|---------|------------------|
| API Graveyard | 355 | ~1.4k | False "Billing Webhooks" on a generic webhook system; migration mis-used as Background Jobs evidence |
| Snapilio | 186 | 649 | Next.js App Router routes invisible → everything degraded to weak evidence |
| SaaSVoice | 125 | 508 | NextAuth + all API routes missed |

## 5. Before / after examples

**Snapilio — Authentication:** before `confidence: medium` (dependency/doc only);
after **`confidence: high`** with real `app/api/.../route.ts` route evidence.

**API Graveyard — Billing Webhooks:** before, a generic webhook delivery system was
**mislabelled** Billing Webhooks; after the file-local evidence gate, it is **no
longer detected** (its only billing association was an e2e spec path). Real billing
webhooks (Snapilio PayPal, demo Stripe) are still correctly detected.

**Demo — the decision loop:** `dtc explain "Billing Webhooks"` → Understanding Debt
`56/100` with uncertainty. After `dtc decision add`, the uncertainty clears and debt
improves to **`72/100`**.

**Demo — risk review:** with retry behavior changed and no duplicate-delivery test
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

- *No claim without evidence* — `tests/unit/test_claims.py`.
- *Usage is not decision* — `tests/unit/test_claims.py`.
- *Uncertainty is output* — scoring/claims tests assert missing-decision uncertainty.
- *Ignored secrets never become evidence* — `tests/fixtures/test_privacy_fixtures.py`,
  `tests/unit/test_walker_prune.py`.
- *Risk review fires on the right change* — `tests/integration/test_risk_review.py`.

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
