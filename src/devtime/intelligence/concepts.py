"""Concept detection (Builder Edition, Chapter 9).

Concepts are stable units of software meaning. V0 detection is pragmatic and
pattern-based: match strong signals against known templates, merge overlaps, and
refuse generic concept names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from devtime.scanner.extractors.base import Signal

# Known concept templates (Chapter 9). names = keyword hints, signals = signal
# kinds that strengthen the match.
CONCEPT_TEMPLATES: dict[str, dict] = {
    "authentication": {
        "display_name": "Authentication",
        "kind": "system_concept",
        "names": ["auth", "authentication", "login", "session", "jwt", "token"],
        "signals": ["auth_dependency", "middleware", "route", "test", "config", "token_usage"],
        "min_score": 0.4,
    },
    "billing_webhooks": {
        "display_name": "Billing Webhooks",
        "kind": "system_concept",
        "names": ["stripe", "webhook", "billing", "subscription", "invoice"],
        "signals": ["route", "webhook_signature_verification", "dependency", "test"],
        "min_score": 0.4,
    },
    "background_jobs": {
        "display_name": "Background Jobs",
        "kind": "system_concept",
        "names": ["queue", "worker", "job", "celery", "bullmq", "redis"],
        "signals": ["background_job", "queue", "dependency", "config"],
        "min_score": 0.4,
    },
    "data_export": {
        "display_name": "Data Export",
        "kind": "system_concept",
        "names": ["export", "download", "csv", "report"],
        "signals": ["route", "handler", "test", "schema"],
        "min_score": 0.4,
    },
    "admin_permissions": {
        "display_name": "Admin Permissions",
        "kind": "system_concept",
        "names": ["admin", "permission", "role", "rbac", "authorize"],
        "signals": ["middleware", "route", "test", "config"],
        "min_score": 0.4,
    },
    "file_uploads": {
        "display_name": "File Uploads",
        "kind": "system_concept",
        "names": ["upload", "multipart", "s3", "attachment", "file"],
        "signals": ["route", "handler", "dependency", "test"],
        "min_score": 0.4,
    },
}

# Forbidden generic concept names (Chapter 9).
FORBIDDEN_NAMES = {
    "utils", "helpers", "api", "database", "files", "code", "services", "components",
}


@dataclass
class ConceptCandidate:
    slug: str
    name: str
    kind: str
    confidence: float
    signals: list[Signal] = field(default_factory=list)


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _signal_haystack(s: Signal) -> str:
    return " ".join(
        str(x).lower()
        for x in (s.name, s.value, s.file_rel_path, *s.metadata.values())
        if x is not None
    )


def signal_matches_template(s: Signal, template: dict) -> bool:
    if s.kind in template["signals"]:
        hay = _signal_haystack(s)
        # A typed signal of the right kind whose text mentions a template keyword
        # is a match; pure kind matches (e.g. generic "route") need a name hit too.
        if any(keyword in hay for keyword in template["names"]):
            return True
        # Strong, concept-specific signal kinds count on their own.
        if s.kind in {
            "auth_dependency",
            "webhook_signature_verification",
            "background_job",
            "token_usage",
        }:
            return True
    # Keyword-only match through paths/names for weak kinds.
    if s.kind in {"dependency", "config", "doc", "decision"}:
        hay = _signal_haystack(s)
        if any(keyword in hay for keyword in template["names"]):
            return True
    return False


def score_template_match(template: dict, matched: list[Signal]) -> float:
    if not matched:
        return 0.0
    # Confidence grows with the number of distinct signal kinds and their strength,
    # not raw count (detection is correlation, not magic).
    kinds = {s.kind for s in matched}
    diversity = min(len(kinds), 4) / 4.0
    avg_conf = sum(s.confidence for s in matched) / len(matched)
    score = 0.5 * diversity + 0.5 * avg_conf
    return round(min(score, 0.99), 2)


def _merge_overlapping(candidates: list[ConceptCandidate]) -> list[ConceptCandidate]:
    by_slug: dict[str, ConceptCandidate] = {}
    for cand in candidates:
        existing = by_slug.get(cand.slug)
        if existing is None or cand.confidence > existing.confidence:
            by_slug[cand.slug] = cand
    return list(by_slug.values())


def _remove_generic(candidates: list[ConceptCandidate]) -> list[ConceptCandidate]:
    return [c for c in candidates if c.name.lower() not in FORBIDDEN_NAMES]


def detect_concepts(signals: list[Signal]) -> list[ConceptCandidate]:
    candidates: list[ConceptCandidate] = []
    for slug, template in CONCEPT_TEMPLATES.items():
        matched = [s for s in signals if signal_matches_template(s, template)]
        score = score_template_match(template, matched)
        if score >= template["min_score"] and matched:
            candidates.append(
                ConceptCandidate(
                    slug=slug,
                    name=template["display_name"],
                    kind=template["kind"],
                    confidence=score,
                    signals=matched,
                )
            )
    candidates = _merge_overlapping(candidates)
    candidates = _remove_generic(candidates)
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates


def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"
