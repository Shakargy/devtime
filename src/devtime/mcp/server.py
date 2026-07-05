"""MCP server description (Builder Edition, Chapter 16).

v0.1.2: the stdio transport is implemented for the read-only tool subset in
devtime.mcp.transport. The remaining planned tools stay listed as planned so
the preview output never overclaims.
"""

from __future__ import annotations

import json

from devtime.mcp import schemas
from devtime.mcp.transport import IMPLEMENTED_TOOLS


def describe_server() -> str:
    """Honest preview: implemented tools are separated from planned ones."""
    planned_read = [t for t in schemas.TOOLS["read"] if t not in IMPLEMENTED_TOOLS]
    planned_context = [t for t in schemas.TOOLS["context"] if t not in IMPLEMENTED_TOOLS]
    lines = [
        "MCP transport: stdio, read-only, local only.",
        'Requires the optional dependency: pip install "devtime-ei[mcp]"',
        "Start with: dtc mcp start (stdout is the protocol stream).",
        "",
        "Implemented tools:",
    ]
    lines += [f"  - {t}" for t in IMPLEMENTED_TOOLS]
    lines += ["Planned read tools (not implemented yet):"]
    lines += [f"  - {t}" for t in planned_read]
    lines += ["Planned context tools (not implemented yet):"]
    lines += [f"  - {t}" for t in planned_context]
    lines += ["Planned review tools (not implemented yet):"]
    lines += [f"  - {t}" for t in schemas.TOOLS["review"]]
    lines += [
        "",
        "Write tools are not exposed. No network listener. No source code is returned.",
    ]
    return "\n".join(lines)


def describe_permissions() -> str:
    return json.dumps(schemas.DEFAULT_PERMISSIONS, indent=2)
