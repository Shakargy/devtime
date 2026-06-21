"""DevTime CLI (Builder Edition, Chapter 4 + Appendix A).

The CLI is the first product surface. It must make trust visible.

Exit codes (Appendix A):
  0 success | 1 general error | 2 not initialized | 3 scan failed
  4 migration failed | 5 privacy boundary violation | 6 fixture assertion failed
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from devtime import __version__, paths

app = typer.Typer(
    help="DevTime - local-first Engineering Intelligence", no_args_is_help=True
)
console = Console()

claim_app = typer.Typer(help="Inspect and govern claims.")
decision_app = typer.Typer(help="Record human decisions.")
mcp_app = typer.Typer(help="Local read-only MCP server.")
app.add_typer(claim_app, name="claim")
app.add_typer(decision_app, name="decision")
app.add_typer(mcp_app, name="mcp")


# --------------------------------------------------------------------------- #
# Initialization
# --------------------------------------------------------------------------- #

@app.command()
def init() -> None:
    """Create .devtime, config, and SQLite database."""
    from devtime.db.migrations import init_repo

    init_repo()
    console.print("[green]DevTime initialized.[/green] Local memory at .devtime/devtime.sqlite")
    console.print("AI disabled. Cloud disabled. Telemetry off. MCP read-only.")


@app.command()
def status() -> None:
    """Show local storage, AI, cloud, telemetry, MCP, and scan status."""
    from devtime.output.terminal import print_status

    print_status()


@app.command()
def doctor(
    privacy: bool = typer.Option(False, "--privacy", help="Show privacy and boundary checks."),
) -> None:
    """Run environment and repository checks."""
    from devtime.privacy import privacy_report

    report = privacy_report()
    console.print("[bold]Privacy check[/bold]\n")
    console.print("[green]Good:[/green]")
    for item in report["good"]:
        console.print(f"  - {item}")
    if report["warning"]:
        console.print("[yellow]Warning:[/yellow]")
        for item in report["warning"]:
            console.print(f"  - {item}")
    if report["recommended"]:
        console.print("[bold]Recommended:[/bold]")
        for item in report["recommended"]:
            console.print(f"  {item}")


# --------------------------------------------------------------------------- #
# Scanning
# --------------------------------------------------------------------------- #

@app.command()
def scan(
    refresh: bool = typer.Option(False, "--refresh", help="Recompute concepts, claims, scores."),
    show_ignored: bool = typer.Option(False, "--show-ignored", help="(reserved)"),
) -> None:
    """Scan repository and update local memory."""
    from devtime.scanner.signals import run_scan

    try:
        result = run_scan(refresh=refresh)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Scan failed:[/red] {exc}")
        raise typer.Exit(code=3)
    console.print(
        f"[green]Scan complete.[/green] {result.file_count} files, "
        f"{result.signal_count} signals, {result.concept_count} concepts "
        f"in {result.duration_seconds}s."
    )
    console.print("Nothing left this machine. Run [bold]dtc concepts[/bold] to inspect.")


# --------------------------------------------------------------------------- #
# Understanding
# --------------------------------------------------------------------------- #

@app.command()
def concepts() -> None:
    """List detected concepts."""
    from devtime.output.terminal import print_concepts

    print_concepts()


@app.command()
def explain(concept: str) -> None:
    """Explain a concept from evidence."""
    from devtime.output.terminal import print_explanation

    print_explanation(concept)


@app.command()
def evidence(concept: str) -> None:
    """Show evidence for a concept."""
    from devtime.output.terminal import print_evidence

    print_evidence(concept)


@app.command()
def debt() -> None:
    """Show top Understanding Debt by concept."""
    from devtime.output.terminal import print_debt

    print_debt()


@app.command()
def understand() -> None:
    """Show Understanding Debt across concepts (alias of debt)."""
    from devtime.output.terminal import print_debt

    print_debt()


# --------------------------------------------------------------------------- #
# Risk
# --------------------------------------------------------------------------- #

@app.command()
def risk(
    diff: bool = typer.Option(False, "--diff", help="Review current diff against memory."),
    base: str = typer.Option("HEAD", "--base", help="Base ref for the diff."),
    fmt: str = typer.Option("text", "--format", help="text or markdown."),
) -> None:
    """Review local changes against repository memory."""
    import subprocess

    from devtime.db import connection, repository
    from devtime.intelligence.risk import parse_unified_diff, review_diff
    from devtime.output.markdown import render_risk_findings

    if not paths.is_initialized():
        console.print("[red]Not initialized.[/red] Run dtc init.")
        raise typer.Exit(code=2)

    try:
        # --relative emits paths relative to the current directory, so diff paths
        # match scan-root-relative evidence even when the scan root is a subdirectory
        # of the git repository (e.g. running the demo from examples/demo-saas).
        diff_text = subprocess.run(
            ["git", "diff", "--relative", base],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except FileNotFoundError:
        console.print("[red]git not found.[/red] Risk review needs a git diff.")
        raise typer.Exit(code=1)

    info = parse_unified_diff(diff_text)
    conn = connection.connect()
    try:
        intelligence = repository.load_all_concepts(conn)
    finally:
        conn.close()

    findings = review_diff(info, intelligence)
    console.print(render_risk_findings(findings))


# --------------------------------------------------------------------------- #
# AI workflow
# --------------------------------------------------------------------------- #

@app.command()
def context(
    concept: str,
    mode: str = typer.Option("risk", "--mode", help="overview|risk|implementation|testing|onboarding|security"),
    copy: bool = typer.Option(False, "--copy", help="(reserved) copy to clipboard"),
) -> None:
    """Generate a Context Pack for humans or AI agents."""
    from devtime.output.terminal import print_context

    print_context(concept, mode)


# --------------------------------------------------------------------------- #
# Memory: claims and decisions
# --------------------------------------------------------------------------- #

@claim_app.command("show")
def claim_show(claim_id: str) -> None:
    """Inspect a claim, evidence, confidence, and uncertainty."""
    from devtime.db import connection

    conn = connection.connect()
    try:
        row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        if not row:
            console.print(f"[yellow]No claim[/yellow] {claim_id}")
            return
        console.print(dict(row))
    finally:
        conn.close()


@claim_app.command("challenge")
def claim_challenge(claim_id: str) -> None:
    """Mark a claim as challenged."""
    from devtime.db import connection

    conn = connection.connect()
    try:
        cur = conn.execute(
            "UPDATE claims SET state = 'challenged' WHERE id = ?", (claim_id,)
        )
        conn.commit()
        if cur.rowcount:
            console.print(f"[green]Claim {claim_id} challenged.[/green]")
        else:
            console.print(f"[yellow]No claim[/yellow] {claim_id}")
    finally:
        conn.close()


@claim_app.command("confirm")
def claim_confirm(claim_id: str) -> None:
    """Confirm a claim (human confirmation)."""
    from devtime.db import connection

    conn = connection.connect()
    try:
        cur = conn.execute(
            "UPDATE claims SET state = 'confirmed', created_by = 'human' WHERE id = ?",
            (claim_id,),
        )
        conn.commit()
        if cur.rowcount:
            console.print(f"[green]Claim {claim_id} confirmed.[/green]")
        else:
            console.print(f"[yellow]No claim[/yellow] {claim_id}")
    finally:
        conn.close()


@decision_app.command("add")
def decision_add(
    title: str = typer.Option(..., "--title", help="Decision title."),
    body: str = typer.Option(..., "--body", help="Why this behavior exists or changed."),
    concept: str = typer.Option(None, "--concept", help="Concept slug to attach to."),
) -> None:
    """Record why a behavior exists or changed."""
    from devtime.db import connection, repository

    conn = connection.connect()
    try:
        did = repository.add_decision(conn, title, body, concept)
        console.print(f"[green]Decision recorded[/green] ({did}).")
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# MCP
# --------------------------------------------------------------------------- #

@mcp_app.command("start")
def mcp_start() -> None:
    """Start local read-only MCP server."""
    from devtime.mcp.server import describe_server

    console.print(describe_server())


@mcp_app.command("status")
def mcp_status() -> None:
    """Inspect MCP permissions and clients."""
    from devtime.mcp.server import describe_permissions

    console.print(describe_permissions())


# --------------------------------------------------------------------------- #
# Export and reset
# --------------------------------------------------------------------------- #

@app.command()
def export(fmt: str = typer.Option("json", "--format", help="json or markdown.")) -> None:
    """Export reviewable memory."""
    from devtime.output.json_export import export_memory

    if not paths.is_initialized():
        console.print("[red]Not initialized.[/red]")
        raise typer.Exit(code=2)
    console.print(export_memory(fmt))


@app.command()
def reset(
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    """Delete local memory after confirmation."""
    import shutil

    if not paths.is_initialized():
        console.print("Nothing to reset.")
        return
    if not yes:
        confirm = typer.confirm("Delete all local DevTime memory? Source code is untouched.")
        if not confirm:
            console.print("Aborted.")
            return
    shutil.rmtree(paths.devtime_dir())
    console.print("[green]Local memory deleted.[/green] Source code untouched.")


@app.command()
def version() -> None:
    """Show DevTime version."""
    console.print(f"DevTime CLI: {__version__}")


if __name__ == "__main__":
    app()
