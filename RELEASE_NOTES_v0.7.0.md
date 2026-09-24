# DevTime v0.7.0 - review a change by what it does to your claims

A reviewer does not need a list of changed files. They need to know what the
change did to what the repository can support. `dtc review` answers that.

```bash
dtc review --base origin/main
```

```text
Regression: admin-authorization  SUPPORTED -> WEAK
  base: 1 of 1 administrative route(s) have an authorization guard at their own call site.
  head: 1 of 2 administrative route(s) have an authorization guard at their own call site.
  changed evidence: src/admin/panel.ts
  missing now: Authorization evidence for: GET /admin/export (src/admin/panel.ts)
```

No cloud, no telemetry, no AI, no code execution - unchanged.

## How it works

- Compares **merge-base..head**, the range a pull request's "Files changed" tab
  shows. Commits added to the base branch after the change branched off are not
  attributed to it.
- Extracts both commits with `git archive` into a temporary directory DevTime
  creates and removes. Your working tree, index, branch, worktree list, and
  `.devtime/` are never touched.
- Verifies every built-in claim at both commits and reports one transition per
  claim: regression, newly applicable, no longer applicable, improvement,
  evidence changed, or unchanged. Unchanged claims are counted, not repeated.
- A renamed file is matched through both its old and new path.
- Run from a subdirectory, it reviews that subdirectory.

Output as text, JSON (`--format json`, `--json-out PATH`), or Markdown for a
GitHub job summary (`--format markdown`).

## A review that could not run never looks clean

Exit 0 means the review ran; findings do not change it, because reviews are
advisory. Exit 1 means it could not run, and the output says why:

```text
DevTime review could not be completed.
  reason: could not compute a merge base
  hint:   This clone is shallow, so the common ancestor is not available. In
          GitHub Actions use actions/checkout with fetch-depth: 0.
This is a failed review, not a clean one. No findings were produced.
```

Exit 7 is opt-in: `--fail-on-regression` fails when a claim regresses.

## The CI workflow now works as intended

The previous workflow scanned once with no baseline, so the claim-impact
mechanism it relied on had nothing to compare against. It also held a
`pull-requests: write` permission it never used. It now runs `dtc review`
against the pull request's merge base, publishes a job summary and a JSON
artifact, runs on `pull_request` with a read-only token, and posts nothing. A
copy-paste workflow for other repositories is in VERIFICATION.md.

## Found by running DevTime on its own repository

Building the CI workflow meant pointing DevTime at itself first. That surfaced
three real bugs, all fixed:

**DevTime found its own search pattern and called it evidence.** The Python
extractor contains the literal `"stripe.Webhook.construct_event"`, because that
is what it looks for. Signature detection was a plain substring match, so
scanning DevTime reported billing webhook signature verification as SUPPORTED
in a repository with no billing code. Detection now requires an actual call in
executable code: a small lexer blanks comments and string literals first,
keeping offsets so line numbers still map. Verification signals now record the
line they were found on.

**Fixture routes counted as application surface for two of three claims.**
v0.5.1 excluded test, example, and fixture routes from route test association
but not from admin authorization or billing webhook signatures. On DevTime's own
repository, 15 "billing webhook handlers" came almost entirely from `fixtures/`.
The exclusion now applies to every claim. DevTime's repository also gains a
`.devtimeignore` for its own fixture corpora.

**A filename was evidence again.** An `import express` inside a file named
`stripe-webhook.ts` counted as "a payment provider dependency is declared",
because matching searched text that included the file path. That is the same
class of bug v0.5.1 fixed for admin routes. Provider dependencies now match on
the dependency's own name.

A fourth bug was caught before release while testing `dtc review` itself:
`git archive` is relative to the current directory, so a review run from a
subdirectory compared two empty snapshots and reported nothing changed. It now
archives from the repository root, and an empty comparison is reported as a
failure or a warning, never as a clean result.

And one from the release's own pull request, which ran the new workflow on
DevTime: that PR adds a `.devtimeignore`, so the merge base scanned DevTime's
packaged demo and the head did not. The review reported `jwt-authentication`
as a regression when no code had changed; only the scanned surface had. A
review now discloses when a change edits ignore rules (`scan_policy_changed`
in JSON, plus a warning), so a change in what DevTime scans is not mistaken for
a change in what the code does.

## Compatibility

- New command `dtc review`; no command, claim id, or MCP tool was renamed or
  removed.
- Signature-verification detection is stricter (a real call, not a mention) and
  slightly broader (`stripeClient.webhooks.constructEvent` and
  `constructEventAsync` now resolve).
- New exit code 7, only with `--fail-on-regression`.
- The CI workflow's display name changes to `devtime-review`; its job id stays
  `devtime`.

## Notes

- 215 passing tests (42 new): transition classification, merge-base
  semantics, multi-commit pull requests, renames, deletions, subdirectory scope,
  shallow clones, unknown refs, workspace cleanup, a repository left untouched,
  ignore-rule changes, the lexer, and every self-scan finding above.
- Known limits: uncommitted changes are not reviewed, a local untracked
  `.devtimeignore` is not applied to snapshots, and transitions inherit every
  static-analysis limit of `dtc verify`. See LIMITATIONS.md.

## Names

- PyPI distribution: `devtime-ei`. Python import: `devtime`. CLI: `dtc`.
