"""Read-only MCP stdio transport (v0.1.2).

Wires the three implemented read tools to a real MCP server over stdio so
coding agents (Claude Code, Cursor, and other MCP clients) can query local
DevTime memory.

Trust model, unchanged:
  - read-only: no write tools are exposed
  - local only: stdio transport, no network listener
  - no source code is returned, only claims, evidence paths, and uncertainty
  - requires the optional dependency: pip install "devtime-ei[mcp]"

IMPORTANT: stdout belongs to the JSON-RPC stream. Nothing here may print to
stdout; diagnostics go to stderr.
"""

from __future__ import annotations

from devtime import paths
from devtime.mcp import tools

SERVER_NAME = "devtime"

SERVER_INSTRUCTIONS = (
    "DevTime is local, evidence-backed repository memory. "
    "Every claim links to evidence files; weak evidence is reported as "
    "uncertainty, not confidence. Use list_concepts to discover what the "
    "scanned repository supports, explain_concept for claims and evidence "
    "behind one concept, and get_context_pack for a governed context bundle "
    "before changing code related to a concept. If results are empty, the "
    "repository has not been scanned: run `dtc init` and `dtc scan` there first."
)

# The subset of the planned tool surface that is implemented and exposed.
IMPLEMENTED_TOOLS = (
    "list_concepts",
    "explain_concept",
    "get_context_pack",
    "verify_claim",
)

_NOT_INITIALIZED = {
    "error": "not_initialized",
    "hint": "No .devtime memory found in the current directory. "
    "Run `dtc init` then `dtc scan` in the repository first.",
}


class McpDependencyMissing(RuntimeError):
    """Raised when the optional MCP SDK is not installed."""

    INSTALL_HINT = 'MCP support needs the optional dependency: pip install "devtime-ei[mcp]"'


def _server_class():
    """Return the SDK's server class across MCP SDK generations.

    The SDK renamed its high-level server in 2.0: `mcp.server.fastmcp.FastMCP`
    became `mcp.server.MCPServer`. Both expose the surface DevTime uses (a
    `tool()` decorator, async `list_tools`/`call_tool`, and a stdio `run`), so
    both are supported rather than pinning users to one generation.
    """
    try:  # MCP SDK 2.x
        from mcp.server import MCPServer

        return MCPServer
    except ImportError:
        pass
    try:  # MCP SDK 1.x
        from mcp.server.fastmcp import FastMCP

        return FastMCP
    except ImportError as exc:  # pragma: no cover - exercised via CLI test
        raise McpDependencyMissing(McpDependencyMissing.INSTALL_HINT) from exc


def build_server():
    """Build the MCP server with the read-only tool surface registered."""
    server_class = _server_class()
    server = server_class(name=SERVER_NAME, instructions=SERVER_INSTRUCTIONS)

    @server.tool()
    def list_concepts(limit: int = 50) -> list[dict] | dict:
        """List concepts detected in the scanned repository with confidence labels.

        Start here to discover what the repository memory contains. Returns
        concept names, slugs, and confidence labels. No source code.
        """
        if not paths.is_initialized():
            return _NOT_INITIALIZED
        return tools.list_concepts(limit=limit)

    @server.tool()
    def explain_concept(concept: str) -> dict:
        """Explain one concept from evidence: claims, evidence file paths, uncertainty, and Understanding Score.

        Claims are evidence-linked; uncertainty lists what the repository
        cannot prove yet. human_review_required is true when uncertainty
        exists. No source code is returned, only file paths.
        """
        if not paths.is_initialized():
            return _NOT_INITIALIZED
        return tools.explain_concept(concept)

    @server.tool()
    def get_context_pack(concept: str, mode: str = "risk") -> dict:
        """Get a governed context pack for a concept before changing related code.

        Includes supported claims, corroborated decisions, uncertainty,
        do-not-change-without-review paths, tests to run, and agent guidance.
        Modes: risk (default), onboarding.
        """
        if not paths.is_initialized():
            return _NOT_INITIALIZED
        return tools.get_context_pack(concept, mode=mode)

    @server.tool()
    def verify_claim(claim_id: str = "") -> dict:
        """Verify a repository claim against scanned evidence (read-only compute).

        Returns status (SUPPORTED / WEAK / CONTRADICTED / UNKNOWN /
        NOT_APPLICABLE), why, supporting evidence with file paths, both-sided
        contradictions, missing evidence, and coverage limitations.
        NOT_APPLICABLE means the repository has no surface this claim is about,
        which is different from UNKNOWN (surface exists, evidence cannot
        decide). Call with no claim_id to list the built-in claims. Results are
        computed fresh and NOT persisted (this server stays read-only); use
        `dtc verify` in a terminal to record one.
        """
        if not paths.is_initialized():
            return _NOT_INITIALIZED
        from devtime.db import connection
        from devtime.intelligence import verification as ver

        conn = connection.connect()
        try:
            if not claim_id:
                return {
                    "builtin_claims": [
                        {
                            "claim_id": d.slug,
                            "name": d.name,
                            "statement": d.statement,
                        }
                        for d in ver.BUILTIN_CLAIMS.values()
                    ]
                }
            try:
                result = ver.verify_claim(conn, claim_id)
            except KeyError:
                return {
                    "error": "unknown_claim",
                    "hint": "Call verify_claim with no claim_id to list built-in claims.",
                }
            payload = result.to_dict()
            # An agent cannot see the user's working tree, so it must be told
            # which snapshot this conclusion came from and whether that snapshot
            # is still current.
            state = ver.scan_state(conn)
            payload["evidence_snapshot"] = state
            if state.get("working_tree") == "changed_since_scan":
                payload["staleness_warning"] = (
                    "This result was computed from a stored scan that no longer "
                    "matches the working tree. Files changed since the scan: "
                    + ", ".join(state.get("changed_paths", [])[:5])
                    + ". Ask the user to run `dtc scan` before relying on it."
                )
            return payload
        finally:
            conn.close()

    return server


def run_stdio() -> None:
    """Run the read-only MCP server over stdio (blocks until the client disconnects)."""
    build_server().run()
