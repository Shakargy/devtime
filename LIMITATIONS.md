# Limitations

DevTime is an early, local-first V0. It is deliberately honest about what it cannot
do. Read this before trusting any single output.

## 1. Current limitations

- DevTime is a **heuristic scanner**, not a full semantic compiler or type-aware
  analyzer. It reasons from patterns in code, paths, tests, configs, and docs.
- **Closed concept ontology.** V0 only detects six supported concept families
  (Authentication, Billing Webhooks, Background Jobs, Data Export, Admin Permissions,
  File Uploads). It does **not** discover arbitrary domain concepts. Anything else is
  out of scope.
- **Word-sense detection is heuristic.** Gates reduce false positives (a job *title*
  is not a Background Job; an avatar *URL* is not a File Upload; a calendar
  *subscription* is not a Billing Webhook), but they are pattern-based and imperfect.
- It builds **local repository memory** only. There is no cloud, no team sync, and
  no shared state between machines.
- There is **no UI**. DevTime is a command-line tool.
- **Understanding Debt is a product signal, not an objective universal truth.** It is
  a useful, explainable heuristic for "how well can this concept be explained from
  evidence?" - not a grade of code quality.

## 2. Accuracy limitations

- **False positives are possible.** DevTime may name or claim a concept that is not
  really there. The file-local evidence gating reduces this, but cannot eliminate it.
- **False negatives are possible.** DevTime may miss a real concept whose evidence it
  cannot parse (e.g. an unsupported framework or an unusual code style).
- Confidence scores and Understanding Debt are **relative heuristics**, calibrated on
  fixtures, not absolute measurements.

## 3. Framework coverage limitations

- DevTime is currently strongest on repositories that resemble its fixtures:
  **TypeScript / JavaScript (Express, named routers, Next.js App Router)** and
  **Python (FastAPI-style routes, Celery-style workers)**.
- Frameworks **not** yet parsed include NestJS, Django, Flask, Rails, Spring, Go
  HTTP frameworks, and many others. On these, detection degrades to weak,
  dependency-level evidence (and DevTime should say so via uncertainty).

## 4. Risk review limitations

- `dtc risk --diff` is **advisory**. It is not a gate and must not block PRs.
- It reviews a git diff against local memory using heuristics; it does not prove a
  change is broken, and it can both miss real risks and surface ones that turn out to
  be fine.
- Risk findings are keyed to a **narrow** set of known change classes (e.g. JWT
  algorithm weakening; retry/idempotency on billing webhooks). Most changes to a known
  concept return **`unsupported_change_class`** - meaning "a tracked file changed but
  V0 has no rule for this change; review it manually" - not a clean bill of health.
- The result states are explicit: `review_failed`, `no_findings`,
  `unsupported_change_class`, `finding`. A git failure is `review_failed`, never
  `no_findings`.

## 5. Privacy and security boundaries

- DevTime runs locally: **no network access and no code execution during a scan.**
- Ignored directories are pruned before traversal; ignored files and secrets are
  excluded from evidence by design.
- These are engineering boundaries enforced by code and tests, **not** a formal
  security guarantee or audit. Review `dtc doctor --privacy` output for your repo.

## 6. AI and MCP limitations

- **No AI provider is wired.** DevTime never calls a model. AI narration is an
  intentional future option, not part of V0.
- **MCP transport is not wired.** The tool surface, schemas, and read-only permission
  model exist in code, but there is no live server you can connect an agent to yet.

## 7. Performance limitations

- Scans prune ignored directories before traversal, which makes them fast on typical
  repos (sub-second on the demo; ~0.5s on a 355-file real repo).
- **Very large repositories can take much longer.** Private reviewers saw scans of
  tens of seconds to several minutes on large monorepos (tens of thousands of files).
  `dtc scan` prints a local progress heartbeat and a boundary report (files scanned,
  pruned directories, skipped files, duration); this is local only - no telemetry.
- Detection is single-pass and in-process; there is no incremental/cached scan yet.

## 8. What is intentionally not built yet

To keep V0 trustworthy rather than large, the following are deliberately **out of
scope** for now:

- git-history signals (freshness, ownership, lineage from commits)
- wired MCP transport / write-enabled MCP tools
- an AI provider integration
- a UI
- cloud, team sync, and enterprise policy layers
- billing, auth, and multi-user features

---

*Trust before novelty. DevTime aims to be embarrassingly clear about both its promise
and its limits.*
