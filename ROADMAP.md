# Roadmap

DevTime is an early, local-first tool focused on being trustworthy before being
large. This roadmap is a direction, not a dated commitment - order and scope may
change based on real feedback.

## Current release - v0.1.0

- Local scan (no cloud, no telemetry, no code execution, no AI).
- Six supported concept families (closed ontology).
- Evidence-linked, strength-aware claims with explicit uncertainty.
- Understanding Score and Understanding Debt.
- Advisory, narrow `dtc risk --diff`.
- Governed, capped, evidence-based Context Packs.
- Corroborated decision records.

## v0.1.1 - Public onboarding and trust patch

- README and onboarding improvements (faster first run, "Try in 60 seconds").
- `CONTRIBUTING.md` and a clearer issue flow.
- Public feedback turned into fixtures.
- Docs fixes from first users.

## v0.2 - Evidence precision and first-run UX

- Exact line-number evidence where available.
- Better `dtc status` and `dtc doctor --privacy` output.
- Stronger unsupported-framework warnings.
- More real-world fixtures.
- Clearer large-repo scan output.

## v0.3 - GitHub Action advisory PR review

- A GitHub Action prototype that runs `dtc risk --diff` in pull requests.
- Advisory PR comments only.
- No blocking by default; no blocking on weak claims.

## Later

- Read-only MCP transport.
- A local UI.
- Shared team decisions.
- Understanding Debt history over time.
- An optional hosted/team product, only if it earns its place.

Have an opinion on priorities? Open an issue - real usage shapes this more than a
plan does.
