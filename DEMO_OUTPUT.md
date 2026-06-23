# Demo Output - DevTime V0 (v0.0.7)

The exact command sequence and **real** expected output for the 2-3 minute demo, with
timing, on-camera guidance, and recovery steps. All output below was captured from
`examples/demo-saas` on v0.0.7 (Python 3.11, local, no network). `dtc` is the console
script installed by `pip install -e ".[dev]"`; if it is not on your PATH, use
`python -m devtime.cli` instead.

## Exact command sequence

```bash
cd examples/demo-saas
rm -rf .devtime
dtc init
dtc scan
dtc concepts
dtc explain "Authentication"
dtc explain "Billing Webhooks"
# --- apply the safe demo diff to src/billing/stripe-webhook.ts (see DEMO_SCRIPT.md) ---
dtc risk --diff
git checkout -- src/billing/stripe-webhook.ts
# --- corroborated decision on a fresh scan ---
rm -rf .devtime && dtc init && dtc scan
dtc decision add --concept billing_webhooks --title "Use Stripe for billing" --body "We use Stripe as the payment provider and verify webhook signatures."
dtc explain "Billing Webhooks"
# --- leave the repo clean ---
rm -rf .devtime
git checkout -- .
git status
```

## Expected output snippets (real)

**`dtc scan`**
```
Scanning locally. No code execution. No network.
Scan complete. Scanned 15 files, 38 signals, 5 concepts in 0.1s.
Pruned directories: 1   Skipped/ignored files: 0
Supported V0 concept families: 6 (closed ontology).
```

**`dtc concepts`** (first two)
```
1. Billing Webhooks   confidence: high    debt: medium
2. Authentication     confidence: high    debt: low
```

**`dtc explain "Authentication"`**
```
Understanding Score: 79 / 100
Understanding Debt: low
Uncertainty: (none)
```

**`dtc explain "Billing Webhooks"`** (before any decision)
```
Uncertainty:
  - No decision was found explaining key choices for Billing Webhooks.
Understanding Score: 58 / 100
Understanding Debt: medium
```

**`dtc risk --diff`** (with the retry diff applied)
```
Finding (high):
  Retry behavior changed without duplicate-delivery test changes.
Why this matters:
  Billing webhooks may receive duplicate events; retry without dedupe tests risks double-processing.
```

**`dtc explain "Billing Webhooks"`** (after the corroborated Stripe decision)
```
Uncertainty: (none)
Understanding Score: 79 / 100
Understanding Debt: low
```

**Counter-example - uncorroborated decision** (optional)
```
Uncertainty:
  - Decision 'Retry strategy' exists, but retry, deduplication is not corroborated
    by scanned implementation evidence.
Understanding Score: 58 / 100
```

## Timing estimate (~2m40s)

| Beat | Action | ~Time |
|------|--------|-------|
| 0-1 | init + scan (local, no network) | 25s |
| 2 | concepts | 15s |
| 3 | explain Authentication (score 79) | 25s |
| 4 | explain Billing Webhooks (58, uncertainty) | 25s |
| 5 | apply diff + risk --diff (high finding) | 35s |
| 6 | corroborated decision → 58→79 | 30s |
| 7 | close + (optional) uncorroborated counter-example | 25s |

Commands themselves run sub-second; the time is narration. Total fits 2-3 minutes;
drop the optional counter-example to land closer to 2 minutes.

## What to say on camera

- "Local-first: no cloud, no telemetry, no code execution, no AI required."
- "Concepts and claims come from evidence - every claim links to files."
- "Authentication scores high because it has evidence **and** a decision the code backs up."
- "Billing Webhooks has strong evidence but missing reasoning - DevTime shows the gap."
- "Risk review is advisory and narrow; it flagged a retry change with no dedupe test."
- "A decision only helps when the code corroborates it."
- "DevTime is honest about uncertainty and its limits (six concept families, heuristic)."

## What NOT to say

- "AI understands your repo" / "AI-powered" (no AI is used).
- "Automatically fixes your code" / "guarantees correctness / safe changes."
- "Understands every repo" or implies arbitrary concept discovery.
- Quoting Understanding Debt as a number - it is a label; the **Score** is the number.

## Reset / revert (leave git clean)

```bash
rm -rf .devtime              # remove local memory (or: dtc reset --yes)
git checkout -- .            # restore stripe-webhook.ts and .devtimeignore
git status                   # examples/demo-saas should show no changes
```

Verified: after this sequence, `git status` reports a clean working tree.

## Troubleshooting

- **`dtc: command not found`** - the venv is not active; re-activate it or use
  `python -m devtime.cli ...`.
- **`risk --diff` shows no findings** - the demo diff was not applied, or its comment
  lacks the word "Retry" (the heuristic keys on retry/idempotency/duplicate). Re-apply
  the diff from DEMO_SCRIPT.md.
- **Decision didn't clear uncertainty** - that is correct if the decision describes
  behavior (retry/dedupe) the code doesn't show. Use the corroborated "Use Stripe for
  billing" decision on a fresh scan to demonstrate the improvement.
- **Dirty `git status` after the demo** - run `git checkout -- .` inside
  `examples/demo-saas` and `rm -rf .devtime`.
