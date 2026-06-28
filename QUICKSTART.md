# Quickstart

Get DevTime running and see the proof in a few minutes.

## 1. Requirements

- **Python ≥ 3.11** (developed and verified on 3.11.9)
- **git**
- A terminal. Works on Windows, macOS, and Linux.

## 2. Install (recommended: pipx)

```bash
pipx install devtime-ei
```

The PyPI distribution is `devtime-ei`. The Python package remains `devtime`, and the
CLI command remains `dtc`. [pipx](https://pipx.pypa.io/) puts `dtc` on your PATH in an
isolated environment. (Plain `pip install devtime-ei` also works.)

### From source (alternative)

```bash
git clone https://github.com/Shakargy/devtime.git
cd devtime
python -m venv .venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1
                                   # Windows (Git Bash):   source .venv/Scripts/activate
pip install -e ".[dev]"
pytest                             # optional: all tests pass (97 at v0.1.0)
```

## 3. Create the demo repo

```bash
dtc demo init
cd devtime-demo-saas
```

`dtc demo init` copies a small static example repo into `./devtime-demo-saas` so you
can try DevTime without cloning this repository. It only copies files: the scan is
local, with no cloud, no telemetry, and no code execution.

(From-source users can instead `cd examples/demo-saas`.)

## 4. Run the demo

DevTime scans the **current directory**, so run these from inside the demo repo:

```bash
dtc init
dtc scan
dtc concepts
dtc explain "Authentication"
dtc explain "Billing Webhooks"
```

To see risk review, see **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)** (it shows how to create
a safe demo diff and revert it).

## 6. Expected output

`dtc scan`:

```
Scan complete. 15 files, 38 signals, 5 concepts in 0.1s.
```

`dtc concepts` (order may vary):

```
1. Billing Webhooks   confidence: high    debt: medium
2. Authentication     confidence: high    debt: low
3. Background Jobs    confidence: medium  debt: high
4. Data Export        confidence: medium  debt: high
5. Admin Permissions  confidence: medium  debt: high
```

`dtc explain "Billing Webhooks"` shows supported claims with evidence, an
**Uncertainty** section ("No decision was found explaining key choices…"), an
**Understanding Score** of `58 / 100` (higher = better), and an **Understanding Debt**
label (`medium`).

V0 detects six supported concept families (closed ontology): Authentication, Billing
Webhooks, Background Jobs, Data Export, Admin Permissions, File Uploads. It does not
discover arbitrary domain concepts yet - see [LIMITATIONS.md](LIMITATIONS.md).

`dtc explain "Authentication"` scores higher, because the demo includes a decision
record (`docs/decisions/0001-use-jwt.md`).

## 7. Troubleshooting

- **`dtc: command not found`** - your virtual environment is not active. Re-run the
  activate command from step 3, or call the module directly: `python -m devtime.cli ...`.
- **`DevTime is not initialized`** - run `dtc init` in the directory you want to scan.
- **`No concept found matching '...'`** - run `dtc concepts` to see the exact names
  (they are case-insensitive but must otherwise match).
- **`risk --diff` shows no findings** - risk review needs a git diff in the current
  directory. See DEMO_SCRIPT.md for the prepared demo change.

## 8. Recording a decision (PowerShell-safe)

`dtc decision add` takes inline options - pass `--title` and `--body` on one line
(works in bash, PowerShell, and cmd):

```
dtc decision add --concept billing_webhooks --title "Use Stripe for billing" --body "We use Stripe as the payment provider and verify webhook signatures."
```

A decision only reduces uncertainty / raises the Understanding Score when it is
**corroborated** by the scanned implementation. A decision describing behavior the
code does not show (e.g. retry) stays flagged as uncorroborated.

## 9. Reset local memory

DevTime's memory lives in `.devtime/` and is safe to delete. Your source code is
never modified. Note: `dtc init` also writes a starter `.devtimeignore` in the repo
root; `dtc reset` removes `.devtime/` but leaves `.devtimeignore` in place (delete it
manually if you don't want it).

```bash
dtc reset            # deletes .devtime/ after confirmation
# or simply:
rm -rf .devtime
```

## Clean-install verification (maintainers)

A fresh-clone check was run on the current candidate:

- **OS:** Windows 11 (Git Bash)
- **Python:** 3.11.9
- **Install:** `pip install -e ".[dev]"`
- **Tests:** all passing (97 at v0.1.0)
- **Demo:** `dtc init` / `dtc scan` / `dtc concepts` / `dtc explain "Billing Webhooks"`
  all produced the expected output from a clean `git clone`.

To repeat it:

```bash
cd /tmp
git clone https://github.com/Shakargy/devtime.git devtime-clean-test
cd devtime-clean-test
python -m venv .venv
source .venv/Scripts/activate       # or .venv/bin/activate
pip install -e ".[dev]"
pytest
cd examples/demo-saas
dtc init && dtc scan && dtc concepts && dtc explain "Billing Webhooks"
```
