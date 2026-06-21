# DevTime — PROOF

Evidence that DevTime V0 does what it claims, on real repositories — and an honest
list of where it is still weak. Built and validated locally; AI off, cloud off,
telemetry off, no code execution, no network.

## 1. Current V0 status

A local-first Engineering Intelligence CLI (`dtc`) that scans a repository, detects
concepts, links them to evidence, generates governed claims with visible
uncertainty, scores Understanding Debt, reviews diffs against memory, and produces
Context Packs for humans and AI agents. SQLite memory in `.devtime/`.

- Tests: **27 passing** (`pytest`) — unit, integration, and 13 fixtures.
- Trust laws enforced as executable gates: no claim without evidence; usage is not
  decision; uncertainty is output; ignored secrets never become evidence.

## 2. Commands that work

```
dtc init                         # create local memory
dtc scan                         # detect concepts/evidence/claims (no code exec, no network)
dtc concepts                     # list detected concepts with confidence + debt
dtc explain <concept>            # claims + evidence + uncertainty + Understanding Debt
dtc evidence <concept>           # raw evidence list with strength
dtc context <concept> --mode risk# governed Context Pack for agents
dtc risk --diff --base <ref>     # memory-aware review of a diff
dtc decision add --title .. --body ..   # record rationale (closes Understanding Debt)
dtc doctor --privacy             # privacy/boundary checks
dtc export --format json|markdown
dtc status / dtc reset
```

## 3. Demo repo proof (`examples/demo-saas`)

`dtc scan` detects Authentication, Billing Webhooks, Background Jobs, Data Export,
Admin Permissions. Billing Webhooks correctly reports **"No decision was found"**
and scores lower than Authentication (which has an ADR). `dtc risk --diff` on a
retry-behavior change flags: *"Retry behavior changed without duplicate-delivery
test changes"* (high). `dtc decision add` drops Billing Webhooks debt 56 → 72 and
clears the uncertainty.

## 4. Real-repo validation results

Validated against three real repositories (see `reports/reality-validation/`):
API Graveyard (FastAPI + TS), Snapilio (Next.js/SST), SaaSVoice (Next.js/SST).

| Repo | Files | Signals | Key failure found |
|------|-------|---------|-------------------|
| API Graveyard | 355 | 1468 | "Billing Webhooks" false positive on a generic webhook system; Context Pack fabricated billing warnings; migration file used as Background Jobs evidence; e2e specs polluting evidence |
| Snapilio | 186 | 649 | Next.js App Router routes invisible → every concept degraded to weak dependency evidence; `//` path bug |
| SaaSVoice | 125 | 508 | NextAuth + all API routes missed; auth reported with no route evidence |

The single highest-leverage finding (two of three repos): **DevTime could not see the
Next.js App Router**, the most common TS API stack.

## 5. Before / after

**Snapilio — Authentication**
- Before: `confidence: medium`, evidence `dependency, doc, middleware`; claim was
  only "has related dependencies present".
- After: `confidence: high`, evidence now includes `route`; claim "Authentication
  has active route handling" anchored on real `app/api/.../route.ts` handlers.

**Snapilio — Billing Webhooks**
- Before: weak dependency-only, no behavior.
- After: `route` evidence + "has active route handling", anchored on the real
  `app/api/paypal/webhook/route.ts`.

**API Graveyard — Background Jobs**
- Before: evidence included `backend/alembic/versions/..._add_jobs.py` (a DB migration).
- After: migrations excluded; no migration files in evidence.

**API Graveyard — Context Pack**
- Before: "Do Not Change: Signature verification behavior / Subscription state
  transition mapping" — fabricated, no billing evidence in repo.
- After: warnings derived from actual evidence ("Token issuing and verification
  behavior", "Authorization / protected-route behavior", "Request handling for …").

## 6. Fixtures added (10 new, from real failures)

| Fixture | Locks in |
|---------|----------|
| `nextjs/nextjs-data-export-route` | App Router `route.ts` GET → Data Export route |
| `nextjs/nextauth-authentication` | `api/auth/[...nextauth]/route.ts` → Authentication route |
| `nextjs/paypal-webhook-is-billing` | PayPal webhook route → Billing Webhooks (real billing) |
| `nextjs/nextjs-file-upload-route` | upload route → File Uploads |
| `nextjs/nextjs-admin-route` | admin route → Admin Permissions |
| `webhooks/generic-webhook-not-billing` | generic webhook must NOT be "Billing Webhooks" |
| `jobs/migration-not-background-job` | migration file must NOT be Background Jobs evidence |
| `evidence/e2e-spec-weak` | e2e UI spec must not define a concept alone |
| `evidence/dependency-only-weak` | dependency-only concept stays weak + uncertain |
| `express/express-named-router` | `authRouter.post(...)` detected (named routers) |

Backed by scanner/claim fixes: Next.js extractor (`scanner/extractors/nextjs.py`),
billing-evidence gate + weak-only gate (`intelligence/concepts.py`), evidence-derived
Context Pack warnings (`intelligence/context_pack.py`), migration exclusion and e2e
down-weighting (`scanner/signals.py`, `scanner/extractors/tests.py`), path
normalization (`scanner/file_walker.py`).

## 7. Known limitations (honest)

- **Detection is pattern/regex-based.** Express, FastAPI, and Next.js App Router are
  covered; other frameworks (NestJS, Django, Flask, Rails, Go) are not yet parsed.
- **Billing gate is repo-wide, not file-local.** A repo with billing tokens anywhere
  can still allow a "Billing Webhooks" concept even if the matched webhook routes are
  generic. Tightening to file-locality is a next step.
- **No git-history signals.** Freshness is a fixed placeholder; ownership is always
  unconfirmed; lineage is not yet implemented.
- **Performance:** the file walker descends into ignored directories before filtering
  (~27s on a 355-file repo with large build output). Needs directory pruning.
- **MCP transport not wired.** Tool logic exists; the server only describes the
  read-only contract.
- **AI provider disabled.** No narration provider is shipped.
- Validation covered 3 real repos + the demo. Two more (a random open-source TS repo
  and a standalone FastAPI repo) are planned on dedicated branches.

## 8. Next recommended milestone

Tighten the billing gate to file-locality, add directory pruning to the walker, then
expand validation to 2 more open-source repos and grow the fixture suite. Only after
that: `dtc doctor`, `dtc claim show <id>`, `dtc export --markdown` polish.

> The milestone reached: **DevTime learned 10 real repo patterns and will not forget them.**
