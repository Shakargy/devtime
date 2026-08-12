# DevTime v0.5.0 - claims that fire on ordinary repositories

The verification layer had a coverage problem. Its two claims (billing webhooks,
JWT) only apply to repositories that happen to have billing or JWT code. Run
against three realistic open-source repositories, `dtc verify` produced nothing
useful on two of them. Honest, but useless.

This release fixes that: claims that apply to ordinary repositories, plus an
output that never dead-ends. No cloud, no telemetry, no AI, no code execution -
unchanged.

## Two new built-in claims

**route-test-coverage** - "HTTP routes are exercised by tests."

```text
Route Test Coverage
Status: WEAK

Why:
  - 6 of 15 routes have a referencing test.

Missing evidence:
  - Tests referencing 9 route(s): /api/items/{id}, /api/login/access-token, ...
```

Routes and tests are the two most abundant kinds of evidence in almost every
server repository, so this claim fires nearly everywhere. Attribution is by test
imports and route names, and end-to-end specs are excluded because they match by
accident. Absence of tests is missing evidence, never a contradiction.

**admin-authorization** - "Administrative routes require an authorization check."

A missing authorization signal is reported as WEAK, never CONTRADICTED.
Authorization can be applied globally, by a router mount, or by a framework
decorator the scanner does not parse. Reporting an endpoint as unprotected when
it is not would destroy the trust this tool is built on, so DevTime says what it
found and what it cannot see.

## New status: NOT_APPLICABLE

A repository with no billing code is not "unknown" for a billing claim. The
claim simply does not apply. NOT_APPLICABLE says that plainly, and UNKNOWN is
now reserved for the harder case: the surface exists but the evidence cannot
decide.

## dtc verify is a report card

Findings first (contradictions before everything else), then a compact list of
claims that do not apply and why.

When nothing applies, DevTime no longer dead-ends. It reports what it scanned,
what evidence it collected, what would make a claim verifiable, and states
plainly that this is a coverage limit rather than a verdict on your code:

```text
No built-in claim applies to this repository yet.

DevTime scanned 129 files and found 199 signals.
Evidence collected: doc=199

Built-in claims become verifiable when a repository has:
  - HTTP routes and tests (route-test-coverage)
  ...

This is a coverage limit, not a verdict on your repository.
```

`dtc verify --list` now shows which claims apply to the current repository.

## Fixed: MCP SDK 2.0 broke every fresh install

The MCP Python SDK released 2.0.0, which removed `mcp.server.fastmcp`. Any new
`pipx install "devtime-ei[mcp]"` resolved to the new SDK and could not start the
server at all. DevTime now supports both SDK generations (`MCPServer` in 2.x,
`FastMCP` in 1.x), verified against both, with a regression test so a future
rename cannot pass silently.

If you installed the MCP extra recently and `dtc mcp start` failed, this
release fixes it.

## Compatibility

- JSON output is `schema_version: 2`. Every version 1 field is unchanged; the
  only addition is the NOT_APPLICABLE status value.
- Results that do not apply are no longer stored. Storing them would pollute
  freshness and diff impact with claims that have no evidence.
- No command, concept, or MCP tool was renamed or removed.

## Notes

- 142 passing tests (20 new).
- Verified against three real repositories: an Express-based project went from
  no findings to "59 of 133 routes have a referencing test"; a FastAPI template
  went to "6 of 15 routes" plus SUPPORTED JWT authentication; a Go project
  correctly reports that no claim applies and explains why.
- `dtc verify` remains sub-second on a repository with 133 routes and thousands
  of tests.
- A secret-handling claim was investigated and deliberately not built: DevTime
  hard-denies secret files from scanning, so evidence for that claim cannot
  exist without breaking the trust model.

## Names

- PyPI distribution: `devtime-ei`. Python import: `devtime`. CLI: `dtc`.
