# Clean Install Check

A repeatable fresh-clone test: clone, install, test, and run the demo from scratch.
Use this before any release to confirm a stranger can get from zero to proof.

## Script

```bash
set -e
cd /tmp
rm -rf devtime-clean-test
git clone https://github.com/Shakargy/devtime.git devtime-clean-test
cd devtime-clean-test

python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash; use .venv/bin/activate on macOS/Linux

pip install -e ".[dev]"
pytest                               # expect: all tests pass (77+)

cd examples/demo-saas
dtc init
dtc scan                             # expect: "Scan complete. 15 files, 38 signals, 5 concepts ..."
dtc concepts
dtc explain "Billing Webhooks"       # expect: Understanding Debt 56/100 + missing-decision uncertainty
```

To exercise the advisory risk review, follow the prepared diff in
[DEMO_SCRIPT.md](DEMO_SCRIPT.md) (edit `src/billing/stripe-webhook.ts`, run
`dtc risk --diff`, then `git checkout -- src/billing/stripe-webhook.ts`).

## Recorded result

| Field | Result |
|-------|--------|
| Date | 2026-06-21 |
| OS | Windows 11 (Git Bash) |
| Python | 3.11.9 |
| Install command | `pip install -e ".[dev]"` |
| Test result | **all passed (77+)** |
| `dtc` on PATH | yes (inside the activated venv) |
| Demo result | scan / concepts / explain produced expected output |
| Issue found | `dtc risk --diff` reported no findings when the scan root is a subdirectory of the git repo (diff paths were repo-relative, evidence paths scan-root-relative) |
| Fix | `dtc risk` now runs `git diff --relative`; risk demo verified working |

## Notes

- If `dtc` is "command not found", the virtual environment is not active. Re-activate
  it, or run `python -m devtime.cli ...`.
- DevTime scans the **current directory**; always `cd` into the repo (or
  `examples/demo-saas`) before `dtc init`/`dtc scan`.
