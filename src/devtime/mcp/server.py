"""MCP server description (Builder Edition, Chapter 16).

V0 ships the tool surface, schemas, and permission model. The actual transport
(stdio/socket via an MCP SDK) is wired in a later milestone; this module makes
the read-only contract inspectable today.
"""

from __future__ import annotations

import json

from devtime.intelligence.context_pack import generate_context_pack  # noqa: F401
from devtime.mcp import schemas


def describe_server() -> str:
    """Honest preview output (Trust Repair v0.0.6): no server is started, and no
    bind address is shown, because the MCP transport is not implemented in V0."""
    lines = [
        "MCP transport is not implemented in V0.",
        "No server was started.",
        "This command is a preview of planned read-only MCP tools.",
        "",
        "Planned read tools:",
    ]
    lines += [f"  - {t}" for t in schemas.TOOLS["read"]]
    lines += ["Planned context tools:"]
    lines += [f"  - {t}" for t in schemas.TOOLS["context"]]
    lines += ["Planned review tools:"]
    lines += [f"  - {t}" for t in schemas.TOOLS["review"]]
    return "\n".join(lines)


def describe_permissions() -> str:
    return json.dumps(schemas.DEFAULT_PERMISSIONS, indent=2)
