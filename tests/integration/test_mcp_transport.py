"""Tests for the read-only MCP stdio transport (v0.1.2).

The transport exposes exactly three read-only tools backed by local memory.
These tests cover tool registration, calls against a scanned demo repo, the
not-initialized guard, and the CLI surface. The blocking stdio loop itself is
not run inside pytest; an end-to-end client check lives in PACKAGING.md.
"""

import asyncio

from typer.testing import CliRunner

from devtime.cli import app
from devtime.mcp.transport import IMPLEMENTED_TOOLS, build_server

runner = CliRunner()


def _scanned_demo(tmp_path, monkeypatch):
    """Create a demo repo copy, init and scan it, and chdir into it."""
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["demo", "init"]).exit_code == 0
    monkeypatch.chdir(tmp_path / "devtime-demo-saas")
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["scan"]).exit_code == 0


def test_server_registers_exactly_the_implemented_tools():
    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = sorted(t.name for t in tools)
    assert names == sorted(IMPLEMENTED_TOOLS)


def test_list_concepts_via_server(tmp_path, monkeypatch):
    _scanned_demo(tmp_path, monkeypatch)
    server = build_server()
    result = asyncio.run(server.call_tool("list_concepts", {}))
    text = str(result)
    assert "Billing Webhooks" in text
    assert "Authentication" in text


def test_explain_concept_via_server_includes_uncertainty(tmp_path, monkeypatch):
    _scanned_demo(tmp_path, monkeypatch)
    server = build_server()
    result = asyncio.run(
        server.call_tool("explain_concept", {"concept": "Billing Webhooks"})
    )
    text = str(result)
    assert "Billing Webhooks" in text
    assert "uncertainty" in text
    # evidence paths, never source code
    assert "stripe-webhook.ts" in text


def test_context_pack_via_server(tmp_path, monkeypatch):
    _scanned_demo(tmp_path, monkeypatch)
    server = build_server()
    result = asyncio.run(
        server.call_tool("get_context_pack", {"concept": "Billing Webhooks"})
    )
    text = str(result)
    assert "Billing Webhooks" in text
    assert "agent_guidance" in text


def test_not_initialized_returns_error_not_crash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = build_server()
    result = asyncio.run(server.call_tool("list_concepts", {}))
    text = str(result)
    assert "not_initialized" in text
    assert "dtc init" in text


# --- CLI surface ------------------------------------------------------------

def test_cli_mcp_start_refuses_uninitialized(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["mcp", "start"])
    assert result.exit_code == 2


def test_cli_mcp_preview_shows_implemented_tools():
    result = runner.invoke(app, ["mcp", "preview"])
    assert result.exit_code == 0
    assert "Implemented tools:" in result.stdout
    for tool in IMPLEMENTED_TOOLS:
        assert tool in result.stdout
    assert "read-only" in result.stdout


def test_server_class_resolves_across_sdk_generations():
    """The SDK renamed FastMCP to MCPServer in 2.0.

    mcp 2.0.0 removed `mcp.server.fastmcp`, which broke every fresh install of
    devtime-ei[mcp]. Both generations must resolve, and the resolved class must
    expose the surface DevTime relies on.
    """
    from devtime.mcp.transport import _server_class

    cls = _server_class()
    assert cls.__name__ in ("MCPServer", "FastMCP")
    for attr in ("tool", "list_tools", "call_tool", "run"):
        assert hasattr(cls, attr), f"server class is missing {attr}"
