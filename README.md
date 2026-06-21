# DevTime

**Local-first Engineering Intelligence for software repositories.**

DevTime helps a repository explain itself from evidence. It scans code, tests,
configs, routes, and decisions to identify the concepts inside a codebase, show the
evidence behind them, surface uncertainty, and warn about risky changes.

It does not execute your code. It does not send your code anywhere. It does not
require AI. It does not pretend to know things without evidence.

> No cloud. No telemetry. No code execution. No AI required.

---

## Why this exists

Git remembers *code*. It does not remember *understanding* — why a behavior exists,
what evidence supports it, or what nobody has decided yet. As AI tools generate code
faster than teams can review it, that missing understanding becomes the bottleneck.

DevTime builds **evidence-backed repository memory**: a local layer that says what a
repository can prove, and — just as importantly — what it cannot prove yet.

## What DevTime does

- **Detects concepts** — stable units of meaning like Authentication, Billing
  Webhooks, Background Jobs — from routes, tests, configs, dependencies, and docs.
- **Explains from evidence** — every claim links to the files/signals behind it.
- **Surfaces uncertainty** — when evidence is missing (e.g. no decision record), it
  says so instead of guessing.
- **Scores Understanding Debt** — a product signal for how well a concept can be
  explained, with the causes shown.
- **Warns about risky changes** — `dtc risk --diff` reviews a git diff against local
  memory and flags advisory findings.
- **Records decisions** — `dtc decision add` stores rationale locally, which reduces
  uncertainty and improves understanding.

## What DevTime does not do

- It does not execute your code.
- It does not send code or data over the network.
- It does not require or call an AI model.
- It does not guarantee correctness or safe changes.
- It does not replace code review or architecture decisions.
- It is **not** a documentation generator, a static analyzer, an observability tool,
  a productivity tracker, or an AI coding agent.

See **[LIMITATIONS.md](LIMITATIONS.md)** for the full, honest list.

## Trust model

- DevTime stores local repository memory in `.devtime/` (a local SQLite database).
- **No network access** during a scan.
- **No code execution** during a scan.
- Ignored directories are pruned *before* scanning; ignored files and secrets must
  never become evidence or claims.
- Every claim must link to evidence — *no claim without evidence*.
- Weak evidence produces **uncertainty**, not confidence.
- *Usage is not decision*: that a dependency is used does not mean someone decided
  why.
- Risk review is **advisory** by default — it does not block PRs.

## Quick demo

DevTime scans the **current directory**, so the demo runs from inside the demo app.

```bash
cd examples/demo-saas
dtc init
dtc scan
dtc concepts
dtc explain "Billing Webhooks"
# ...make a change, then:
dtc risk --diff
dtc decision add --concept billing_webhooks \
  --title "Webhook retry and idempotency strategy" \
  --body "Retry subscription updates up to 3x; dedupe by Stripe event id."
dtc explain "Billing Webhooks"
```

The narrative:

- **Before a decision:** Billing Webhooks has strong evidence (route, signature
  verification, test) *and* uncertainty — no decision explains its retry or
  duplicate-delivery behavior. Understanding Debt is `56/100`.
- **Risk review:** changing retry behavior without updating duplicate-delivery tests
  is flagged **high severity**.
- **After adding a decision:** the missing reasoning is now in repository memory, the
  uncertainty clears, and Understanding Debt improves to `72/100`.

A full, copy-pasteable walkthrough is in **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)**.

## Installation

Requires **Python ≥ 3.11** and git.

```bash
git clone https://github.com/Shakargy/devtime.git
cd devtime
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                              # 33 tests should pass
```

This installs the `dtc` command. See **[QUICKSTART.md](QUICKSTART.md)** for a
step-by-step first run and troubleshooting.

## Commands

| Command | Purpose |
|---------|---------|
| `dtc init` | Create local `.devtime` memory. |
| `dtc scan` | Scan the current repository and extract evidence-backed signals. |
| `dtc concepts` | List detected concepts with confidence and Understanding Debt. |
| `dtc explain <concept>` | Explain a concept: claims, evidence, confidence, uncertainty, Understanding Debt. |
| `dtc context <concept>` | Create a governed Context Pack for agents or humans. |
| `dtc risk --diff` | Review a git diff for risky changes using local evidence (advisory). |
| `dtc decision add` | Add a local decision record that can reduce uncertainty. |

(Also available: `dtc evidence`, `dtc debt`, `dtc status`, `dtc doctor --privacy`,
`dtc export`, `dtc reset`.)

## Example output

```
$ dtc explain "Billing Webhooks"
Concept: Billing Webhooks

Supported claims:
  - Billing Webhooks is present in this repository.
    type: concept  confidence: 0.86  evidence: src/billing/stripe-webhook.ts, tests/stripe-signature.test.ts
  - Billing Webhooks has active route handling.
    type: behavior  confidence: 0.82  evidence: src/billing/stripe-webhook.ts
  - Billing Webhooks verifies webhook signatures.
    type: behavior  confidence: 0.85  evidence: src/billing/stripe-webhook.ts

Uncertainty:
  - No decision was found explaining key choices for Billing Webhooks.

Understanding Debt: 56 / 100 (medium)
causes:
  - missing decision evidence
  - no confirmed owner
```

## Proof

DevTime runs on `examples/demo-saas` and on real repositories. During Reality
Validation it detected — and then learned from — real failures (Next.js App Router
blindness, a false Billing Webhooks detection on a generic webhook system, a DB
migration mis-counted as Background Jobs evidence, and more). Each failure became a
fixture so it cannot silently regress.

- Tests grew from 13 → **33 passing**.
- Scan time on a 355-file real repo dropped from ~27.3s to ~0.48s after ignored-
  directory pruning.

Full evidence, before/after examples, and the validation reports are in
**[PROOF.md](PROOF.md)** and `reports/reality-validation/`.

## Privacy and safety

- Runs entirely locally; nothing leaves your machine during a scan.
- No code execution and no network calls during scanning.
- Secrets and ignored files are excluded from evidence by design (`dtc doctor
  --privacy` reports the boundaries).
- `dtc reset` deletes local memory; your source code is never modified.

## Known limitations

DevTime is a **heuristic scanner**, not a full compiler or semantic analyzer. It is
currently strongest on TypeScript / Next.js / Express / FastAPI-style repositories
that resemble its fixtures. False positives and false negatives are possible.
Understanding Debt is a product signal, not an objective universal truth.

Read the full list — including framework coverage, risk-review scope, and what is
intentionally not built yet — in **[LIMITATIONS.md](LIMITATIONS.md)**.

## Roadmap

This is an early, local-first V0 focused on being trustworthy before being large.
Not yet built (intentionally): git-history signals, wired MCP transport, an AI
provider, a UI, and any cloud/team/enterprise features. See LIMITATIONS.md.

## Contributing

The most valuable contribution is a **fixture**: a small repository pattern plus the
expected concepts, allowed claims, forbidden claims, and required uncertainty. If
DevTime gets something wrong on your code, that wrong output can become a fixture so
it never regresses. See `fixtures/` for the format and `tests/` for how they run.

## License

No license has been chosen yet. **TODO: choose a license before public release.**
