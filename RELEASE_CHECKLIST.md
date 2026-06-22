# Release Checklist

Gate for taking DevTime from private to public. Current target tag:
`v0.0.3-public-candidate`. **The repository stays private until a human approves the
public release gate.**

## 1. Code health

- [x] No local DB committed (`.devtime/`, `*.sqlite` ignored and absent from tree)
- [x] No `.devtime/` committed
- [x] No secrets committed (privacy fixture uses an ignored `secrets.env` with fake values)
- [x] No generated caches committed (`__pycache__`, `*.egg-info`, `.pytest_cache` ignored)
- [x] No AI authorship traces (project policy: none in code, commits, or PR bodies)
- [x] Clean `git status` on the release branch

## 2. Tests

- [x] `pytest` passes (33 passed)
- [x] Fixture runner passes (16 fixtures)
- [x] Trust-law tests pass (no claim without evidence; usage is not decision)
- [x] Privacy fixtures pass (ignored secrets never become evidence)
- [x] Risk fixtures pass (retry-without-test flagged)

## 3. CI

- [x] Green from a clean clone (`.github/workflows/ci.yml`)
- [x] Advisory GitHub Action exits 0 (`.github/workflows/devtime-risk-review.yml`)
- [x] No blocking PR behavior yet (risk review is advisory)

## 3b. Trust repair gates (v0.0.6)

- [x] Risk review states verified (`review_failed` / `no_findings` / `unsupported_change_class` / `finding`)
- [x] Git diff failure is `review_failed`, not `no_findings`
- [x] JWT algorithm weakening (→ `none`) flagged high
- [x] Billing Webhooks false positives fixture-guarded (calendar/credential/generic/dep-only)
- [x] Word-sense gates verified (session_id, NEXTAUTH_URL, invitation JWT, job title, avatar URL, model download)
- [x] Low-confidence concepts do not claim "is present"
- [x] Decisions must be corroborated to clear uncertainty
- [x] Context pack noise checked (limited for weak concepts; tests capped + reasoned)
- [x] Understanding Score/Debt wording fixed; no hidden freshness points
- [x] Closed ontology disclosed (six families)
- [x] Framework coverage warnings (Django / NestJS)
- [x] MCP `start` does not pretend to start a server
- [x] Bracketed paths render literally
- [x] External reviewer failures converted to fixtures or documented limitations

## 3c. Evidence precision gates (v0.0.7)

- [x] Billing Webhooks requires local payment-provider evidence (negative contexts suppressed)
- [x] High-confidence Authentication requires direct auth evidence (word-sense pollution filtered)
- [x] Context Pack reasons are truthful ("same directory" / "imports the implementation", no false "same module")
- [x] Employment job-title/role taxonomy excluded from Background Jobs
- [x] Direct `bg_tasks` tests attach to Background Jobs
- [x] Package version is `0.0.7` (not `0.1.0`)

## 4. Privacy

- [x] No network during scan
- [x] No code execution during scan
- [x] Ignored directories pruned before traversal
- [x] Ignored secrets never become evidence (covered by tests)

## 5. Documentation

- [x] README explains the trust model and links to LIMITATIONS.md
- [x] QUICKSTART works from a clean clone (verified)
- [x] PROOF.md has real before/after examples
- [x] LIMITATIONS.md is visible and linked from README
- [x] DEMO_SCRIPT.md tested (commands run, risk step verified)

## 6. Demo

- [x] Demo commands verified end to end
- [x] Safe demo diff documented with revert step
- [ ] 2–3 minute demo video recorded *(pending — human)*

## 7. Packaging

- [x] `pyproject.toml` is correct (`requires-python = ">=3.11"`, `dtc` entry point)
- [x] Install command verified: `pip install -e ".[dev]"`
- [ ] (Optional later) publish to PyPI — not required for private reviewers

## 8. GitHub readiness

- [x] README.md, QUICKSTART.md, PROOF.md, LIMITATIONS.md, DEMO_SCRIPT.md, RELEASE_CHECKLIST.md present
- [x] `.gitignore`, `.gitattributes`, CI workflows present
- [x] **LICENSE chosen** — Apache-2.0 (`LICENSE`, declared in `pyproject.toml`)
- [ ] Repository description / topics set on GitHub *(human)*

## 9. Public release gate (all must be true)

- [ ] A stranger can install and run the demo in under 10 minutes
- [x] Known limitations are visible (LIMITATIONS.md, linked from README)
- [ ] Demo video recorded
- [ ] First 5–10 private reviewers have tested it
- [ ] No major confusion reported about the README
- [x] LICENSE chosen (Apache-2.0)
- [ ] **Human approves flipping the repo to public**

## 10. Post-release feedback loop

- [ ] Issue template for "DevTime got this wrong" → convert to a fixture
- [ ] Triage false positives / false negatives into fixtures
- [ ] Track which frameworks reviewers tried (coverage gaps → next fixtures)
- [ ] Re-run Reality Validation on new community repos

---

**Status:** ready for **private reviewers**. Not yet ready for **public** — remaining
blockers: a recorded demo video and reviewer feedback (LICENSE is now Apache-2.0).
