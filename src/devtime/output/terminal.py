"""Terminal output (Builder Edition, Chapter 4).

The CLI is the first proof surface. Output shows what was learned, what evidence
supports it, what is uncertain, and what to do next.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markup import escape

from devtime import config, paths
from devtime.db import connection, repository
from devtime.intelligence import concepts as concepts_mod
from devtime.intelligence.context_pack import generate_context_pack, render_markdown
from devtime.intelligence.scoring import compute_understanding

console = Console()


def _require_init(root: Path | None = None) -> bool:
    if not paths.is_initialized(root):
        console.print("[red]DevTime is not initialized.[/red] Run [bold]dtc init[/bold] first.")
        return False
    return True


def print_concepts(root: Path | None = None) -> None:
    if not _require_init(root):
        return
    conn = connection.connect(root)
    try:
        items = repository.load_all_concepts(conn)
        if not items:
            console.print("No concepts detected yet. Run [bold]dtc scan[/bold].")
            return
        console.print("[bold]Detected concepts[/bold]\n")
        for i, ci in enumerate(items, 1):
            us = compute_understanding(ci)
            ev_kinds = sorted({e.kind for e in ci.evidence})
            console.print(f"{i}. [bold]{ci.concept.name}[/bold]")
            console.print(
                f"   confidence: {concepts_mod.confidence_label(ci.concept.confidence)}"
            )
            console.print(f"   evidence: {', '.join(ev_kinds) or 'none'}")
            console.print(f"   debt: {us.debt_label}\n")
    finally:
        conn.close()


def print_explanation(concept: str, root: Path | None = None) -> None:
    if not _require_init(root):
        return
    conn = connection.connect(root)
    try:
        ci = repository.load_concept(conn, concept)
        if ci is None:
            console.print(f"[yellow]No concept found matching[/yellow] '{concept}'.")
            console.print("Run [bold]dtc concepts[/bold] to see detected concepts.")
            return
        us = compute_understanding(ci)
        console.print(f"[bold]Concept:[/bold] {ci.concept.name}\n")

        console.print("[bold]Supported claims:[/bold]")
        supported = [c for c in ci.claims if c.type != "uncertainty"]
        if not supported:
            console.print("  (none)")
        for c in supported:
            paths_str = ", ".join(dict.fromkeys(e.path for e in c.evidence if e.path)) or "n/a"
            console.print(f"  - {escape(c.text)}")
            console.print(
                f"    [dim]type: {c.type}  confidence: {c.confidence:.2f}  "
                f"evidence: {escape(paths_str)}[/dim]"
            )

        console.print("\n[bold]Uncertainty:[/bold]")
        if not ci.uncertainties:
            console.print("  (none)")
        for u in ci.uncertainties:
            console.print(f"  - {escape(u.text)}")

        # Trust Repair: Understanding Score (higher = better); Debt is a label.
        console.print(
            f"\n[bold]Understanding Score:[/bold] {us.score} / 100"
        )
        console.print(f"[bold]Understanding Debt:[/bold] {us.debt_label}")
        if us.causes:
            console.print("causes:")
            for cause in us.causes:
                console.print(f"  - {cause}")
        if us.how_to_reduce:
            console.print("suggested next steps:")
            for step in us.how_to_reduce:
                console.print(f"  - {step}")
    finally:
        conn.close()


def print_evidence(concept: str, root: Path | None = None) -> None:
    if not _require_init(root):
        return
    conn = connection.connect(root)
    try:
        ci = repository.load_concept(conn, concept)
        if ci is None:
            console.print(f"[yellow]No concept found matching[/yellow] '{concept}'.")
            return
        console.print(f"[bold]Evidence for {ci.concept.name}[/bold]\n")
        for e in ci.evidence:
            loc = f" ({e.path})" if e.path else ""
            console.print(f"- [{e.strength}] {escape(e.summary + loc)}")
    finally:
        conn.close()


def print_debt(root: Path | None = None) -> None:
    if not _require_init(root):
        return
    conn = connection.connect(root)
    try:
        items = repository.load_all_concepts(conn)
        scored = sorted(
            ((ci, compute_understanding(ci)) for ci in items),
            key=lambda pair: pair[1].score,
        )
        console.print("[bold]Understanding Score and Debt[/bold]\n")
        for ci, us in scored:
            console.print(
                f"[bold]{ci.concept.name}[/bold] - score {us.score}/100, debt {us.debt_label}"
            )
            for cause in us.causes:
                console.print(f"  - {cause}")
            console.print("")
    finally:
        conn.close()


def print_context(concept: str, mode: str, root: Path | None = None) -> str | None:
    if not _require_init(root):
        return None
    conn = connection.connect(root)
    try:
        ci = repository.load_concept(conn, concept)
        if ci is None:
            console.print(f"[yellow]No concept found matching[/yellow] '{concept}'.")
            return None
        pack = generate_context_pack(ci, mode=mode)
        md = render_markdown(pack)
        # markup=False so filesystem paths like calendar/[provider]/route.ts render literally.
        console.print(md, markup=False)
        # Persist the generated pack to memory.
        repository_save_context_pack(conn, ci.concept.slug, mode, md)
        return md
    finally:
        conn.close()


def repository_save_context_pack(conn, concept_slug: str, mode: str, body: str) -> None:
    import uuid
    from datetime import datetime, timezone

    conn.execute(
        "INSERT INTO context_packs(id, concept_id, mode, body_markdown, metadata_json, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            f"CP-{uuid.uuid4().hex[:10]}",
            concept_slug,
            mode,
            body,
            "{}",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def print_status(root: Path | None = None) -> None:
    root = root or paths.repo_root()
    initialized = paths.is_initialized(root)
    cfg = config.load_config(root)
    priv = cfg["privacy"]
    mcp = cfg["mcp"]

    last_scan = None
    if initialized:
        conn = connection.connect(root)
        try:
            last_scan = repository.last_scan_time(conn)
        finally:
            conn.close()

    console.print("[bold]Repository:[/bold]")
    console.print(f"  Initialized: {'yes' if initialized else 'no'}")
    console.print(f"  Root: {root.resolve()}")
    console.print("[bold]Storage:[/bold]")
    console.print(f"  Local SQLite: {paths.db_path(root)}")
    console.print("[bold]AI:[/bold]")
    console.print(f"  {'Enabled' if priv['ai_enabled'] else 'Disabled'}")
    console.print("[bold]Cloud:[/bold]")
    console.print(f"  {'Enabled' if priv['cloud_enabled'] else 'Disabled'}")
    console.print("[bold]Telemetry:[/bold]")
    console.print(f"  {'On' if priv['telemetry_enabled'] else 'Off'}")
    console.print("[bold]MCP:[/bold]")
    console.print(f"  {'Enabled' if mcp['enabled'] else 'Stopped'}")
    console.print("[bold]Last scan:[/bold]")
    console.print(f"  {last_scan or 'never'}")
