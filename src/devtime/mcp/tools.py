"""MCP tool implementations (Builder Edition, Chapter 16).

Read-only by default. Evidence ids and uncertainty are always included; full
source is never returned.
"""

from __future__ import annotations

from devtime.db import connection, repository
from devtime.intelligence import concepts as concepts_mod
from devtime.intelligence.context_pack import generate_context_pack
from devtime.intelligence.scoring import compute_understanding


def list_concepts(limit: int = 50) -> list[dict]:
    conn = connection.connect()
    try:
        out = []
        for ci in repository.load_all_concepts(conn)[:limit]:
            out.append(
                {
                    "concept": ci.concept.name,
                    "slug": ci.concept.slug,
                    "confidence": concepts_mod.confidence_label(ci.concept.confidence),
                }
            )
        return out
    finally:
        conn.close()


def explain_concept(concept: str) -> dict:
    conn = connection.connect()
    try:
        ci = repository.load_concept(conn, concept)
        if ci is None:
            return {"error": "concept_not_found", "suggested_tool": "list_concepts"}
        us = compute_understanding(ci)
        return {
            "concept": ci.concept.name,
            "confidence": {
                "concept": concepts_mod.confidence_label(ci.concept.confidence),
                "decision": "low" if not any(e.kind == "decision" for e in ci.evidence) else "high",
            },
            "claims": [
                {
                    "type": c.type,
                    "text": c.text,
                    "state": c.state,
                    "confidence": round(c.confidence, 2),
                    "evidence": [e.path for e in c.evidence if e.path],
                }
                for c in ci.claims
                if c.type != "uncertainty"
            ],
            "uncertainty": [u.text for u in ci.uncertainties],
            "understanding_score": us.score,
            "human_review_required": bool(ci.uncertainties),
        }
    finally:
        conn.close()


def get_context_pack(concept: str, mode: str = "risk") -> dict:
    conn = connection.connect()
    try:
        ci = repository.load_concept(conn, concept)
        if ci is None:
            return {"error": "concept_not_found", "suggested_tool": "list_concepts"}
        pack = generate_context_pack(ci, mode=mode)
        return {
            "concept": pack.concept,
            "mode": pack.mode,
            "supported_claims": pack.supported_claims,
            "decisions": pack.decisions,
            "uncertainty": pack.uncertainty,
            "do_not_change_without_review": pack.do_not_change,
            "tests_to_run": pack.tests_to_run,
            "agent_guidance": pack.agent_guidance,
            "privacy": {
                "contains_source_excerpts": False,
                "contains_file_paths": True,
                "review_before_sharing": True,
            },
        }
    finally:
        conn.close()
