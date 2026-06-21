"""Evidence system (Builder Edition, Chapter 10).

Evidence is the truth layer. It records what material supports a concept, how
strong it is, and what claim types it can support.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from devtime.intelligence.concepts import ConceptCandidate
from devtime.scanner.extractors.base import Signal

# Signal kind -> evidence kind.
_KIND_MAP = {
    "route": "route",
    "middleware": "middleware",
    "auth_dependency": "auth",
    "token_usage": "usage",
    "webhook_signature_verification": "behavior",
    "background_job": "worker",
    "queue": "queue",
    "dependency": "dependency",
    "config": "config",
    "test": "test",
    "doc": "doc",
    "decision": "decision",
}

# Evidence strength tiers (Chapter 10).
STRONG_KINDS = {"route", "auth_dependency", "webhook_signature_verification", "decision"}
MEDIUM_KINDS = {"middleware", "token_usage", "background_job", "config"}
# "test" strength depends on whether it is behavior-specific; handled below.
WEAK_KINDS = {"dependency", "doc"}


@dataclass
class EvidenceItem:
    concept_slug: str
    kind: str
    strength: str
    summary: str
    path: str | None
    start_line: int | None
    end_line: int | None
    signal: Signal
    supports_claim_types: list[str] = field(default_factory=list)


def map_signal_to_evidence_kind(kind: str) -> str:
    return _KIND_MAP.get(kind, "other")


def estimate_strength(s: Signal) -> str:
    if s.kind == "test":
        # E2E UI specs match keywords by accident -> weak (Reality Validation).
        if s.metadata.get("e2e"):
            return "weak"
        # Behavior-specific test names are strong; bare test presence is medium.
        return "strong" if s.name and len(s.name) > 8 else "medium"
    if s.kind in STRONG_KINDS:
        return "strong"
    if s.kind in MEDIUM_KINDS:
        return "medium"
    return "weak"


def _supports(kind: str) -> list[str]:
    mapping = {
        "route": ["concept", "behavior"],
        "auth": ["concept", "behavior"],
        "behavior": ["behavior"],
        "usage": ["usage"],
        "dependency": ["usage"],
        "test": ["test", "behavior"],
        "decision": ["decision"],
        "config": ["usage"],
        "doc": ["concept"],
        "worker": ["concept", "behavior"],
        "middleware": ["behavior"],
    }
    return mapping.get(kind, ["concept"])


def summarize_signal(s: Signal) -> str:
    if s.kind == "route":
        return f"{s.name} route handles requests in {s.file_rel_path}."
    if s.kind == "test":
        return f"Test '{s.name}' in {s.file_rel_path}."
    if s.kind == "dependency":
        return f"Depends on '{s.name}' ({s.file_rel_path})."
    if s.kind == "webhook_signature_verification":
        return f"Verifies {s.name} webhook signatures in {s.file_rel_path}."
    if s.kind == "auth_dependency":
        return f"Auth dependency '{s.name}' in {s.file_rel_path}."
    if s.kind == "decision":
        return f"Decision record: {s.name} ({s.file_rel_path})."
    if s.kind == "config":
        return f"Config reference '{s.name}' in {s.file_rel_path}."
    return f"{s.kind}: {s.name or ''} ({s.file_rel_path})".strip()


def _rank_key(e: EvidenceItem) -> tuple[int, float]:
    order = {"strong": 3, "medium": 2, "weak": 1, "contradictory": 0}
    return (order.get(e.strength, 0), e.signal.confidence)


def build_evidence(concept: ConceptCandidate) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for s in concept.signals:
        kind = map_signal_to_evidence_kind(s.kind)
        strength = estimate_strength(s)
        items.append(
            EvidenceItem(
                concept_slug=concept.slug,
                kind=kind,
                strength=strength,
                summary=summarize_signal(s),
                path=s.file_rel_path,
                start_line=s.start_line,
                end_line=s.end_line,
                signal=s,
                supports_claim_types=_supports(kind),
            )
        )
    items.sort(key=_rank_key, reverse=True)
    return items
