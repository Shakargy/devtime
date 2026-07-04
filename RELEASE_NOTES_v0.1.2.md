# DevTime v0.1.2 - read-only MCP server for coding agents

DevTime memory is now available to coding agents. `dtc mcp start` runs a local,
read-only MCP server over stdio, so agents like Claude Code can query
evidence-backed repository memory instead of guessing. No changes to concept
detection, risk review, or scanner behavior.

## Highlights

- **New: `dtc mcp start`**: a real MCP stdio server exposing three read-only tools:
  - `list_concepts` - detected concepts with confidence labels
  - `explain_concept` - claims, evidence file paths, uncertainty, Understanding Score
  - `get_context_pack` - governed context with do-not-change-without-review paths,
    tests to run, and agent guidance
- **Optional dependency**: MCP support is an extra, so the core install stays lean:
  `pipx install "devtime-ei[mcp]"`
- **One-line agent setup** for Claude Code:
  `claude mcp add devtime -- dtc mcp start`
- `dtc mcp preview` now shows which tools are implemented vs planned.

## Trust model (unchanged, now enforced by a real server)

- Read-only: no write tools are exposed.
- Local stdio only: no network listener.
- No source code is returned: claims, evidence file paths, and uncertainty only.
- Weak evidence is reported as uncertainty, not confidence.
- If the repository is not scanned, tools return a clear not_initialized error.

## Try it

```bash
pipx install "devtime-ei[mcp]"
cd your-repo
dtc init
dtc scan
claude mcp add devtime -- dtc mcp start
```

Then ask your agent things like "what concepts does this repo support?" or "get the
context pack for Billing Webhooks before I change it."

## Names

- The PyPI distribution is `devtime-ei`.
- The Python import package remains `devtime`.
- The CLI command remains `dtc`.

## Notes

- 104 passing tests (7 new for the MCP transport, including registration, calls
  against a scanned demo repo, and the not-initialized guard).
- End-to-end verified with the official MCP Python client over stdio.
- No cloud, no telemetry, no AI, no code execution added.
