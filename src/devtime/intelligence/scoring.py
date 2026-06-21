"""Understanding Score and Understanding Debt (Builder Edition, Chapter 12).

Scores must explain themselves or they are theater. The V0 formula is a weighted
sum of explainable dimensions, and every score carries its causes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from devtime.intelligence.claims import ConceptIntelligence
from devtime.intelligence.evidence import EvidenceItem


@dataclass
class UnderstandingScore:
    score: int
    debt_label: str
    causes: list[str] = field(default_factory=list)
    how_to_reduce: list[str] = field(default_factory=list)
    dimensions: dict[str, float] = field(default_factory=dict)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _evidence_quality(evidence: list[EvidenceItem]) -> float:
    if not evidence:
        return 0.0
    weights = {"strong": 1.0, "medium": 0.6, "weak": 0.3, "contradictory": 0.0}
    return sum(weights.get(e.strength, 0.0) for e in evidence) / len(evidence)


def compute_understanding(ci: ConceptIntelligence) -> UnderstandingScore:
    evidence = ci.evidence
    kinds = {e.signal.kind for e in evidence}

    concept_confidence = ci.concept.confidence
    evidence_quality = _evidence_quality(evidence)
    decision_coverage = 1.0 if any(e.kind == "decision" for e in evidence) else 0.0
    test_coverage_signal = (
        1.0 if any(e.signal.kind == "test" and e.strength == "strong" for e in evidence)
        else (0.4 if "test" in kinds else 0.0)
    )
    ownership_clarity = 0.0  # V0 has no confirmed owners yet.
    freshness = 0.6  # V0 has no git-time data yet; assume moderately fresh.
    contradiction_penalty = (
        1.0 if any(e.strength == "contradictory" for e in evidence) else 0.0
    )

    score = 0.0
    score += concept_confidence * 25
    score += evidence_quality * 20
    score += decision_coverage * 15
    score += test_coverage_signal * 15
    score += ownership_clarity * 10
    score += freshness * 10
    score -= contradiction_penalty * 15
    score = int(round(_clamp(score, 0, 100)))

    causes: list[str] = []
    how: list[str] = []
    if decision_coverage == 0.0:
        causes.append("missing decision evidence")
        how.append("Record a decision explaining why key choices were made.")
    if test_coverage_signal < 1.0:
        causes.append("weak or missing behavior-specific tests")
        how.append("Add or link a behavior-specific test.")
    if ownership_clarity == 0.0:
        causes.append("no confirmed owner")
        how.append("Confirm a suggested reviewer or owner.")
    if contradiction_penalty > 0.0:
        causes.append("contradictory docs and code")
        how.append("Resolve the conflict between documentation and implementation.")

    debt_label = "low" if score >= 75 else "medium" if score >= 50 else "high"

    return UnderstandingScore(
        score=score,
        debt_label=debt_label,
        causes=causes,
        how_to_reduce=how,
        dimensions={
            "concept_confidence": round(concept_confidence, 2),
            "evidence_quality": round(evidence_quality, 2),
            "decision_coverage": decision_coverage,
            "test_coverage_signal": test_coverage_signal,
            "ownership_clarity": ownership_clarity,
            "freshness": freshness,
            "contradiction_penalty": contradiction_penalty,
        },
    )
