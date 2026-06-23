# Demo Script - DevTime V0: Repository Memory From Evidence

A 2-3 minute walkthrough. Every command is real and copy-pasteable, and every output
block matches current v0.1.0 behavior (verified on `examples/demo-saas`). Run it from
inside the sample app, because DevTime scans the **current directory**.

> Tone: this is **evidence-backed local memory**, not magic. Say: evidence,
> uncertainty, local memory, advisory risk review, corroborated decisions. Never say:
> "AI understands your repo", "automatically fixes your code", or "guarantees
> correctness". DevTime requires no AI.

## 0. Clean start

```bash
cd examples/demo-saas
rm -rf .devtime
dtc init
```

Output:

```
DevTime initialized. Local memory at .devtime/devtime.sqlite
AI disabled. Cloud disabled. Telemetry off. MCP read-only.
```

Narration: *"DevTime created a local memory store in `.devtime/`. Nothing leaves this
machine - no cloud, no telemetry, no code execution, no AI required."*

## 1. Scan - no execution, no network  (beat A)

```bash
dtc scan
```

Output:

```
Scanning locally. No code execution. No network.
Scan complete. Scanned 15 files, 38 signals, 5 concepts in 0.1s.
Pruned directories: 1   Skipped/ignored files: 0
Supported V0 concept families: 6 (closed ontology).
Nothing left this machine. Run dtc concepts to inspect.
```

Narration: *"It scanned the repo without running any of its code and without a network
call. V0 detects six supported concept families - it doesn't invent arbitrary
concepts."*

## 2. Concepts - what the repo contains  (beat B)

```bash
dtc concepts
```

Output:

```
Detected concepts

1. Billing Webhooks
   confidence: high
   evidence: behavior, dependency, route, test
   debt: medium

2. Authentication
   confidence: high
   evidence: decision, dependency, middleware, route, test, usage
   debt: low
...
```

Narration: *"Five concepts, each with a confidence level and an Understanding Debt
label derived from evidence."*

## 3. Authentication - better understood, because evidence and a decision exist  (beat C)

```bash
dtc explain "Authentication"
```

Output (trimmed):

```
Supported claims:
  - Authentication is present and supported by behavior evidence.
    type: concept  confidence: 0.85  evidence: src/auth/login.ts, tests/auth-login.test.ts, docs/decisions/0001-use-jwt.md
  - Authentication has active route handling.
  - Authentication uses JWT access tokens.

Uncertainty:
  (none)

Understanding Score: 79 / 100
Understanding Debt: low
```

Narration: *"Authentication has routes, JWT usage, middleware, tests - and a decision
record (an ADR) that the code backs up. Because the 'why' is documented and
corroborated, the Understanding Score is high and there's no open uncertainty."*

## 4. Billing Webhooks - strong evidence, but missing reasoning  (beat D)

```bash
dtc explain "Billing Webhooks"
```

Output (trimmed):

```
Supported claims:
  - Billing Webhooks is present and supported by behavior evidence.
  - Billing Webhooks has active route handling.
  - Billing Webhooks verifies webhook signatures.

Uncertainty:
  - No decision was found explaining key choices for Billing Webhooks.

Understanding Score: 58 / 100
Understanding Debt: medium
```

Narration: *"Strong behavior evidence - a Stripe webhook route and signature
verification - but DevTime surfaces uncertainty: no decision explains its key choices.
Uncertainty is a feature, not a bug."*

## 5. A risky change is flagged (advisory, narrow)  (beat E)

Apply the safe demo diff - change retry behavior inside the
`customer.subscription.updated` branch of `src/billing/stripe-webhook.ts`, **without**
updating a duplicate-delivery test:

```ts
  if (event.type === "customer.subscription.updated") {
    // Retry the subscription update a few times on transient failures.
    for (let attempt = 0; attempt < 3; attempt++) {
      try { await updateSubscriptionState(event.data.object); break; }
      catch (err) { if (attempt === 2) throw err; }
    }
  }
```

```bash
dtc risk --diff
```

Output:

```
DevTime Risk Review

Affected concept:
  Billing Webhooks
Finding (high):
  Retry behavior changed without duplicate-delivery test changes.
Why this matters:
  Billing webhooks may receive duplicate events; retry without dedupe tests risks double-processing.
Missing:
  - duplicate-delivery test update
  - retry strategy decision
Suggested action:
  Update duplicate-delivery tests or record the retry behavior decision before merge.
```

Narration: *"This is advisory and narrow - not a gate. DevTime noticed retry behavior
changed while no duplicate-delivery test was touched: exactly the kind of change worth
a second look."*

Revert the code change before continuing:

```bash
git checkout -- src/billing/stripe-webhook.ts
```

## 6. A *corroborated* decision improves understanding  (beat F)

DevTime won't be fooled by a decision the code doesn't support. Record a decision that
**matches** the scanned evidence (Stripe signature verification), on a fresh scan:

```bash
rm -rf .devtime && dtc init && dtc scan
dtc decision add --concept billing_webhooks --title "Use Stripe for billing" --body "We use Stripe as the payment provider and verify webhook signatures."
dtc explain "Billing Webhooks"
```

Output (trimmed):

```
Uncertainty:
  (none)

Understanding Score: 79 / 100
Understanding Debt: low
```

Narration: *"This decision matches the implementation, so the missing-decision
uncertainty clears and the Understanding Score rises from 58 to 79."*

> Counter-example (optional, beat G): record a decision the code does NOT back up -
> `dtc decision add --concept billing_webhooks --title "Retry strategy" --body "Retry up to 3x and dedupe by event id."`
> DevTime keeps the uncertainty: *"Decision 'Retry strategy' exists, but retry,
> deduplication is not corroborated by scanned implementation evidence."* A decision is
> evidence, not automatic truth.

> PowerShell note: pass `--title`/`--body` inline on one line (as above). All demo
> commands are single-line and work in bash, PowerShell, and cmd.

## Close  (beat G)

Narration: *"DevTime is not magic and not an AI agent. It's evidence-backed local
memory: it shows what the repository can prove, admits what it can't prove yet, warns
about a narrow set of risky changes, and only rewards decisions the code corroborates."*

## Reset / revert - leave the repo clean

```bash
rm -rf .devtime
git checkout -- .          # restores stripe-webhook.ts and .devtimeignore
git status                 # should report nothing in examples/demo-saas
```
