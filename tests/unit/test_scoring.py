from devtime.intelligence.claims import build_concept_intelligence
from devtime.intelligence.concepts import ConceptCandidate
from devtime.intelligence.evidence import build_evidence
from devtime.intelligence.scoring import compute_understanding
from devtime.scanner.extractors.base import Signal


def _candidate(signals):
    return ConceptCandidate(
        slug="authentication",
        name="Authentication",
        kind="system_concept",
        confidence=0.8,
        signals=signals,
    )


def test_missing_decision_lowers_score_and_adds_uncertainty():
    signals = [
        Signal(kind="route", name="POST /auth/login", file_rel_path="src/auth/login.ts", confidence=0.8),
        Signal(kind="token_usage", name="jwt", file_rel_path="src/auth/tokens.ts", confidence=0.8),
    ]
    cand = _candidate(signals)
    ci = build_concept_intelligence(cand, build_evidence(cand))
    us = compute_understanding(ci)
    assert "missing decision evidence" in us.causes
    assert any("decision" in u.text.lower() for u in ci.uncertainties)
    assert 0 <= us.score <= 100


def test_score_is_clamped():
    cand = _candidate([])
    ci = build_concept_intelligence(cand, [])
    us = compute_understanding(ci)
    assert 0 <= us.score <= 100
