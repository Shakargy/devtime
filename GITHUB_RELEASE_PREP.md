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

## Repo metadata fields (TODO)

```
Website:    TODO
Demo video: TODO — upload devtime-demo-v0.0.8.mp4 after the repo becomes public,
            then add the public link to README.md (## Demo) and the release notes.
```

Demo assets (local, not in the repo):
- Video: `devtime-demo-v0.0.8.mp4` (2:02, 1920×1080, silent/caption-driven)
- Thumbnail: `devtime-demo-thumbnail-v0.0.8.png` (1920×1080)

---

## Final Public Release Gate

All must be true before flipping the repo to public. Check, don't assume.

- [ ] Repo visibility still **private** until final approval
- [x] Tests pass (88)
- [x] Clean-clone install works (see CLEAN_INSTALL_CHECK.md)
- [ ] Package version decision made (currently `0.0.7`; bump to `0.1.0` only at release)
- [ ] `v0.1.0` release tag **not** created until final approval
- [ ] README has the public demo link (currently a placeholder)
- [ ] Demo video uploaded somewhere public
- [x] Thumbnail ready (`devtime-demo-thumbnail-v0.0.8.png`)
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
- [ ] Final clean-clone test completed on the release commit
- [ ] Release notes reviewed (RELEASE_NOTES_v0.1.0_DRAFT.md)
- [ ] Launch post reviewed (LAUNCH_POSTS.md)

### Recommended release sequence (when approved)

1. Decide the version (bump `pyproject.toml` + `__init__.py` to `0.1.0` if releasing as v0.1.0).
2. Upload the demo video publicly; replace the README `## Demo` placeholder with the link.
3. Final clean-clone test on the release commit.
4. Tag `v0.1.0`, push.
5. Flip repository visibility to **public**.
6. Publish the GitHub Release using RELEASE_NOTES_v0.1.0_DRAFT.md.
7. Post the launch messages (LAUNCH_POSTS.md).
