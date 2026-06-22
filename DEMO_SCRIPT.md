# Demo Script — DevTime V0: Repository Memory From Evidence

A 2–3 minute walkthrough. Every command below is real and copy-pasteable. Run it from
inside the sample app (`examples/demo-saas`), because DevTime scans the current
directory.

> Tone: this is **evidence-backed local memory**, not magic. We talk about evidence,
> uncertainty, local memory, advisory risk review, and the decision loop — never
> "AI understands your repo", "automatically fixes your code", or "guarantees
> correctness".

## Setup

```bash
cd examples/demo-saas
dtc init
```

Narration: *"DevTime created a local memory store in `.devtime/`. Nothing leaves this
machine. No cloud, no telemetry, no code execution."*

## 1. Scan — no execution, no network

```bash
dtc scan
```

Output:

```
Scan complete. 15 files, 38 signals, 5 concepts in 0.1s.
```

Narration: *"It scanned the repository without running any of its code and without a
network call, and extracted evidence-backed signals."*

## 2. Concepts — what the repo contains

```bash
dtc concepts
```

Narration: *"DevTime found five concepts — Authentication, Billing Webhooks,
Background Jobs, Data Export, Admin Permissions — each with a confidence level and an
Understanding Debt score."*

## 3. Authentication — stronger, because there is a decision

```bash
dtc explain "Authentication"
```

Narration: *"Authentication is well supported: routes, JWT usage, middleware, tests —
and a decision record (an ADR). Because the 'why' is documented, its Understanding
Debt is lower."*

## 4. Billing Webhooks — strong evidence, but real uncertainty

```bash
dtc explain "Billing Webhooks"
```

Output includes:

```
Uncertainty:
  - No decision was found explaining key choices for Billing Webhooks.

Understanding Score: 56 / 100
Understanding Debt: medium
```

Narration: *"Billing Webhooks has strong behavior evidence — a route and Stripe
signature verification — but DevTime surfaces uncertainty: no decision explains its
key choices. Understanding Score is higher = better; Debt is a label. Uncertainty is
a feature, not a bug."*

## 5. A risky change is flagged (advisory)

Create the safe demo diff — change retry behavior **without** updating the
duplicate-delivery test:

```bash
# edit src/billing/stripe-webhook.ts: wrap the subscription update in a retry loop
```

Apply this change inside the `customer.subscription.updated` branch (note the word
"Retry" in the comment — the heuristic keys on it):

```ts
  if (event.type === "customer.subscription.updated") {
    // Retry the subscription update a few times on transient failures.
    for (let attempt = 0; attempt < 3; attempt++) {
      try { await updateSubscriptionState(event.data.object); break; }
      catch (err) { if (attempt === 2) throw err; }
    }
  }
```

Then:

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
Missing:
  - duplicate-delivery test update
  - retry strategy decision
Suggested action:
  Update duplicate-delivery tests or record the retry behavior decision before merge.
```

Narration: *"This is advisory, not a gate. DevTime noticed retry behavior changed but
no duplicate-delivery test was touched — exactly the kind of change worth a second
look."*

**Revert the demo change:**

```bash
git checkout -- src/billing/stripe-webhook.ts
```

## 6. Close the loop — but only a *corroborated* decision counts

First, the unsafe move DevTime refuses to reward. We reverted the retry code, so if we
record a retry decision anyway, DevTime should NOT be fooled:

```bash
dtc decision add --concept billing_webhooks \
  --title "Webhook retry and idempotency strategy" \
  --body "Retry subscription updates up to 3x; dedupe by Stripe event id."

dtc explain "Billing Webhooks"
```

The uncertainty stays, with a corroboration note:

```
Uncertainty:
  - Decision 'Webhook retry and idempotency strategy' exists, but retry, deduplication
    is not corroborated by scanned implementation evidence.
```

Narration: *"DevTime will not raise the score for a decision the code does not back
up. A decision is evidence, not automatic truth."*

Now contrast a decision that **matches** the implementation. On a fresh scan
(`dtc reset && dtc init && dtc scan`), record a corroborated one:

```bash
dtc decision add --concept billing_webhooks \
  --title "Use Stripe for billing" \
  --body "We use Stripe as the payment provider and verify webhook signatures."

dtc explain "Billing Webhooks"
```

This decision matches the scanned Stripe signature-verification evidence, so the
missing-decision uncertainty clears and the Understanding Score improves.

Narration: *"A corroborated decision adds real understanding. DevTime distinguishes a
decision that matches the code from one that merely claims behavior."*

> PowerShell note: pass each option inline (as above) rather than a multi-line body.
> `dtc decision add --concept billing_webhooks --title "..." --body "..."`

## Close

Narration: *"DevTime is not magic and not an AI agent. It is evidence-backed local
memory: it shows what the repository can prove, admits what it cannot prove yet, and
gives humans and agents safer context."*

## Reset (optional)

```bash
dtc reset            # or: rm -rf .devtime
```
