"""Claim transitions between two snapshots (v0.7.0).

A change is not interesting because it touched files. It is interesting when it
moves what the repository can support: a claim that was supported and no
longer is, a claim that newly applies, or a claim whose evidence changed even
though its conclusion held.

This module is pure: it takes two lists of verification results and the set of
changed paths, and returns transitions. It does no git, filesystem, or database
work, so its behavior is fully determined by its inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from devtime.intelligence import verification as ver

# Transition kinds, in reporting order (most important first).
REGRESSION = "regression"
NEWLY_APPLICABLE = "newly_applicable"
NO_LONGER_APPLICABLE = "no_longer_applicable"
IMPROVEMENT = "improvement"
EVIDENCE_CHANGED = "evidence_changed"
UNCHANGED = "unchanged"

_ORDER = {
    REGRESSION: 0,
    NEWLY_APPLICABLE: 1,
    NO_LONGER_APPLICABLE: 2,
    IMPROVEMENT: 3,
    EVIDENCE_CHANGED: 4,
    UNCHANGED: 5,
}

# How strongly a status supports its claim. Used only to tell a regression from
# an improvement; NOT_APPLICABLE is handled separately because it is not a
# weaker form of support, it is the absence of a surface.
_RANK = {
    ver.CONTRADICTED: 0,
    ver.UNKNOWN: 1,
    ver.WEAK: 1,
    ver.SUPPORTED: 2,
}

_NOTES = {
    REGRESSION: "The change reduced what the repository can support for this claim.",
    NEWLY_APPLICABLE: "The change introduced a surface this claim now applies to.",
    NO_LONGER_APPLICABLE: (
        "The surface this claim applied to is no longer detected. It may have "
        "been removed, renamed, or moved outside scanner coverage."
    ),
    IMPROVEMENT: "The change added evidence for this claim.",
    EVIDENCE_CHANGED: (
        "Files this claim depends on changed. The status held, but the evidence "
        "behind it is different and may be worth a look."
    ),
    UNCHANGED: "",
}


@dataclass
class Transition:
    claim_id: str
    claim_name: str
    kind: str
    base_status: str
    head_status: str
    base_summary: str
    head_summary: str
    changed_evidence: list[str] = field(default_factory=list)
    head_missing: list[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "claim_name": self.claim_name,
            "kind": self.kind,
            "base_status": self.base_status,
            "head_status": self.head_status,
            "base_summary": self.base_summary,
            "head_summary": self.head_summary,
            "changed_evidence": self.changed_evidence,
            "head_missing_evidence": self.head_missing,
            "note": self.note,
        }


def _summary(result) -> str:
    return result.why[0] if result.why else ""


def _classify(base_status: str, head_status: str) -> str | None:
    """Kind for a status change, or None when the status did not change."""
    if base_status == head_status:
        return None
    if base_status == ver.NOT_APPLICABLE:
        return NEWLY_APPLICABLE
    if head_status == ver.NOT_APPLICABLE:
        return NO_LONGER_APPLICABLE
    if head_status == ver.CONTRADICTED:
        return REGRESSION
    if _RANK.get(head_status, 1) < _RANK.get(base_status, 1):
        return REGRESSION
    if _RANK.get(head_status, 1) > _RANK.get(base_status, 1):
        return IMPROVEMENT
    # WEAK <-> UNKNOWN: same strength, different reason. Report it as a change
    # of evidence rather than inventing a direction.
    return EVIDENCE_CHANGED


def compute_transitions(
    base_results: list, head_results: list, changed_paths: set[str]
) -> list[Transition]:
    """Every claim's transition from base to head, most important first.

    `changed_paths` must contain both the new and the old path of a rename, so a
    claim that depended on a renamed file is recognized as affected.
    """
    base_by_id = {r.claim_slug: r for r in base_results}
    head_by_id = {r.claim_slug: r for r in head_results}
    transitions: list[Transition] = []

    for claim_id in sorted(set(base_by_id) | set(head_by_id)):
        base = base_by_id.get(claim_id)
        head = head_by_id.get(claim_id)
        base_status = base.status if base else ver.NOT_APPLICABLE
        head_status = head.status if head else ver.NOT_APPLICABLE

        deps: set[str] = set()
        for r in (base, head):
            if r is None:
                continue
            deps |= set(r.dependencies)
            deps |= {e.path for e in r.supporting}
        touched = sorted(deps & changed_paths)

        kind = _classify(base_status, head_status)
        base_summary = _summary(base) if base else ""
        head_summary = _summary(head) if head else ""
        if kind is None:
            both_not_applicable = base_status == ver.NOT_APPLICABLE
            if not both_not_applicable and (touched or base_summary != head_summary):
                kind = EVIDENCE_CHANGED
            else:
                kind = UNCHANGED

        ref = head or base
        transitions.append(
            Transition(
                claim_id=claim_id,
                claim_name=ref.claim_name if ref else claim_id,
                kind=kind,
                base_status=base_status,
                head_status=head_status,
                base_summary=base_summary,
                head_summary=head_summary,
                changed_evidence=touched[:20],
                head_missing=list(head.missing) if head else [],
                note=_NOTES[kind],
            )
        )

    transitions.sort(key=lambda t: (_ORDER[t.kind], t.claim_id))
    return transitions


def summarize(transitions: list[Transition]) -> dict:
    counts = {kind: 0 for kind in _ORDER}
    for t in transitions:
        counts[t.kind] += 1
    return counts


def reportable(transitions: list[Transition]) -> list[Transition]:
    """Transitions worth showing. Unchanged, unaffected claims are only counted,
    so a review does not repeat low-value observations on every run."""
    return [t for t in transitions if t.kind != UNCHANGED]
