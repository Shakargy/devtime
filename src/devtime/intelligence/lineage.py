"""Lineage (Builder Edition / Full Book, Book III Ch.9).

Lineage shows how meaning changes over time. V0 is a placeholder: it has no
git-history backed evolution yet, but the seam exists so later versions can track
how concepts evolve across code, decisions, tests, and risk.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LineageEntry:
    concept_slug: str
    note: str


def lineage_for(concept_slug: str) -> list[LineageEntry]:
    # V0: no historical lineage yet.
    return []
