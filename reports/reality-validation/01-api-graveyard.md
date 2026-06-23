# Reality Validation - API Graveyard

Repo: API Graveyard (local, mixed FastAPI backend + TS qa-automation)
Commands run: `dtc init`, `dtc scan`, `dtc concepts`, `dtc explain` (x6), `dtc context "Billing Webhooks"`, `dtc evidence "Billing Webhooks"`, `dtc risk --diff --base HEAD`
Files scanned: 355
Signals extracted: 1468
Concepts detected: Authentication, Billing Webhooks, Data Export, File Uploads, Admin Permissions, Background Jobs (6)

Best output:
- **Authentication** - genuinely correct. Evidence `backend/app/api/v1/auth.py`, `core/security.py`, `api/deps.py`; "uses JWT access tokens" (0.88) is well supported by real JWT code. Active route handling correct. Debt 54/medium with honest "no decision found". This is the kind of output that earns trust.

Worst output:
- **Billing Webhooks is a FALSE POSITIVE.** It is actually a *generic webhook delivery system* (`POST /webhook-receiver`, `GET /{webhook_id}/deliveries`, `POST /{webhook_id}/deliveries/{id}/retry`). There is **no Stripe, no billing, no subscription, no signature verification** anywhere. DevTime named it "Billing Webhooks" purely on the word "webhook".

Wrong claim:
- "Billing Webhooks is present in this repository." - wrong: there is no billing here.

Missing concept:
- A correct **Webhooks (generic delivery)** concept is missing; it was swallowed by the Billing Webhooks template.
- **RBAC** real implementation (`backend/app/api/rbac.py`) is under-detected - only cited as a weak "dependency", not behavior.

Bad evidence:
- E2E UI specs are attached as evidence to many concepts via keyword-matched test names: `qa-automation/tests-e2e/specs/sidebar-navigation.e2e.spec.ts` → File Uploads; `dependencies.e2e.spec.ts`, `risks.e2e.spec.ts` → Data Export. These are weak/irrelevant.
- An **Alembic migration** `backend/alembic/versions/146526398b6a_add_demo_traffic_jobs_clean.py` is cited as Background Jobs evidence (and as a "dependency") because the filename contains "jobs". A DB migration is not a worker.

Missing uncertainty:
- For Billing Webhooks, DevTime should have emitted uncertainty like "matched on the word 'webhook' but found no billing/Stripe/subscription evidence" - instead it asserted the concept confidently.

Unsupported confidence:
- Billing Webhooks concept claim at 0.72 ("medium", state supported) despite zero billing evidence.
- **Context Pack fabricates billing-specific warnings**: "Do Not Change Without Review: Signature verification behavior / Idempotency behavior / Subscription state transition mapping" - none of these exist in this repo. This comes from the hardcoded `_do_not_change_for("Billing Webhooks")` table and is the most serious trust violation found: a claim with no evidence.

Privacy or ignore issue:
- None observed. `.devtime` created and removed; no secrets surfaced. `.gitignore` respected.

Risk review usefulness:
- `risk --diff --base HEAD` returned "No findings" (clean working tree). Not exercised meaningfully here.

New fixture needed:
1. `generic-webhook-not-billing` - webhook delivery system must NOT become "Billing Webhooks" without billing/Stripe/subscription/signature evidence.
2. `context-pack-no-fabricated-warnings` - Context Pack "do not change" warnings must derive from evidence, not a hardcoded per-name table.
3. `migration-not-background-job` - Alembic/migration files must not be Background Jobs evidence.
4. `e2e-spec-weak-evidence` - keyword-matched E2E UI specs should be weak/excluded, not concept-defining evidence.

Fix priority:
- P0: fabricated Context Pack warnings (#2) and Billing false positive (#1) - both violate "no claim without evidence / no claim stronger than its evidence".
- P1: migration + e2e noise (#3, #4).
- P2: performance - scan took 27s because the walker does not prune ignored directories (walks into them before filtering).

Notes:
- Authentication shows the product working as intended. The failures are all over-claiming from weak keyword matches - exactly the precision risk flagged earlier. One repo already yields 4 strong fixture candidates.
