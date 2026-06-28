# Contributing to DevTime

Thanks for helping. The single most valuable contribution is a **fixture** - a small
repository pattern that captures something DevTime got wrong (or should keep getting
right) so it can never silently regress.

## The best contribution is a fixture

A fixture is a tiny repo plus the expected output: which concepts should (or should
not) be detected, which claims are allowed, which are forbidden, and what uncertainty
is required. When DevTime is wrong on real code, turning that into a fixture is what
makes the fix permanent. See `fixtures/` for the format and `tests/` for how they run.

## "DevTime got this wrong" reports are valuable

If DevTime over-claims, under-claims, mislabels a concept, or misses one, please open
a **"DevTime got this wrong"** issue (there is a template). Include:

- a minimal reproduction (a tiny sanitized repo or snippet) or the public repo + path
- the exact command you ran (e.g. `dtc explain "Authentication"`)
- the expected output
- the actual output
- why the claim is too strong, too weak, or missing

Please do **not** include secrets or private source. File paths and small sanitized
snippets are enough. If you can, attach a small fixture repo/pattern that reproduces
it.

## Trust rules contributions must preserve

DevTime is a trust system. Any change must keep these true:

- no claim without evidence
- weak or missing evidence produces uncertainty, not confidence
- no network access and no code execution during a scan
- ignored files and secrets never become evidence
- risk review is advisory (it does not block PRs)

## Local dev workflow

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

Run the full suite before opening a PR; new behavior should come with a fixture or
test that pins it.
