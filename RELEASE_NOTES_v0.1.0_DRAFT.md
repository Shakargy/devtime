# DevTime v0.1.0 — Repository Memory From Evidence

> **DRAFT.** This is a draft for the first public release. `v0.1.0` has **not** been
> tagged. Versions/links are finalized at release time.

## 1. What is DevTime?

DevTime is a **local-first Engineering Intelligence** CLI. It helps a repository
explain itself **from evidence**: it scans code, tests, configs, routes, and
decisions to identify the concepts inside a codebase, shows the evidence behind each
claim, surfaces uncertainty, and warns about a narrow set of risky changes.

It does not execute your code, does not send your code anywhere, and does not require
AI. It does not pretend to know things without evidence.

## 2. What works in this release

- Local scan of a repository (no network, no code execution) into a local SQLite
  memory store in `.devtime/`.
- Detection of **six** supported concept families (closed ontology — see below).
- Evidence-linked, strength-aware claims with explicit **uncertainty**.
- An **Understanding Score** (higher = better) and an **Understanding Debt** label.
- **Advisory, narrow** risk review of a git diff (e.g. JWT algorithm weakening;
  billing-webhook retry without dedupe tests), with explicit result states.
- Governed, capped, evidence-based **Context Packs** for humans and agents.
- Local decision records that improve understanding **only when corroborated** by the
  scanned implementation.

## 3. Core commands

```
dtc init        Create local .devtime memory.
dtc scan        Scan the current repository (no code execution, no network).
dtc concepts    List detected concepts with confidence and Understanding Debt.
dtc explain     Explain a concept: claims, evidence, confidence, uncertainty, score.
dtc context     Create a governed Context Pack for agents or humans.
dtc risk --diff Review a git diff for risky changes (advisory).
dtc decision add Record a decision that can reduce uncertainty when corroborated.
```

(Also: `dtc evidence`, `dtc debt`, `dtc status`, `dtc doctor --privacy`, `dtc export`,
`dtc reset`.)

## 4. Trust model

- Local repository memory in `.devtime/` (local SQLite).
- **No cloud. No telemetry. No code execution during scan. No AI required.**
- Ignored directories are pruned before scanning; ignored files and secrets are
  excluded from evidence by design.
- Every claim links to evidence. Weak evidence produces uncertainty, not confidence.
- Risk review is **advisory** — it does not block PRs.

## 5. Demo

A ~2-minute demo video walks through a real scan on the sample app.

*TODO at release:* upload the demo video and add the public link here.

## 6. What changed during private validation

DevTime was validated privately on real repositories (Langfuse, Cal.com, Open WebUI,
Plane, Twenty) across several review rounds. The output got **more honest**, not
larger:

- File-local payment-provider evidence for Billing Webhooks (calendar/credential/
  generic webhooks no longer become Billing Webhooks).
- Word-sense gates (a job *title* is not a Background Job; an avatar *URL* is not a
  File Upload; a `session_id` trace is not Authentication).
- Strength-aware claims; no contradictory "is present" for weak evidence.
- Explicit risk-review states (`review_failed`/`no_findings`/`unsupported_change_class`/
  `finding`); a git failure is never reported as "no findings".
- Decisions must be corroborated by the code to clear uncertainty or raise the score.
- Context Pack reasons are truthful and auditable (import / same-directory, or omit).

## 7. Known limitations

DevTime is a **heuristic scanner**, not a compiler or semantic analyzer. It uses a
**closed six-concept ontology** (Authentication, Billing Webhooks, Background Jobs,
Data Export, Admin Permissions, File Uploads) and does not discover arbitrary domain
concepts. It is strongest on TypeScript/Next.js/Express/FastAPI-style repos. Risk
review covers a **narrow** set of change classes and is advisory. False positives and
negatives are possible. No git-history signals, no wired MCP transport, no AI provider,
no UI, no cloud. See [LIMITATIONS.md](LIMITATIONS.md). This is **not** a production-ready
enterprise platform or a broad security review.

## 8. Install

Requires Python ≥ 3.11 and git.

```
git clone <repo-url>
cd devtime
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                         # 88 tests
```

## 9. Try the demo repo

```
cd examples/demo-saas
dtc init
dtc scan
dtc concepts
dtc explain "Billing Webhooks"
```

See QUICKSTART.md and DEMO_SCRIPT.md for the full walkthrough (including the risk-diff
and corroborated-decision steps).

## 10. Feedback wanted

If DevTime gets something wrong on your repo, that's the most useful feedback — open a
**"DevTime got this wrong"** issue (template included). Wrong outputs become fixtures
so they can't silently regress.

---

Licensed under **Apache-2.0**. Local-first. Honest about uncertainty, honest about
limits.
