"""Persistence and read-back for repository memory (Builder Edition, Chapter 6).

Writes concepts, evidence, claims, uncertainties, and decisions during a scan,
and reconstructs ConceptIntelligence objects for explain/context/risk/scoring so
those commands read from durable memory rather than re-deriving truth on the fly.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from devtime.intelligence.claims import (
    Claim,
    ConceptIntelligence,
    Uncertainty,
)
from devtime.intelligence.concepts import ConceptCandidate
from devtime.intelligence.evidence import EvidenceItem
from devtime.scanner.extractors.base import Signal


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# --------------------------------------------------------------------------- #
# Write
# --------------------------------------------------------------------------- #

def add_repository_if_missing(conn: sqlite3.Connection, root) -> str:
    """Return the existing repository id, creating a row if none exists."""
    row = conn.execute("SELECT id FROM repositories LIMIT 1").fetchone()
    if row:
        return row["id"]
    repo_id = _id("repo")
    root_path = str(root.resolve()) if hasattr(root, "resolve") else str(root)
    conn.execute(
        "INSERT INTO repositories(id, root_path, created_at, updated_at) VALUES (?,?,?,?)",
        (repo_id, root_path, _now(), _now()),
    )
    conn.commit()
    return repo_id


def clear_derived_memory(conn: sqlite3.Connection) -> None:
    """Remove machine-derived memory before a re-scan. Human decisions are kept."""
    for table in ("evidence", "claims", "uncertainties", "concepts", "risk_findings"):
        conn.execute(f"DELETE FROM {table}")


def save_intelligence(
    conn: sqlite3.Connection,
    repository_id: str,
    items: list[ConceptIntelligence],
) -> None:
    for ci in items:
        concept_id = ci.concept.slug
        conn.execute(
            "INSERT OR REPLACE INTO concepts"
            "(id, repository_id, name, slug, kind, summary, confidence, status, "
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                concept_id,
                repository_id,
                ci.concept.name,
                ci.concept.slug,
                ci.concept.kind,
                f"{ci.concept.name} detected from repository evidence.",
                ci.concept.confidence,
                "supported",
                _now(),
                _now(),
            ),
        )

        # Evidence (stash original signal kind/confidence for faithful read-back).
        ev_id_map: dict[int, str] = {}
        for idx, e in enumerate(ci.evidence):
            eid = _id("E")
            ev_id_map[idx] = eid
            conn.execute(
                "INSERT INTO evidence"
                "(id, concept_id, file_id, signal_id, kind, strength, summary, path, "
                " start_line, end_line, metadata_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    eid,
                    concept_id,
                    None,
                    None,
                    e.kind,
                    e.strength,
                    e.summary,
                    e.path,
                    e.start_line,
                    e.end_line,
                    json.dumps(
                        {
                            "signal_kind": e.signal.kind,
                            "signal_confidence": e.signal.confidence,
                            "signal_name": e.signal.name,
                            "supports": e.supports_claim_types,
                        }
                    ),
                    _now(),
                ),
            )

        for c in ci.claims:
            conn.execute(
                "INSERT INTO claims"
                "(id, concept_id, type, text, confidence, state, evidence_ids_json, "
                " uncertainty_ids_json, requires_human_confirmation, created_by, "
                " created_at, updated_at, last_verified_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    _id("C"),
                    concept_id,
                    c.type,
                    c.text,
                    c.confidence,
                    c.state,
                    json.dumps([e.path for e in c.evidence if e.path]),
                    "[]",
                    1 if c.requires_human_confirmation else 0,
                    c.created_by,
                    _now(),
                    _now(),
                    None,
                ),
            )

        for u in ci.uncertainties:
            conn.execute(
                "INSERT INTO uncertainties"
                "(id, concept_id, type, text, action, severity, evidence_gap_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (_id("U"), concept_id, u.type, u.text, u.action, u.severity, "{}", _now()),
            )
    conn.commit()


def add_decision(
    conn: sqlite3.Connection,
    title: str,
    body: str,
    concept_slug: str | None = None,
) -> str:
    did = _id("D")
    conn.execute(
        "INSERT INTO decisions"
        "(id, concept_id, title, body, source, status, evidence_ids_json, "
        " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (did, concept_slug, title, body, "human", "active", "[]", _now(), _now()),
    )
    conn.commit()
    return did


# --------------------------------------------------------------------------- #
# Read / reconstruct
# --------------------------------------------------------------------------- #

def _row_to_evidence(row: sqlite3.Row) -> EvidenceItem:
    meta = json.loads(row["metadata_json"] or "{}")
    signal = Signal(
        kind=meta.get("signal_kind", row["kind"]),
        name=meta.get("signal_name"),
        file_rel_path=row["path"] or "",
        confidence=meta.get("signal_confidence", 0.5),
    )
    return EvidenceItem(
        concept_slug=row["concept_id"],
        kind=row["kind"],
        strength=row["strength"],
        summary=row["summary"],
        path=row["path"],
        start_line=row["start_line"],
        end_line=row["end_line"],
        signal=signal,
        supports_claim_types=meta.get("supports", []),
    )


def load_concept(conn: sqlite3.Connection, slug_or_name: str) -> ConceptIntelligence | None:
    row = conn.execute(
        "SELECT * FROM concepts WHERE slug = ? OR lower(name) = lower(?)",
        (slug_or_name, slug_or_name),
    ).fetchone()
    if row is None:
        return None
    return _load_for_concept_row(conn, row)


def _load_for_concept_row(conn: sqlite3.Connection, row: sqlite3.Row) -> ConceptIntelligence:
    concept_id = row["id"]
    evidence = [
        _row_to_evidence(r)
        for r in conn.execute(
            "SELECT * FROM evidence WHERE concept_id = ?", (concept_id,)
        ).fetchall()
    ]
    candidate = ConceptCandidate(
        slug=row["slug"],
        name=row["name"],
        kind=row["kind"],
        confidence=row["confidence"],
        signals=[e.signal for e in evidence],
    )
    # Attach human decisions as decision-kind evidence so scoring/uncertainty see them.
    for d in conn.execute(
        "SELECT * FROM decisions WHERE concept_id = ? AND status = 'active'",
        (concept_id,),
    ).fetchall():
        evidence.append(
            EvidenceItem(
                concept_slug=row["slug"],
                kind="decision",
                strength="strong",
                summary=f"Decision: {d['title']}",
                path=None,
                start_line=None,
                end_line=None,
                signal=Signal(kind="decision", name=d["title"], file_rel_path="(decision)"),
                supports_claim_types=["decision"],
            )
        )

    claims = [
        Claim(
            type=r["type"],
            text=r["text"],
            confidence=r["confidence"],
            state=r["state"],
            evidence=[e for e in evidence if e.path in set(json.loads(r["evidence_ids_json"] or "[]"))],
            requires_human_confirmation=bool(r["requires_human_confirmation"]),
            created_by=r["created_by"],
        )
        for r in conn.execute(
            "SELECT * FROM claims WHERE concept_id = ?", (concept_id,)
        ).fetchall()
    ]
    has_decision = any(e.kind == "decision" for e in evidence)
    uncertainties = [
        Uncertainty(
            type=r["type"], text=r["text"], action=r["action"], severity=r["severity"]
        )
        for r in conn.execute(
            "SELECT * FROM uncertainties WHERE concept_id = ?", (concept_id,)
        ).fetchall()
        # A recorded decision resolves the matching "missing decision" uncertainty.
        if not (has_decision and r["type"] == "missing_decision")
    ]
    # Keep uncertainty-typed claims consistent with resolved decisions too.
    if has_decision:
        claims = [
            c for c in claims
            if not (c.type == "uncertainty" and "decision" in c.text.lower())
        ]
    return ConceptIntelligence(
        concept=candidate, evidence=evidence, claims=claims, uncertainties=uncertainties
    )


def load_all_concepts(conn: sqlite3.Connection) -> list[ConceptIntelligence]:
    rows = conn.execute(
        "SELECT * FROM concepts ORDER BY confidence DESC"
    ).fetchall()
    return [_load_for_concept_row(conn, r) for r in rows]


def last_scan_time(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT finished_at FROM scans WHERE status='completed' "
        "ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()
    return row["finished_at"] if row and row["finished_at"] else None
