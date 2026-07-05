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
IMPLEMENTED_TOOLS = ("list_concepts", "explain_concept", "get_context_pack")

_NOT_INITIALIZED = {
    "error": "not_initialized",
    "hint": "No .devtime memory found in the current directory. "
    "Run `dtc init` then `dtc scan` in the repository first.",
}


class McpDependencyMissing(RuntimeError):
    """Raised when the optional MCP SDK is not installed."""

    INSTALL_HINT = 'MCP support needs the optional dependency: pip install "devtime-ei[mcp]"'


def build_server():
    """Build the FastMCP server with the read-only tool surface registered."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised via CLI test
        raise McpDependencyMissing(McpDependencyMissing.INSTALL_HINT) from exc

    server = FastMCP(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)

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

    return server


def run_stdio() -> None:
    """Run the read-only MCP server over stdio (blocks until the client disconnects)."""
    build_server().run()
