# GitHub Release Prep

Recommendations for the GitHub repository's public-facing settings and the gate that
must pass before the repo goes public. **Nothing here is applied automatically** — a
human sets the GitHub fields and flips visibility.

> The repository is still **PRIVATE**. Do not make it public until the Final Public
> Release Gate (below) passes and a human approves.

## Recommended GitHub description

```
Local-first Engineering Intelligence for software repositories.
```

## Recommended GitHub topics

```
developer-tools
cli
software-engineering
code-intelligence
repository-analysis
local-first
static-analysis
engineering-intelligence
developer-productivity
architecture
technical-debt
python
sqlite
open-source
```

## Repo metadata fields

```
Website:    TODO (optional)
Demo video: https://youtu.be/1Hiu3Y9J_SI  (linked from README ## Demo)
```

Release assets:
- Demo video (YouTube): https://youtu.be/1Hiu3Y9J_SI
- Thumbnail in repo: `assets/devtime-demo-thumbnail-v0.1.0.png` (1920×1080)
- Final release notes: `RELEASE_NOTES_v0.1.0.md`
- **Package version decision: `0.1.0`** for the public release (bumped on the
  `v0.1.0-release-candidate` branch).

---

## Final Public Release Gate

All must be true before flipping the repo to public. Check, don't assume.

- [ ] Repo visibility still **private** until final approval (flip is the explicit final manual step)
- [x] Tests pass (88)
- [x] Clean-clone install works (see CLEAN_INSTALL_CHECK.md and the record below)
- [x] Package version decision made — **`0.1.0`** (bumped on `v0.1.0-release-candidate`)
- [ ] `v0.1.0` release tag **not** created until final approval
- [x] README has the public demo link (https://youtu.be/1Hiu3Y9J_SI)
- [x] Demo video uploaded publicly (YouTube)
- [x] Thumbnail in repo (`assets/devtime-demo-thumbnail-v0.1.0.png`)
- [x] LICENSE present (Apache-2.0)
- [x] Limitations visible (LIMITATIONS.md, linked from README)
- [x] Issue template present (`.github/ISSUE_TEMPLATE/devtime-got-this-wrong.yml`)
- [x] No local DB committed (`*.sqlite` ignored/absent)
- [x] No `.devtime/` committed
- [x] No secrets committed
- [x] No AI-authorship traces (project policy)
- [ ] GitHub description set (recommendation above)
- [ ] GitHub topics set (recommendation above)
- [ ] 5–10 reviewers completed, or final approval given
- [x] Final clean-clone test completed on the release-candidate branch (record below)
- [x] Release notes finalized (`RELEASE_NOTES_v0.1.0.md`)
- [x] Launch post updated with demo link (`LAUNCH_POSTS.md`)

### Final clean-clone test record

| Field | Result |
|-------|--------|
| Date | 2026-06-23 |
| OS | Windows 11 (Git Bash) |
| Python | 3.11.9 |
| Branch | `v0.1.0-release-candidate` |
| Install command | `pip install -e ".[dev]"` |
| Test result | **88 passed** |
| Package version | **0.1.0** |
| Demo repo smoke | `dtc init` / `scan` / `concepts` / `explain "Billing Webhooks"` → Score 58/100, missing-decision uncertainty (as documented) |
| Issue found | none |

### Recommended release sequence (when approved)

1. Decide the version (bump `pyproject.toml` + `__init__.py` to `0.1.0` if releasing as v0.1.0).
2. Upload the demo video publicly; replace the README `## Demo` placeholder with the link.
3. Final clean-clone test on the release commit.
4. Tag `v0.1.0`, push.
5. Flip repository visibility to **public**.
6. Publish the GitHub Release using RELEASE_NOTES_v0.1.0_DRAFT.md.
7. Post the launch messages (LAUNCH_POSTS.md).
