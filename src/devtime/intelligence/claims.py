"""Claim generation and governance (Builder Edition, Chapter 11).

Claims are structured beliefs, not prose. They are generated from evidence first,
then rendered. This prevents narration from inventing truth.

Core laws enforced here:
  - No claim without evidence.
  - No claim stronger than its evidence.
  - Usage is not decision.
  - Uncertainty is output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from devtime.intelligence.concepts import ConceptCandidate
from devtime.intelligence.evidence import EvidenceItem

CLAIM_TYPES = (
    "concept", "usage", "behavior", "decision", "test", "risk",
    "ownership", "lineage", "uncertainty",
)


@dataclass
class Claim:
    type: str
    text: str
    confidence: float
    state: str = "supported"
    evidence: list[EvidenceItem] = field(default_factory=list)
    requires_human_confirmation: bool = False
    created_by: str = "machine"


@dataclass
class Uncertainty:
    type: str
    text: str
    action: str | None = None
    severity: str = "medium"


@dataclass
class ConceptIntelligence:
    concept: ConceptCandidate
    evidence: list[EvidenceItem]
    claims: list[Claim]
    uncertainties: list[Uncertainty]


def _has(evidence: list[EvidenceItem], kind: str) -> list[EvidenceItem]:
    return [e for e in evidence if e.signal.kind == kind]


def _has_strong_route(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    return [e for e in evidence if e.kind == "route" and e.strength == "strong"]


def generate_claims_and_uncertainty(
    concept: ConceptCandidate, evidence: list[EvidenceItem]
) -> tuple[list[Claim], list[Uncertainty]]:
    claims: list[Claim] = []
    uncertainties: list[Uncertainty] = []

    # concept claim — supported by the matched evidence itself.
    if evidence:
        claims.append(
            Claim(
                type="concept",
                text=f"{concept.name} is present in this repository.",
                confidence=concept.confidence,
                evidence=evidence[:4],
            )
        )

    # behavior claim — active route handling.
    routes = _has_strong_route(evidence)
    if routes:
        claims.append(
            Claim(
                type="behavior",
                text=f"{concept.name} has active route handling.",
                confidence=0.82,
                evidence=routes,
            )
        )

    # usage claim — JWT access tokens (usage is not decision).
    jwt_usage = _has(evidence, "token_usage")
    if jwt_usage:
        claims.append(
            Claim(
                type="usage",
                text=f"{concept.name} uses JWT access tokens.",
                confidence=0.88,
                evidence=jwt_usage,
            )
        )

    # behavior claim — webhook signature verification.
    sig = _has(evidence, "webhook_signature_verification")
    if sig:
        claims.append(
            Claim(
                type="behavior",
                text=f"{concept.name} verifies webhook signatures.",
                confidence=0.85,
                evidence=sig,
            )
        )

    # dependency-only presence is weak evidence — never a behavior claim.
    deps = _has(evidence, "dependency")
    if deps and not routes and not sig:
        claims.append(
            Claim(
                type="usage",
                text=f"{concept.name} has related dependencies present.",
                confidence=0.55,
                state="weak",
                evidence=deps[:3],
            )
        )

    # --- Uncertainty generation (uncertainty is output) ---

    # Presence-only evidence: dependencies/manifests but no parsed behavior.
    if getattr(concept, "weak_only", False):
        uncertainties.append(
            Uncertainty(
                type="presence_only_evidence",
                text=(
                    f"Only dependency or manifest evidence was found for "
                    f"{concept.name}; presence is not confirmed behavior."
                ),
                action=f"Confirm {concept.name} behavior, or treat this as a weak signal.",
                severity="medium",
            )
        )

    # Missing decision evidence.
    has_decision = bool(_has(evidence, "decision"))
    if not has_decision:
        uncertainties.append(
            Uncertainty(
                type="missing_decision",
                text=f"No decision was found explaining key choices for {concept.name}.",
                action=f"Record a decision for {concept.name}, or link an existing ADR.",
                severity="medium",
            )
        )
        claims.append(
            Claim(
                type="uncertainty",
                text=f"No decision was found explaining key choices for {concept.name}.",
                confidence=1.0,
                state="uncertain",
                evidence=[],
            )
        )

    # Behavior present but no behavior-specific test.
    behavior_tests = [
        e for e in _has(evidence, "test") if e.strength == "strong"
    ]
    if (routes or sig) and not behavior_tests:
        uncertainties.append(
            Uncertainty(
                type="weak_test_evidence",
                text=f"No behavior-specific test was found for {concept.name}.",
                action=f"Add or link a behavior test for {concept.name}.",
                severity="medium",
            )
        )

    return claims, uncertainties


def build_concept_intelligence(
    concept: ConceptCandidate, evidence: list[EvidenceItem]
) -> ConceptIntelligence:
    claims, uncertainties = generate_claims_and_uncertainty(concept, evidence)
    return ConceptIntelligence(
        concept=concept,
        evidence=evidence,
        claims=claims,
        uncertainties=uncertainties,
    )
