"""JSON / Markdown export of repository memory (Builder Edition, Chapter 4)."""

from __future__ import annotations

import json
from pathlib import Path

from devtime.db import connection, repository
from devtime.intelligence.scoring import compute_understanding


def export_memory(fmt: str = "json", root: Path | None = None) -> str:
    conn = connection.connect(root)
    try:
        items = repository.load_all_concepts(conn)
        data = []
        for ci in items:
            us = compute_understanding(ci)
            data.append(
                {
                    "concept": ci.concept.name,
                    "slug": ci.concept.slug,
                    "confidence": round(ci.concept.confidence, 2),
                    "understanding_score": us.score,
                    "debt": us.debt_label,
                    "claims": [
                        {"type": c.type, "text": c.text, "confidence": round(c.confidence, 2)}
                        for c in ci.claims
                    ],
                    "uncertainty": [u.text for u in ci.uncertainties],
                    "evidence": [
                        {"kind": e.kind, "strength": e.strength, "path": e.path}
                        for e in ci.evidence
                    ],
                }
            )
    finally:
        conn.close()

    if fmt == "markdown":
        lines = ["# DevTime Repository Memory Export", ""]
        for d in data:
            lines.append(f"## {d['concept']} ({d['understanding_score']}/100, debt: {d['debt']})")
            lines.append("Claims:")
            lines += [f"- [{c['type']}] {c['text']}" for c in d["claims"]]
            lines.append("Uncertainty:")
            lines += [f"- {u}" for u in d["uncertainty"]] or ["- None"]
            lines.append("")
        return "\n".join(lines)
    return json.dumps(data, indent=2)
