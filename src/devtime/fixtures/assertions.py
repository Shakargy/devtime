"""Fixture assertions (Builder Edition, Chapter 17).

Allowed claims must appear, forbidden claims must not, required uncertainty must
be present, and expected concepts must be detected.
"""

from __future__ import annotations

from devtime.intelligence.claims import ConceptIntelligence

# Loose substring matching so fixtures stay readable while detection wording evolves.


def _all_claim_texts(intelligence: list[ConceptIntelligence]) -> list[str]:
    texts: list[str] = []
    for ci in intelligence:
        texts += [c.text for c in ci.claims]
    return texts


def _all_uncertainty_texts(intelligence: list[ConceptIntelligence]) -> list[str]:
    texts: list[str] = []
    for ci in intelligence:
        texts += [u.text for u in ci.uncertainties]
        texts += [c.text for c in ci.claims if c.type == "uncertainty"]
    return texts


def _matches(needle: str, haystack: list[str]) -> bool:
    key = needle.lower().strip()
    return any(key in h.lower() for h in haystack)


def assert_expected_concepts(intelligence, expected: list[str]) -> list[str]:
    names = {ci.concept.name.lower() for ci in intelligence}
    return [c for c in expected if c.lower() not in names]


def assert_allowed_claims(intelligence, allowed: list[str]) -> list[str]:
    texts = _all_claim_texts(intelligence)
    return [c for c in allowed if not _matches(c, texts)]


def assert_forbidden_claims_absent(intelligence, forbidden: list[str]) -> list[str]:
    texts = _all_claim_texts(intelligence)
    return [c for c in forbidden if _matches(c, texts)]


def assert_required_uncertainty(intelligence, required: list[str]) -> list[str]:
    texts = _all_uncertainty_texts(intelligence)
    return [u for u in required if not _matches(u, texts)]
