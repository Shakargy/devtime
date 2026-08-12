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
demo_app = typer.Typer(
    help="Create a local copy of the bundled demo repository.", no_args_is_help=True
)
app.add_typer(claim_app, name="claim")
app.add_typer(decision_app, name="decision")
app.add_typer(mcp_app, name="mcp")
app.add_typer(demo_app, name="demo")


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


@demo_app.command("init")
def demo_init(
    force: bool = typer.Option(
        False, "--force", help="Replace devtime-demo-saas if it already exists."
    ),
) -> None:
    """Copy the bundled demo repository into ./devtime-demo-saas (static files only)."""
    from devtime.demo import DEMO_DIR_NAME, DemoExistsError, create_demo

    try:
        create_demo(Path.cwd(), force=force)
    except DemoExistsError as exc:
        console.print(
            f"[yellow]{DEMO_DIR_NAME}/ already exists[/yellow] at {exc.path}."
        )
        console.print(
            "Use [bold]dtc demo init --force[/bold] to replace it, "
            "or remove the directory first."
        )
        raise typer.Exit(code=1)

    console.print(f"[green]Demo repository created[/green] at ./{DEMO_DIR_NAME}")
    console.print("")
    console.print("Next:")
    console.print(f"  cd {DEMO_DIR_NAME}")
    console.print("  dtc init")
    console.print("  dtc scan")
    console.print("  dtc concepts")
    console.print('  dtc explain "Billing Webhooks"')


@app.command()
def verify(
    claim: str = typer.Argument(None, help="Claim id to verify. Omit to verify all built-in claims."),
    list_claims: bool = typer.Option(False, "--list", help="List built-in claims with last status and freshness."),
    as_json: bool = typer.Option(False, "--json", help="Stable machine-readable output."),
) -> None:
    """Verify a repository claim against scanned evidence (v0.2 experimental)."""
    import json as _json

    from devtime.db import connection
    from devtime.intelligence import verification as ver

    if not paths.is_initialized():
        console.print("[red]Not initialized.[/red] Run dtc init first.")
        raise typer.Exit(code=2)

    conn = connection.connect()
    try:
        if list_claims:
            # Relevance is computed live so the list answers the useful question:
            # which of these claims apply to THIS repository?
            current = {r.claim_slug: r for r in ver.verify_all(conn)}
            rows = []
            for slug, definition in ver.BUILTIN_CLAIMS.items():
                latest = ver.load_latest_verification(conn, slug)
                freshness, changed = ver.freshness_for(conn, slug)
                live = current.get(slug)
                rows.append(
                    {
                        "claim_id": slug,
                        "name": definition.name,
                        "statement": definition.statement,
                        "applies_here": bool(
                            live and live.status in ver.APPLICABLE_STATUSES
                        ),
                        "current_status": live.status if live else None,
                        "last_status": latest[0]["status"] if latest else None,
                        "freshness": freshness,
                        "changed_evidence": changed,
                    }
                )
            rows.sort(key=lambda r: (not r["applies_here"], r["claim_id"]))
            if as_json:
                console.print_json(_json.dumps({"schema_version": "2", "claims": rows}))
            else:
                console.print("[bold]Built-in claims[/bold]\n")
                for r in rows:
                    if not r["applies_here"]:
                        console.print(f"  [dim]{r['claim_id']} (not applicable here)[/dim]")
                        continue
                    status_txt = r["last_status"] or "never verified"
                    console.print(f"  {r['claim_id']}")
                    console.print(f"    {r['statement']}")
                    console.print(
                        f"    current: {r['current_status']}   "
                        f"last verified: {status_txt}   freshness: {r['freshness']}"
                    )
                    for p in r["changed_evidence"]:
                        console.print(f"      changed since verification: {p}", markup=False)
                    console.print("")
            return

        if claim:
            try:
                results = [ver.verify_claim(conn, claim)]
            except KeyError:
                console.print(f"[red]Unknown claim:[/red] {claim}")
                console.print("Run [bold]dtc verify --list[/bold] to see built-in claims.")
                raise typer.Exit(code=1)
        else:
            results = ver.verify_all(conn)

        # Only real verifications are recorded. A claim that does not apply to
        # this repository was not verified, so storing it would pollute
        # freshness and diff impact with claims that have no evidence.
        for result in results:
            if result.status in ver.APPLICABLE_STATUSES:
                ver.save_verification(conn, result)

        if as_json:
            console.print_json(
                _json.dumps(
                    {
                        "schema_version": "2",
                        "command": "verify",
                        "results": [r.to_dict() for r in results],
                    }
                )
            )
            return

        _print_report(results, single=bool(claim))
    finally:
        conn.close()


def _print_report(results: list, single: bool) -> None:
    """Report card: what DevTime can and cannot verify about this repository."""
    from devtime.intelligence import verification as ver

    applicable = [r for r in results if r.status in ver.APPLICABLE_STATUSES]
    not_applicable = [r for r in results if r.status == ver.NOT_APPLICABLE]

    for result in applicable:
        _print_verification(result)

    if not_applicable and not single:
        console.print("[dim]Not applicable to this repository:[/dim]")
        for r in not_applicable:
            reason = r.why[0] if r.why else "No relevant surface was found."
            console.print(f"  - {r.claim_slug}: {reason}", markup=False)
        console.print("")

    if single and not applicable:
        # An explicitly requested claim that does not apply still explains itself.
        for result in not_applicable:
            _print_verification(result)
        return

    if not applicable:
        _print_nothing_verifiable()


def _print_nothing_verifiable() -> None:
    """Never a dead end: say what was scanned and what would unlock a claim."""
    from devtime.db import connection

    conn = connection.connect()
    try:
        scan = conn.execute(
            "SELECT id, file_count, signal_count FROM scans WHERE status = 'completed' "
            "ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        kinds = []
        if scan:
            kinds = conn.execute(
                "SELECT kind, COUNT(*) c FROM signals WHERE scan_id = ? "
                "GROUP BY kind ORDER BY c DESC LIMIT 6",
                (scan["id"],),
            ).fetchall()
    finally:
        conn.close()

    console.print("[bold]No built-in claim applies to this repository yet.[/bold]")
    console.print("")
    if scan:
        console.print(
            f"DevTime scanned {scan['file_count']} files and found "
            f"{scan['signal_count']} signals.",
            markup=False,
        )
        if kinds:
            summary = ", ".join(f"{k['kind']}={k['c']}" for k in kinds)
            console.print(f"Evidence collected: {summary}", markup=False)
        else:
            console.print(
                "No evidence was extracted, which usually means this repository's "
                "language or framework is outside current scanner coverage.",
                markup=False,
            )
    console.print("")
    console.print("Built-in claims become verifiable when a repository has:")
    console.print("  - HTTP routes and tests (route-test-coverage)")
    console.print("  - admin, staff, or back-office routes (admin-authorization)")
    console.print("  - JWT usage or a JWT dependency (jwt-authentication)")
    console.print("  - billing webhooks or a payment provider (billing-webhook-signature)")
    console.print("")
    console.print(
        "This is a coverage limit, not a verdict on your repository. "
        "Scanner support is strongest on TypeScript, Next.js, Express, and "
        "FastAPI-style code; see LIMITATIONS.md.",
        markup=False,
    )
    console.print(
        "If DevTime missed something your repository clearly has, that is worth "
        "an issue: https://github.com/Shakargy/devtime/issues",
        markup=False,
    )


def _print_verification(result) -> None:
    color = {
        "SUPPORTED": "green",
        "WEAK": "yellow",
        "CONTRADICTED": "red",
        "UNKNOWN": "cyan",
        "NOT_APPLICABLE": "dim",
    }.get(result.status, "white")
    console.print(f"[bold]{result.claim_name}[/bold]")
    console.print(f"Claim: {result.statement}")
    console.print(f"Status: [{color}]{result.status}[/{color}]")
    console.print("")
    console.print("Why:")
    for line in result.why:
        console.print(f"  - {line}", markup=False)
    if result.supporting:
        console.print("\nSupporting evidence:")
        for e in result.supporting[:6]:
            loc = f":{e.start_line}" if e.start_line else ""
            console.print(f"  - {e.path}{loc}  [{e.strength}]", markup=False)
            console.print(f"      {e.observation}", markup=False)
    if result.contradictions:
        console.print("\n[red]Contradictions:[/red]")
        for c in result.contradictions:
            console.print(f"  - {c.summary}", markup=False)
            console.print(f"      claimed:  {c.claimed_side}", markup=False)
            console.print(f"      observed: {c.observed_side}", markup=False)
    if result.missing:
        console.print("\nMissing evidence:")
        for m in result.missing:
            console.print(f"  - {m}", markup=False)
    console.print("\nLimitations:")
    for lim in result.limitations:
        console.print(f"  - {lim}", markup=False)
    console.print("")


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
        result = run_scan(refresh=refresh, progress=True)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Scan failed:[/red] {exc}")
        raise typer.Exit(code=3)
    console.print(
        f"[green]Scan complete.[/green] Scanned {result.file_count} files, "
        f"{result.signal_count} signals, {result.concept_count} concepts "
        f"in {result.duration_seconds}s."
    )
    console.print(
        f"Pruned directories: {result.pruned_dirs}   "
        f"Skipped/ignored files: {result.skipped_files}"
    )
    console.print("Supported V0 concept families: 6 (closed ontology).")
    for w in result.framework_warnings:
        console.print(f"[yellow]{w}[/yellow]")
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
    from devtime.intelligence.risk import (
        STATE_REVIEW_FAILED,
        parse_unified_diff,
        review_diff,
        review_failed,
    )
    from devtime.output.markdown import render_risk_review

    if not paths.is_initialized():
        console.print("[red]Not initialized.[/red] Run dtc init.")
        raise typer.Exit(code=2)

    # Git failure must surface as review_failed, never as "no findings".
    try:
        # --relative emits paths relative to the current directory, so diff paths
        # match scan-root-relative evidence even when the scan root is a subdirectory
        # of the git repository (e.g. running the demo from examples/demo-saas).
        proc = subprocess.run(
            ["git", "diff", "--relative", base],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        console.print(render_risk_review(review_failed("git executable not found")), markup=False)
        raise typer.Exit(code=1)

    if proc.returncode != 0:
        reason = (proc.stderr or "git diff returned a non-zero exit code").strip()
        console.print(render_risk_review(review_failed(reason)), markup=False)
        raise typer.Exit(code=1)

    info = parse_unified_diff(proc.stdout)
    conn = connection.connect()
    try:
        intelligence = repository.load_all_concepts(conn)
        from devtime.intelligence.verification import claims_affected_by_paths

        claim_impact = claims_affected_by_paths(conn, info.changed_files)
    finally:
        conn.close()

    review = review_diff(info, intelligence)
    console.print(render_risk_review(review), markup=False)

    # v0.4.0: claim impact. A diff is not just risky in general - it can
    # destabilize a previously verified claim. Only evidence files count;
    # nothing is printed when no verified claim is affected.
    if claim_impact:
        console.print("\nClaim impact:", markup=False)
        for item in claim_impact:
            console.print(
                f"  - {item['claim_id']} (previous status: {item['previous_status']})",
                markup=False,
            )
            for p in item["changed_evidence"]:
                console.print(f"      changed evidence: {p}", markup=False)
            console.print(f"      re-verify: {item['suggested_action']}", markup=False)

    if review.state == STATE_REVIEW_FAILED:
        raise typer.Exit(code=1)


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
    """Start the local read-only MCP server over stdio (for coding agents)."""
    # stdout belongs to the JSON-RPC stream: all diagnostics go to stderr.
    err = Console(stderr=True)

    if not paths.is_initialized():
        err.print("[red]DevTime is not initialized here.[/red]")
        err.print("Run [bold]dtc init[/bold] and [bold]dtc scan[/bold] in the repository first.")
        raise typer.Exit(code=2)

    from devtime.mcp.transport import McpDependencyMissing, run_stdio

    err.print("DevTime MCP server: stdio, read-only, local only. Ctrl+C to stop.")
    try:
        run_stdio()
    except McpDependencyMissing as exc:
        # markup=False: the hint contains [mcp], which rich would eat as a tag.
        err.print(str(exc), markup=False, style="red")
        raise typer.Exit(code=1)


@mcp_app.command("preview")
def mcp_preview() -> None:
    """Show implemented and planned read-only MCP tools."""
    from devtime.mcp.server import describe_server

    # markup=False: the text contains [mcp], which rich would eat as a tag.
    console.print(describe_server(), markup=False)


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
