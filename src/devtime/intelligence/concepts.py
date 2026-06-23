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
        "names": ["queue", "worker", "celery", "bullmq", "sidekiq", "bgtask",
                  "bg_task", "bg-task", "bgtasks", "cron job"],
        "signals": ["background_job", "queue", "dependency", "config", "test"],
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
# (v0.0.6): a bare "subscription" is NOT billing (calendar subscriptions, etc.) -
# require a payment provider or an explicit billing/payment term.
BILLING_PROVIDER_TOKENS = (
    "stripe", "paypal", "braintree", "chargebee", "lemonsqueezy", "paddle", "razorpay",
)
# Explicit payment/billing terms (Evidence Precision v0.0.7). "subscription" and
# "customer" alone are NOT here - they appear in calendar/CRM contexts too.
BILLING_TERM_TOKENS = (
    "billing", "invoice", "invoices", "checkout", "payment", "payments",
    "charge", "charges", "customer.subscription",
)
BILLING_TOKENS = BILLING_PROVIDER_TOKENS + BILLING_TERM_TOKENS
WEBHOOK_TOKENS = ("webhook",)

# Negative billing contexts: webhook routes that are clearly NOT payment webhooks.
# A billing concept here requires an explicit payment provider to override.
NEGATIVE_BILLING_CONTEXTS = (
    "calendar", "credential", "connector", "monitor", "scheduler", "cron",
    "webhooktrigger", "webhook-trigger", "webhook_trigger", "github", "fireflies",
    "recall", "resend", "ses", "oauth", "cleanup",
)

# Direct authentication terms. A weak signal (test/config/dep) only counts as
# Authentication evidence if it contains one of these (Evidence Precision v0.0.7).
# Deliberately excludes bare "auth"/"token"/"session"/"signing" and "nextauth_url"
# (the real NextAuth handler is a route, not a URL constant in a permalink test).
STRONG_AUTH_TERMS = (
    "login", "log in", "logout", "log out", "signin", "sign in", "sign-in",
    "register", "oauth", "bearer", "cookie", "password", "access token",
    "access_token", "accesstoken", "jwt", "authenticate", "authentication",
    "auth middleware", "api key", "api_key", "apikey", "session creation",
    "session verification", "csrf",
)

# Employment / person taxonomy that must never become Background Jobs.
EMPLOYMENT_NEG_TOKENS = (
    "job title", "job-title", "jobtitle", "job_title", "job role", "job-role",
    "jobrole", "job_role", "job class", "job-class", "job_class", "job sub-role",
    "sub-role", "employment", "occupation", "position title", "role options",
    "title options", "role-options", "title-options",
)

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
    actually demonstrates that concept's behavior - not a coincidental keyword
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
        if dep_hit(JOB_EXECUTION_DEPS):
            return True
        # A direct background-task test (path or import references bg_tasks/celery/etc).
        for s in matched:
            hay = _signal_haystack(s)
            if _is_employment(hay):
                continue
            if any(t in hay for t in ("bgtask", "bg_task", "bg-task", "bgtasks",
                                      "celery", "sidekiq", "bullmq", "worker",
                                      "queue", "cron job", "scheduler")):
                return True
        return False

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


def _is_employment(hay: str) -> bool:
    return any(t in hay for t in EMPLOYMENT_NEG_TOKENS)


def _passes_billing_gate(slug: str, matched: list[Signal]) -> bool:
    """Billing Webhooks requires webhook evidence and *payment-provider* evidence
    local to each other.

    Evidence Precision (v0.0.7): a webhook in a negative context (calendar,
    credential, connector, monitor, scheduler, cron, generic trigger) is NOT billing
    unless an explicit payment provider (Stripe/PayPal/...) is local. "subscription"
    and "customer" alone do not count.
    """
    if slug != "billing_webhooks":
        return True

    # A provider signature-verification handler (Stripe constructEvent, etc.) is by
    # itself a local payment-provider signal.
    if any(s.kind == "webhook_signature_verification" for s in matched):
        return True

    by_file: dict[str, list[Signal]] = {}
    for s in matched:
        by_file.setdefault(s.file_rel_path, []).append(s)

    for file_path, sigs in by_file.items():
        hay = file_path.lower() + " " + " ".join(_signal_haystack(s) for s in sigs)
        has_webhook = any(tok in hay for tok in WEBHOOK_TOKENS)
        has_provider = any(tok in hay for tok in BILLING_PROVIDER_TOKENS)
        has_payment_term = any(tok in hay for tok in BILLING_TERM_TOKENS)
        is_negative = any(tok in hay for tok in NEGATIVE_BILLING_CONTEXTS)

        if not has_webhook:
            continue
        # An explicit payment provider always qualifies.
        if has_provider:
            return True
        # A payment/billing term qualifies only outside a negative context.
        if has_payment_term and not is_negative:
            return True
    return False


def _is_false_sense(slug: str, s: Signal) -> bool:
    """Drop signals that match a concept only through a misleading keyword
    (Evidence Precision v0.0.7). Real behavior signals are never dropped."""
    hay = _signal_haystack(s)

    if slug == "authentication":
        # Real auth behavior kinds are headline evidence and are never dropped.
        if s.kind in ("auth_dependency", "middleware", "token_usage"):
            return False
        # A route is auth evidence only if it is genuinely an auth route - a `[token]`
        # path segment on an upload/file route is not authentication.
        if s.kind == "route":
            return not _is_auth_route(hay)
        # Weak kinds (test/config/dependency/doc): judge by FILE PATH so a passing
        # mention of "auth" in storage/signing code cannot leak in. An
        # s3SigningDiagnostics.test.ts is storage/signing, not authentication.
        path = s.file_rel_path.lower()
        if any(d in path for d in AUTH_NEGATIVE_DOMAIN):
            return True
        has_auth_path = any(t in path for t in AUTH_POSITIVE_PATH_TERMS)
        has_strong = any(t in hay for t in STRONG_AUTH_TERMS)
        return not (has_auth_path or has_strong)

    if slug == "background_jobs":
        return _is_employment(hay)

    if slug == "billing_webhooks":
        # A payment-provider signature handler is always real billing evidence.
        if s.kind == "webhook_signature_verification":
            return False
        has_provider = any(p in hay for p in BILLING_PROVIDER_TOKENS)
        if has_provider:
            return False
        has_payment = any(t in hay for t in BILLING_TERM_TOKENS)
        is_negative = any(n in hay for n in NEGATIVE_BILLING_CONTEXTS)
        # Calendar/credential/connector/cron/generic-trigger contexts without a local
        # payment provider are NOT billing evidence (Codex blocker 1 / Cal.com).
        if is_negative:
            return True
        if "webhook" in hay and not has_payment:
            return True
        if "subscription" in hay and not has_payment:
            return True
        return False

    return False


# For weak Authentication signals, the file path decides. Storage/signing/upload/
# diagnostics files are not authentication, even if their content mentions "auth".
AUTH_NEGATIVE_DOMAIN = (
    "s3", "signing", "signed", "storage", "bucket", "minio", "cdn", "upload",
    "diagnostic", "billing", "calendar", "webhook", "export", "avatar", "image",
    "media", "trace", "permalink", "monitor", "analytics", "telemetry",
)
AUTH_POSITIVE_PATH_TERMS = (
    "auth", "login", "logout", "signin", "signup", "oauth", "nextauth", "session",
    "password", "mfa", "2fa", "/sso", "saml", "credential",
)

_AUTH_ROUTE_POSITIVE = (
    "/auth", "login", "logout", "signin", "sign-in", "signup", "sign-up", "oauth",
    "register", "password", "nextauth", "/session", "forgot", "reset-password",
    "2fa", "mfa", "/sso", "saml", "verify-email", "magic-link",
)
_AUTH_ROUTE_NEGATIVE_DOMAIN = (
    "upload", "album", "file", "avatar", "export", "download", "calendar",
    "billing", "webhook", "invoice", "image", "media", "asset",
)


def _is_auth_route(hay: str) -> bool:
    if any(t in hay for t in _AUTH_ROUTE_POSITIVE):
        return True
    # A bare token/jwt path segment counts only outside a clearly non-auth domain
    # (e.g. /app-upload/[token] is an upload route, not authentication).
    if "token" in hay or "jwt" in hay:
        return not any(d in hay for d in _AUTH_ROUTE_NEGATIVE_DOMAIN)
    return False


def _sense_filter(slug: str, signals: list[Signal]) -> list[Signal]:
    return [s for s in signals if not _is_false_sense(slug, s)]


def detect_concepts(signals: list[Signal]) -> list[ConceptCandidate]:
    candidates: list[ConceptCandidate] = []
    for slug, template in CONCEPT_TEMPLATES.items():
        matched = [s for s in signals if signal_matches_template(s, template)]
        if not matched:
            continue

        # Gate 1: drop concepts defined only by e2e specs or docs.
        meaningful = _meaningful_signals(matched)
        # Gate 1b: drop word-sense pollution (session_id traces, NEXTAUTH_URL,
        # employment job-title taxonomy, etc.) so it never becomes evidence.
        meaningful = _sense_filter(slug, meaningful)
        if not meaningful:
            continue

        # Gate 2: "Billing" Webhooks needs billing evidence local to webhook
        # evidence. Only meaningful signals count - an e2e spec under a path like
        # tests-e2e/specs/billing.e2e.spec.ts must not satisfy the billing gate.
        if not _passes_billing_gate(slug, meaningful):
            continue

        # Gate 3: require a concept-appropriate behavior anchor (word-sense).
        # A coincidental keyword (job title, avatar URL, session_id trace) is not
        # enough to emit the concept.
        if not _has_concept_anchor(slug, meaningful):
            continue

        # Score and evidence use the cleaned (sense-filtered) signals only, so
        # word-sense pollution never inflates confidence or drives headline evidence.
        score = score_template_match(template, meaningful)
        if score < template["min_score"]:
            continue

        # Weak-only: presence evidence (deps/config) but no behavior anchor.
        weak_only = not any(s.kind in ANCHOR_KINDS for s in meaningful)
        if weak_only:
            score = min(score, 0.45)

        candidates.append(
            ConceptCandidate(
                slug=slug,
                name=template["display_name"],
                kind=template["kind"],
                confidence=score,
                signals=meaningful,
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
