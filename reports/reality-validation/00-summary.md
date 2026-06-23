# Reality Validation - Summary

Goal: find where DevTime V0 is wrong on real repos, then convert failures into
fixtures so it never regresses.

Repos validated: API Graveyard (FastAPI+TS), Snapilio (Next.js/SST), SaaSVoice
(Next.js/SST), plus the `examples/demo-saas` demo. Two more (random open-source TS
+ standalone FastAPI) are deferred to follow-up branches; the 10-fixture metric was
met with the three real repos above.

## 10 failures → fixtures

| # | Failure (repo) | Fixture | Fix |
|---|----------------|---------|-----|
| 1 | Next.js routes invisible (Snapilio, SaaSVoice) | nextjs-data-export-route | `extractors/nextjs.py` |
| 2 | NextAuth route missed (SaaSVoice) | nextauth-authentication | nextjs extractor |
| 3 | PayPal webhook not seen as billing (Snapilio) | paypal-webhook-is-billing | nextjs extractor + billing gate |
| 4 | Upload route missed (Next.js) | nextjs-file-upload-route | nextjs extractor |
| 5 | Admin route missed (Next.js) | nextjs-admin-route | nextjs extractor |
| 6 | Generic webhook named "Billing Webhooks" (API Graveyard) | generic-webhook-not-billing | billing-evidence gate |
| 7 | Migration file as Background Jobs evidence (API Graveyard) | migration-not-background-job | migration exclusion |
| 8 | E2E spec defining a concept (API Graveyard) | e2e-spec-weak | e2e down-weighting |
| 9 | Dependency-only concept over-claimed (SaaSVoice) | dependency-only-weak | weak-only gate + uncertainty |
| 10 | Named Express routers undetected (common) | express-named-router | broadened route regex |

Plus Context Pack fabricated warnings (API Graveyard) → fixed by deriving warnings
from evidence; and a `//` path bug (Snapilio) → fixed by path normalization, both
covered by unit tests.

Result: 27 tests passing. See `PROOF.md` for before/after and known limitations.
