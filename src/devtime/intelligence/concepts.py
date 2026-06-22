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


# Signal kinds that prove behavior, not just presence.
ANCHOR_KINDS = {
    "route",
    "auth_dependency",
    "middleware",
    "webhook_signature_verification",
    "background_job",
    "token_usage",
    "queue",
    "upload_endpoint",
}

# Tokens that justify naming a concept "Billing Webhooks". Reality Hardening
# (v0.0.2): billing evidence must be *file-local* to webhook evidence. Trust Repair
# (v0.0.6): a bare "subscription" is NOT billing (calendar subscriptions, etc.) —
# require a payment provider or an explicit billing/payment term.
BILLING_PROVIDER_TOKENS = (
    "stripe", "paypal", "braintree", "chargebee", "lemonsqueezy", "paddle", "razorpay",
)
BILLING_TERM_TOKENS = (
    "billing", "invoice", "checkout", "payment", "customer.subscription",
)
BILLING_TOKENS = BILLING_PROVIDER_TOKENS + BILLING_TERM_TOKENS
WEBHOOK_TOKENS = ("webhook",)

# Execution dependencies that justify a Background Jobs concept on their own.
JOB_EXECUTION_DEPS = (
    "celery", "bullmq", "sidekiq", "dramatiq", "rq", "kombu", "bull", "agenda",
    "sqs", "kafka", "rabbitmq", "resque",
)
# Upload-related dependencies.
UPLOAD_DEPS = ("multer", "busboy", "formidable", "multipart", "minio")


@dataclass
class ConceptCandidate:
    slug: str
    name: str
    kind: str
    confidence: float
    signals: list[Signal] = field(default_factory=list)
    weak_only: bool = False  # supported only by presence evidence, not behavior


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


def _meaningful_signals(matched: list[Signal]) -> list[Signal]:
    """Signals that can legitimately define a concept (excludes e2e tests + docs)."""
    out = []
    for s in matched:
        if s.kind == "doc":
            continue
        if s.kind == "test" and s.metadata.get("e2e"):
            continue
        out.append(s)
    return out


def _has_concept_anchor(slug: str, matched: list[Signal]) -> bool:
    """Require a concept-appropriate behavior anchor (Trust Repair v0.0.6).

    Word-sense protection: a concept is only emitted when at least one signal
    actually demonstrates that concept's behavior — not a coincidental keyword
    (job *title*, avatar *URL*, *session_id* trace, model *download*, etc.).
    """
    kinds = {s.kind for s in matched}

    def dep_hit(tokens) -> bool:
        return any(
            s.kind == "dependency" and any(t in _signal_haystack(s) for t in tokens)
            for s in matched
        )

    if slug == "background_jobs":
        if {"background_job", "queue"} & kinds:
            return True
        return dep_hit(JOB_EXECUTION_DEPS)

    if slug == "file_uploads":
        if "upload_endpoint" in kinds:
            return True
        if dep_hit(UPLOAD_DEPS):
            return True
        # A route whose own path/handler is about uploading.
        return any(
            s.kind == "route" and "upload" in _signal_haystack(s) for s in matched
        )

    if slug == "data_export":
        # Distinguish user-data export from model/artifact/dependency downloads.
        artifact_terms = ("model", "artifact", "asset", "package", "dependency",
                          "plugin", "binary", "weights", "checkpoint")
        for s in matched:
            if s.kind != "route":
                continue
            hay = _signal_haystack(s)
            if any(t in hay for t in ("export", "csv", "report", "backup")):
                return True
            if "download" in hay and not any(a in hay for a in artifact_terms):
                return True
        return False

    if slug == "admin_permissions":
        return any(
            s.kind in ("middleware", "route")
            and any(t in _signal_haystack(s)
                    for t in ("admin", "superuser", "rbac", "owner", "role", "authorize"))
            for s in matched
        )

    if slug == "authentication":
        if {"auth_dependency", "token_usage"} & kinds:
            return True
        if any(s.kind == "middleware" for s in matched):
            return True
        return any(
            s.kind == "route"
            and any(t in _signal_haystack(s)
                    for t in ("login", "logout", "signin", "sign-in", "/auth", "oauth",
                              "token", "register", "password", "session/"))
            for s in matched
        )

    # billing_webhooks is gated separately by _passes_billing_gate.
    return True


def _passes_billing_gate(slug: str, matched: list[Signal]) -> bool:
    """Billing Webhooks requires webhook evidence and billing evidence that are
    *local to each other* — in the same file (the tightest evidence cluster).

    Reality Hardening (v0.0.2): a repo-wide Stripe dependency, or a generic webhook
    system plus unrelated billing code elsewhere, must NOT infer Billing Webhooks.
    """
    if slug != "billing_webhooks":
        return True

    # A provider signature-verification handler (Stripe constructEvent, etc.) is by
    # itself a local billing-webhook signal.
    if any(s.kind == "webhook_signature_verification" for s in matched):
        return True

    # Otherwise require one file that has BOTH webhook and billing evidence.
    by_file: dict[str, list[Signal]] = {}
    for s in matched:
        by_file.setdefault(s.file_rel_path, []).append(s)

    for file_path, sigs in by_file.items():
        hay = file_path.lower() + " " + " ".join(_signal_haystack(s) for s in sigs)
        has_webhook = any(tok in hay for tok in WEBHOOK_TOKENS)
        has_billing = any(tok in hay for tok in BILLING_TOKENS)
        if has_webhook and has_billing:
            return True
    return False


def detect_concepts(signals: list[Signal]) -> list[ConceptCandidate]:
    candidates: list[ConceptCandidate] = []
    for slug, template in CONCEPT_TEMPLATES.items():
        matched = [s for s in signals if signal_matches_template(s, template)]
        if not matched:
            continue

        # Gate 1: drop concepts defined only by e2e specs or docs.
        meaningful = _meaningful_signals(matched)
        if not meaningful:
            continue

        # Gate 2: "Billing" Webhooks needs billing evidence local to webhook
        # evidence. Only meaningful signals count — an e2e spec under a path like
        # tests-e2e/specs/billing.e2e.spec.ts must not satisfy the billing gate.
        if not _passes_billing_gate(slug, meaningful):
            continue

        # Gate 3: require a concept-appropriate behavior anchor (word-sense).
        # A coincidental keyword (job title, avatar URL, session_id trace) is not
        # enough to emit the concept.
        if not _has_concept_anchor(slug, meaningful):
            continue

        score = score_template_match(template, matched)
        if score < template["min_score"]:
            continue

        # Weak-only: presence evidence (deps/config) but no behavior anchor.
        weak_only = not any(s.kind in ANCHOR_KINDS for s in matched)
        if weak_only:
            score = min(score, 0.45)

        candidates.append(
            ConceptCandidate(
                slug=slug,
                name=template["display_name"],
                kind=template["kind"],
                confidence=score,
                signals=matched,
                weak_only=weak_only,
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
