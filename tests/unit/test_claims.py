from devtime.intelligence.claims import build_concept_intelligence
from devtime.intelligence.concepts import ConceptCandidate
from devtime.intelligence.evidence import build_evidence
from devtime.scanner.extractors.base import Signal


def test_usage_is_not_decision():
    """A dependency/usage signal must never become a decision claim."""
    signals = [
        Signal(kind="token_usage", name="jwt", file_rel_path="src/auth/tokens.ts",
               confidence=0.8, metadata={"purpose": "access"}),
        Signal(kind="route", name="POST /auth/login", file_rel_path="src/auth/login.ts", confidence=0.8),
    ]
    cand = ConceptCandidate(
        slug="authentication", name="Authentication", kind="system_concept",
        confidence=0.8, signals=signals,
    )
    ci = build_concept_intelligence(cand, build_evidence(cand))
    texts = " ".join(c.text for c in ci.claims).lower()
    assert "uses jwt access tokens" in texts
    # No claim should assert *why* JWT was chosen.
    assert "was chosen because" not in texts
    decision_claims = [c for c in ci.claims if c.type == "decision"]
    assert decision_claims == []


def test_no_claim_without_evidence():
    cand = ConceptCandidate(
        slug="authentication", name="Authentication", kind="system_concept",
        confidence=0.0, signals=[],
    )
    ci = build_concept_intelligence(cand, [])
    # Only uncertainty (which needs no evidence) may exist with no evidence.
    for c in ci.claims:
        if c.type != "uncertainty":
            assert c.evidence, f"claim '{c.text}' has no evidence"
