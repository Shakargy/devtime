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
    lines = [
        "DevTime MCP (local, read-only by default)",
        "  bind: 127.0.0.1",
        "  read_source: false",
        "  write tools: disabled",
        "",
        "Read tools:",
    ]
    lines += [f"  - {t}" for t in schemas.TOOLS["read"]]
    lines += ["Context tools:"]
    lines += [f"  - {t}" for t in schemas.TOOLS["context"]]
    lines += ["Review tools:"]
    lines += [f"  - {t}" for t in schemas.TOOLS["review"]]
    lines += [
        "",
        "Note: transport binding is wired in a later milestone; "
        "tool logic is available via devtime.mcp.tools.",
    ]
    return "\n".join(lines)


def describe_permissions() -> str:
    return json.dumps(schemas.DEFAULT_PERMISSIONS, indent=2)
