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


def _concept_presence_claim(concept: ConceptCandidate, evidence: list[EvidenceItem]) -> Claim:
    """Strength-aware presence claim. Trust Repair (v0.0.6): never say
    'is present' for low-confidence / dependency-only concepts, and never
    contradict the uncertainty section.
    """
    name = concept.name
    weak_only = getattr(concept, "weak_only", False)
    conf = concept.confidence
    has_behavior = any(
        e.signal.kind in ("route", "auth_dependency", "middleware",
                          "webhook_signature_verification", "background_job",
                          "token_usage", "queue")
        for e in evidence
    )

    if not weak_only and conf >= 0.75 and has_behavior:
        text = f"{name} is present and supported by behavior evidence."
        state = "supported"
    elif not weak_only and conf >= 0.5:
        text = f"{name} signals are present, but behavior is only partially established."
        state = "partial"
    else:
        text = (
            f"Possible {name} signals detected. "
            f"{name} behavior is not established from current evidence."
        )
        state = "weak"
    return Claim(type="concept", text=text, confidence=conf, state=state, evidence=evidence[:4])


def _jwt_claim(name: str, jwt_usage: list[EvidenceItem]) -> Claim:
    """Purpose-aware JWT claim. Trust Repair (v0.0.6): only assert access-token
    behavior when the evidence shows it; invitation JWTs are not access tokens.
    """
    purposes = {e.signal.metadata.get("purpose", "unclear") for e in jwt_usage}
    if "access" in purposes:
        return Claim(
            type="usage",
            text=f"{name} uses JWT access tokens.",
            confidence=0.85,
            evidence=jwt_usage,
        )
    if purposes <= {"invitation"}:
        return Claim(
            type="usage",
            text="JWT usage detected for invitations; access-token behavior not established.",
            confidence=0.6,
            state="partial",
            evidence=jwt_usage,
        )
    return Claim(
        type="usage",
        text="JWT usage detected; token purpose not fully classified.",
        confidence=0.55,
        state="partial",
        evidence=jwt_usage,
    )


def generate_claims_and_uncertainty(
    concept: ConceptCandidate, evidence: list[EvidenceItem]
) -> tuple[list[Claim], list[Uncertainty]]:
    claims: list[Claim] = []
    uncertainties: list[Uncertainty] = []

    # concept claim - strength-aware (never "is present" for weak evidence).
    if evidence:
        claims.append(_concept_presence_claim(concept, evidence))

    # behavior claim - active route handling.
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

    # usage claim - JWT, purpose-aware (usage is not decision).
    jwt_usage = _has(evidence, "token_usage")
    if jwt_usage:
        claims.append(_jwt_claim(concept.name, jwt_usage))

    # behavior claim - webhook signature verification.
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

    # dependency-only presence is weak evidence - never a behavior claim.
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
