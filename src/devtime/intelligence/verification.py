"""Claim verification engine (v0.2.0 - the verification slice).

DevTime's evolution target: the verification layer for repository understanding.
A claim is a statement about the repository; verification evaluates it against
persisted scan evidence and answers with a status, both-sided contradictions,
missing evidence, coverage limitations, and freshness - never with confidence
the evidence cannot back.

Scope, deliberately narrow:
  - Built-in claims only (no user-defined claim files yet).
  - Deterministic and rule-driven. No AI, no network, no code execution.
  - Freshness from file fingerprints: FRESH, STALE, NEEDS_VERIFICATION.

Statuses (documented meaning, per repository evidence policy - not formal proof):
  SUPPORTED       required behavior evidence exists in the current scan.
  WEAK            the claim's surface exists, but the proving evidence is missing.
  CONTRADICTED    credible evidence conflicts with the claim; both sides are shown.
  UNKNOWN         the surface exists but coverage cannot responsibly decide.
  NOT_APPLICABLE  the repository has no surface this claim is about (v0.5.0).

NOT_APPLICABLE matters as much as the others. A repository with no billing code
is not "unknown" for a billing claim - the claim simply does not apply, and
saying so plainly is more honest than an ominous UNKNOWN. UNKNOWN is reserved
for the harder case: the surface exists, but the evidence cannot decide.

Freshness is separate from truth:
  FRESH               supporting evidence files are unchanged since verification.
  STALE               at least one evidence file changed or disappeared.
  NEEDS_VERIFICATION  the claim has never been verified in this repository.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from devtime import __version__

# Statuses
SUPPORTED = "SUPPORTED"
WEAK = "WEAK"
CONTRADICTED = "CONTRADICTED"
UNKNOWN = "UNKNOWN"
NOT_APPLICABLE = "NOT_APPLICABLE"

# Statuses that mean "this claim has something to say about this repository".
APPLICABLE_STATUSES = (SUPPORTED, WEAK, CONTRADICTED, UNKNOWN)

# Freshness
FRESH = "FRESH"
STALE = "STALE"
NEEDS_VERIFICATION = "NEEDS_VERIFICATION"

# Billing vocabulary (kept aligned with concepts.py; duplicated deliberately so
# the verification engine has no import-time coupling to concept detection).
_PROVIDER_TOKENS = (
    "stripe", "paypal", "braintree", "chargebee", "lemonsqueezy", "paddle", "razorpay",
)
_PAYMENT_TOKENS = _PROVIDER_TOKENS + (
    "billing", "invoice", "payment", "payments", "checkout", "charge",
)


@dataclass
class EvidenceRef:
    """One piece of evidence with provenance."""

    path: str
    observation: str
    kind: str
    strength: str  # strong | moderate | weak
    start_line: int | None = None
    end_line: int | None = None
    sha256: str | None = None

    def to_dict(self) -> dict:
        d = {
            "path": self.path,
            "observation": self.observation,
            "kind": self.kind,
            "strength": self.strength,
        }
        if self.start_line is not None:
            d["start_line"] = self.start_line
        if self.end_line is not None:
            d["end_line"] = self.end_line
        return d


@dataclass
class Contradiction:
    """A conflict, always with both sides."""

    summary: str
    claimed_side: str
    observed_side: str
    evidence: list[EvidenceRef] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "claimed_side": self.claimed_side,
            "observed_side": self.observed_side,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class VerificationResult:
    claim_slug: str
    claim_name: str
    statement: str
    status: str
    why: list[str]
    supporting: list[EvidenceRef]
    contradictions: list[Contradiction]
    missing: list[str]
    limitations: list[str]
    scan_id: str | None
    verified_at: str
    engine_version: str

    def to_dict(self) -> dict:
        # schema_version 2 (v0.5.0): adds the NOT_APPLICABLE status value. All
        # version 1 fields are unchanged, so consumers that ignore unknown
        # status values keep working.
        return {
            "schema_version": "2",
            "claim_id": self.claim_slug,
            "claim_name": self.claim_name,
            "statement": self.statement,
            "status": self.status,
            "why": self.why,
            "supporting_evidence": [e.to_dict() for e in self.supporting],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "missing_evidence": self.missing,
            "limitations": self.limitations,
            "scan_id": self.scan_id,
            "verified_at": self.verified_at,
            "engine_version": self.engine_version,
        }


@dataclass(frozen=True)
class ClaimDefinition:
    slug: str
    name: str
    statement: str
    category: str


BUILTIN_CLAIMS: dict[str, ClaimDefinition] = {
    "billing-webhook-signature": ClaimDefinition(
        slug="billing-webhook-signature",
        name="Billing Webhook Signature Verification",
        statement="Incoming billing webhooks verify the payment provider's signature.",
        category="billing",
    ),
    "jwt-authentication": ClaimDefinition(
        slug="jwt-authentication",
        name="JWT Authentication",
        statement="Authentication uses JWT access tokens.",
        category="authentication",
    ),
    "route-test-coverage": ClaimDefinition(
        slug="route-test-coverage",
        name="Route Test Coverage",
        statement="HTTP routes are exercised by tests.",
        category="testing",
    ),
    "admin-authorization": ClaimDefinition(
        slug="admin-authorization",
        name="Admin Authorization",
        statement="Administrative routes require an authorization check.",
        category="security",
    ),
}

# JWT library names for dependency evidence.
_JWT_DEP_TOKENS = ("jsonwebtoken", "pyjwt", "jose", "njwt", "jwt-decode", "fast-jwt")

_LIMITATIONS = [
    "Heuristic scanner: evidence comes from static patterns, not execution.",
    "Signature verification is recognized for known provider patterns "
    "(e.g. Stripe constructEvent); custom schemes may not be detected.",
    "Coverage follows scanner language support; see LIMITATIONS.md.",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Signal loading (persisted scan evidence)
# --------------------------------------------------------------------------- #

def _latest_scan_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT id FROM scans WHERE status = 'completed' "
        "ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def _load_signals(conn: sqlite3.Connection, scan_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT s.kind, s.name, s.value, s.start_line, s.end_line, s.confidence, "
        "       s.metadata_json, f.path, f.sha256 "
        "FROM signals s JOIN files f ON f.id = s.file_id "
        "WHERE s.scan_id = ?",
        (scan_id,),
    ).fetchall()


def _hay(row: sqlite3.Row) -> str:
    return " ".join(
        str(x).lower()
        for x in (row["name"], row["value"], row["path"], row["metadata_json"])
        if x is not None
    )


def _is_billingish(hay: str) -> bool:
    return any(t in hay for t in _PAYMENT_TOKENS)


# --------------------------------------------------------------------------- #
# The engine
# --------------------------------------------------------------------------- #

def _no_scan_result(definition: ClaimDefinition) -> VerificationResult:
    return VerificationResult(
        claim_slug=definition.slug,
        claim_name=definition.name,
        statement=definition.statement,
        status=UNKNOWN,
        why=["No completed scan exists. Run dtc scan first."],
        supporting=[],
        contradictions=[],
        missing=["A completed repository scan."],
        limitations=_LIMITATIONS,
        scan_id=None,
        verified_at=_now(),
        engine_version=__version__,
    )


def verify_claim(conn: sqlite3.Connection, slug: str) -> VerificationResult:
    """Verify one built-in claim against the latest completed scan."""
    definition = BUILTIN_CLAIMS.get(slug)
    if definition is None:
        raise KeyError(slug)

    scan_id = _latest_scan_id(conn)
    if scan_id is None:
        return _no_scan_result(definition)

    rows = _load_signals(conn, scan_id)
    return _EVALUATORS[slug](definition, rows, scan_id)


def verify_all(conn: sqlite3.Connection) -> list[VerificationResult]:
    """Verify every built-in claim, loading scan evidence exactly once.

    Applicable results (something to say about this repository) sort first, so
    the first thing a user reads is what DevTime actually found.
    """
    scan_id = _latest_scan_id(conn)
    if scan_id is None:
        return [_no_scan_result(d) for d in BUILTIN_CLAIMS.values()]

    rows = _load_signals(conn, scan_id)
    results = [
        _EVALUATORS[slug](definition, rows, scan_id)
        for slug, definition in BUILTIN_CLAIMS.items()
    ]
    # Contradictions first: they are the findings a user most needs to see.
    order = {CONTRADICTED: 0, SUPPORTED: 1, WEAK: 2, UNKNOWN: 3, NOT_APPLICABLE: 4}
    results.sort(key=lambda r: (order.get(r.status, 9), r.claim_slug))
    return results


def _verify_billing_webhook_signature(
    definition: ClaimDefinition, rows: list[sqlite3.Row], scan_id: str
) -> VerificationResult:
    verifications: list[EvidenceRef] = []
    webhook_routes: list[EvidenceRef] = []
    stub_webhooks: list[EvidenceRef] = []
    signature_tests: list[EvidenceRef] = []
    provider_deps: list[EvidenceRef] = []

    for row in rows:
        hay = _hay(row)
        kind = row["kind"]

        if kind == "webhook_signature_verification":
            verifications.append(
                _ref(row, "Verifies the provider's webhook signature.", "strong")
            )
        elif kind == "route" and "webhook" in hay and _is_billingish(hay):
            webhook_routes.append(
                _ref(row, "Billing webhook route is handled here.", "moderate")
            )
        elif kind == "disabled_endpoint" and "webhook" in hay and _is_billingish(hay):
            stub_webhooks.append(
                _ref(
                    row,
                    "Webhook endpoint is a disabled stub: its only behavior is a "
                    "404/501 response.",
                    "strong",
                )
            )
        elif kind == "test" and "signature" in hay and _is_billingish(hay):
            signature_tests.append(
                _ref(row, "Test exercises webhook signature behavior.", "moderate")
            )
        elif kind == "dependency" and any(p in hay for p in _PROVIDER_TOKENS):
            provider_deps.append(
                _ref(row, "Payment provider dependency is declared.", "weak")
            )

    why: list[str] = []
    missing: list[str] = []
    contradictions: list[Contradiction] = []
    supporting: list[EvidenceRef] = []

    if stub_webhooks and not verifications:
        for stub in stub_webhooks:
            contradictions.append(
                Contradiction(
                    summary="The billing webhook endpoint cannot verify signatures "
                    "because it is a disabled stub.",
                    claimed_side=f"{stub.path} is named and routed as a billing "
                    "webhook endpoint, which implies webhook handling.",
                    observed_side="The handler's only behavior is a 404/501 "
                    "response; no webhook processing or signature verification "
                    "path exists in this repository snapshot.",
                    evidence=[stub],
                )
            )
        why.append(
            "A billing webhook endpoint exists in name, but it is a disabled stub."
        )
        why.append("No signature verification evidence was found anywhere in the scan.")
        status = CONTRADICTED
        supporting = signature_tests  # tests may still exist for other editions
        missing.append("An active webhook handler that verifies provider signatures.")
    elif verifications:
        status = SUPPORTED
        supporting = verifications + webhook_routes + signature_tests
        why.append("Signature verification behavior evidence was found.")
        if webhook_routes:
            why.append("Billing webhook route handling was found.")
        if signature_tests:
            why.append("A test exercises signature behavior.")
        else:
            missing.append("A test that exercises webhook signature verification.")
        # A stub existing next to real verification is worth surfacing, not failing.
        for stub in stub_webhooks:
            contradictions.append(
                Contradiction(
                    summary="One webhook endpoint is a disabled stub while "
                    "verification exists elsewhere.",
                    claimed_side=f"{stub.path} is routed as a billing webhook.",
                    observed_side="Its only behavior is a 404/501 response.",
                    evidence=[stub],
                )
            )
    elif webhook_routes or provider_deps:
        status = WEAK
        supporting = webhook_routes + provider_deps + signature_tests
        why.append(
            "Billing webhook surface exists (routes or provider dependencies), "
            "but no signature verification evidence was found."
        )
        missing.append("Signature verification behavior (e.g. constructEvent).")
        if not signature_tests:
            missing.append("A test that exercises webhook signature verification.")
    else:
        return _not_applicable(
            definition,
            scan_id,
            "No billing webhook surface was found in the scanned files.",
            "A billing webhook route, handler, or payment provider dependency.",
        )

    return VerificationResult(
        claim_slug=definition.slug,
        claim_name=definition.name,
        statement=definition.statement,
        status=status,
        why=why,
        supporting=supporting,
        contradictions=contradictions,
        missing=missing,
        limitations=_LIMITATIONS,
        scan_id=scan_id,
        verified_at=_now(),
        engine_version=__version__,
    )


def _verify_jwt_authentication(
    definition: ClaimDefinition, rows: list[sqlite3.Row], scan_id: str
) -> VerificationResult:
    """Verify JWT access-token authentication, with the documentation-vs-
    implementation contradiction detector.

    The purpose classifier (Trust Repair v0.0.6) distinguishes access tokens
    from invitation/verification tokens. Documentation claiming JWT while the
    only JWT usage found is invitation-purpose is a real, both-sided conflict.
    Documentation with NO usage found at all is missing evidence (WEAK), not a
    contradiction: absence is not positive conflicting evidence.
    """
    access_usage: list[EvidenceRef] = []
    invitation_usage: list[EvidenceRef] = []
    unclear_usage: list[EvidenceRef] = []
    jwt_docs: list[EvidenceRef] = []
    jwt_deps: list[EvidenceRef] = []

    for row in rows:
        hay = _hay(row)
        kind = row["kind"]

        if kind == "token_usage":
            try:
                purpose = json.loads(row["metadata_json"] or "{}").get("purpose", "unclear")
            except json.JSONDecodeError:
                purpose = "unclear"
            if purpose == "access":
                access_usage.append(
                    _ref(row, "JWT used as an access token (login/bearer context).", "strong")
                )
            elif purpose == "invitation":
                invitation_usage.append(
                    _ref(
                        row,
                        "JWT used for invitation/verification tokens, not access.",
                        "moderate",
                    )
                )
            else:
                unclear_usage.append(
                    _ref(row, "JWT usage found; its purpose is unclear.", "weak")
                )
        elif kind in ("doc", "decision") and "jwt" in hay:
            jwt_docs.append(
                _ref(
                    row,
                    "Documentation or decision record references JWT.",
                    "moderate" if kind == "decision" else "weak",
                )
            )
        elif kind == "dependency" and any(t in hay for t in _JWT_DEP_TOKENS):
            jwt_deps.append(
                _ref(row, "JWT library dependency is declared.", "weak")
            )

    why: list[str] = []
    missing: list[str] = []
    contradictions: list[Contradiction] = []
    supporting: list[EvidenceRef] = []

    if access_usage:
        status = SUPPORTED
        supporting = access_usage + jwt_docs + jwt_deps
        why.append("JWT access-token usage evidence was found.")
        if jwt_docs:
            why.append("Documentation or a decision record corroborates JWT usage.")
        else:
            missing.append("A decision record explaining the JWT choice.")
    elif jwt_docs and invitation_usage:
        status = CONTRADICTED
        supporting = invitation_usage
        doc = jwt_docs[0]
        inv = invitation_usage[0]
        contradictions.append(
            Contradiction(
                summary="Documentation claims JWT authentication, but the only JWT "
                "usage found is invitation/verification tokens.",
                claimed_side=f"{doc.path} references JWT in a documentation or "
                "decision context, implying JWT-based authentication.",
                observed_side=f"{inv.path} uses JWT for invitation/verification "
                "tokens. Invitation tokens are not access-token authentication, "
                "and no access-token usage was found.",
                evidence=[doc, inv],
            )
        )
        why.append(
            "Documentation references JWT, but no access-token usage exists; "
            "the only JWT usage found is invitation-purpose."
        )
        missing.append("JWT access-token usage (login/bearer/authorization context).")
    elif jwt_docs or jwt_deps or invitation_usage or unclear_usage:
        status = WEAK
        supporting = jwt_docs + jwt_deps + invitation_usage + unclear_usage
        why.append(
            "JWT surface exists (documentation, dependencies, or unclear usage), "
            "but access-token authentication is not established."
        )
        missing.append("JWT access-token usage (login/bearer/authorization context).")
    else:
        return _not_applicable(
            definition,
            scan_id,
            "No JWT evidence was found in the scanned files.",
            "JWT usage, a JWT library dependency, or documentation referencing JWT.",
        )

    return VerificationResult(
        claim_slug=definition.slug,
        claim_name=definition.name,
        statement=definition.statement,
        status=status,
        why=why,
        supporting=supporting,
        contradictions=contradictions,
        missing=missing,
        limitations=_LIMITATIONS,
        scan_id=scan_id,
        verified_at=_now(),
        engine_version=__version__,
    )


# --------------------------------------------------------------------------- #
# Route test coverage (v0.5.0)
# --------------------------------------------------------------------------- #

# Route path segments that carry no identity and must not be used for matching.
_GENERIC_SEGMENTS = {"api", "v1", "v2", "v3", "app", "index", "route", "routes", "src"}


def _module_token(path: str) -> str:
    """The distinctive file stem of an implementation file, lowercased."""
    stem = path.rsplit("/", 1)[-1]
    for suffix in (".ts", ".tsx", ".js", ".jsx", ".py", ".mjs", ".cjs"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem.lower()


def _route_tokens(route_path: str) -> list[str]:
    """Distinctive, non-generic segments of a route path."""
    out = []
    for seg in route_path.lower().replace("\\", "/").split("/"):
        seg = seg.strip()
        if not seg or seg.startswith(("[", ":", "{", "<")) or seg in _GENERIC_SEGMENTS:
            continue
        if len(seg) < 3:
            continue
        out.append(seg)
    return out


def _verify_route_test_coverage(
    definition: ClaimDefinition, rows: list[sqlite3.Row], scan_id: str
) -> VerificationResult:
    """Verify that HTTP routes are exercised by tests.

    Matching is deliberately conservative and explainable. A route counts as
    covered when a test file either imports the route's implementation module,
    or names a distinctive segment of the route path. Test files are aggregated
    first so the comparison stays linear in test FILES, not test cases (large
    repos have thousands of test cases across a few dozen files).

    Absence of tests is missing evidence, never a contradiction.
    """
    # Aggregate tests per file: imports + a single blob of test names.
    test_imports: dict[str, set[str]] = {}
    test_blobs: dict[str, list[str]] = {}
    for row in rows:
        if row["kind"] != "test":
            continue
        try:
            meta = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            meta = {}
        if meta.get("e2e"):
            # E2E specs match by accident (Reality Validation finding); they are
            # weak evidence for concepts and unreliable for route attribution.
            continue
        path = row["path"]
        imports = test_imports.setdefault(path, set())
        for imp in meta.get("imports") or []:
            imports.add(str(imp).lower())
        test_blobs.setdefault(path, []).append(str(row["name"] or "").lower())

    # One joined blob per test file keeps matching linear in test FILES and turns
    # each check into a single substring scan.
    test_name_blob = {p: " ".join(names) for p, names in test_blobs.items()}
    test_import_blob = {p: " ".join(sorted(i)) for p, i in test_imports.items()}

    # Deduplicate routes: several methods on one path are one surface to cover.
    routes: dict[tuple[str, str], sqlite3.Row] = {}
    for row in rows:
        if row["kind"] != "route":
            continue
        try:
            meta = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            meta = {}
        route_path = str(meta.get("path") or row["name"] or "").strip()
        routes.setdefault((row["path"], route_path.lower()), row)

    if not routes:
        return _not_applicable(
            definition,
            scan_id,
            "No HTTP routes were found in the scanned files.",
            "Any HTTP route (Express, Next.js, or FastAPI style).",
        )

    covered: list[tuple[str, str, str]] = []  # (impl path, route path, reason)
    uncovered: list[tuple[str, str]] = []
    for (impl_path, route_path), row in sorted(routes.items()):
        token = _module_token(impl_path)
        reason = ""
        # 1. A test that imports the implementation module.
        if token and len(token) >= 3:
            for test_path, blob in test_import_blob.items():
                if token in blob:
                    reason = f"{test_path} imports {token}"
                    break
        # 2. A test whose names mention a distinctive segment of the route path.
        if not reason:
            segments = _route_tokens(route_path)
            for test_path, blob in test_name_blob.items():
                if segments and any(seg in blob for seg in segments):
                    reason = f"{test_path} names {segments[0]}"
                    break
        if reason:
            covered.append((impl_path, route_path, reason))
        else:
            uncovered.append((impl_path, route_path))

    total = len(routes)
    n_covered = len(covered)
    # Evidence is bounded (responses and stored fingerprints must stay bounded),
    # and truncation is disclosed below rather than hidden.
    _EVIDENCE_CAP = 25
    sha_by_path = {row["path"]: row["sha256"] for row in rows}
    supporting = [
        EvidenceRef(
            path=impl,
            observation=f"Route {route or impl} is referenced by a test ({reason}).",
            kind="route",
            strength="moderate",
            sha256=sha_by_path.get(impl),
        )
        for impl, route, reason in covered[:_EVIDENCE_CAP]
    ]

    why = [f"{n_covered} of {total} routes have a referencing test."]
    missing: list[str] = []
    if n_covered == total:
        status = SUPPORTED
        why.append("Every detected route has at least one test referencing it.")
    else:
        status = WEAK
        why.append(
            "Routes without a referencing test are not proven to be exercised."
        )
        shown = [r or p for p, r in uncovered[:8]]
        missing.append(
            f"Tests referencing {total - n_covered} route(s): " + ", ".join(shown)
            + (" ..." if len(uncovered) > 8 else "")
        )

    limitations = _LIMITATIONS + [
        "Coverage is attributed by test imports and route names, not by executing "
        "tests; a route exercised only indirectly may be reported as uncovered.",
        "End-to-end specs are excluded from attribution because they match by "
        "accident.",
    ]
    if len(covered) > _EVIDENCE_CAP:
        limitations.append(
            f"Evidence is capped at {_EVIDENCE_CAP} routes; freshness tracks only "
            f"those recorded files, not all {len(covered)} covered routes."
        )
    return VerificationResult(
        claim_slug=definition.slug,
        claim_name=definition.name,
        statement=definition.statement,
        status=status,
        why=why,
        supporting=supporting,
        contradictions=[],
        missing=missing,
        limitations=limitations,
        scan_id=scan_id,
        verified_at=_now(),
        engine_version=__version__,
    )


# --------------------------------------------------------------------------- #
# Admin authorization (v0.5.0)
# --------------------------------------------------------------------------- #

_ADMIN_TOKENS = ("admin", "superuser", "staff", "backoffice", "back-office")
_AUTHZ_TOKENS = (
    "requireadmin", "require_admin", "isadmin", "is_admin", "adminonly",
    "admin_only", "hasrole", "has_role", "authorize", "authorization",
    "permission", "rbac", "requireauth", "require_auth", "isauthenticated",
    "current_user", "get_current_user", "authmiddleware", "auth_middleware",
)


def _verify_admin_authorization(
    definition: ClaimDefinition, rows: list[sqlite3.Row], scan_id: str
) -> VerificationResult:
    """Verify that administrative routes require an authorization check.

    Honesty rule for this claim: a missing authorization signal is WEAK, never
    CONTRADICTED. Authorization can be applied globally, by a decorator, or by a
    wrapper the scanner cannot see. Telling someone their admin endpoint is
    unprotected when it is not would destroy the trust this tool is built on.
    """
    admin_routes: list[sqlite3.Row] = []
    authz_files: set[str] = set()
    authz_rows: list[sqlite3.Row] = []

    for row in rows:
        hay = _hay(row)
        kind = row["kind"]
        if kind == "route" and any(t in hay for t in _ADMIN_TOKENS):
            admin_routes.append(row)
        if kind in ("middleware", "auth_dependency") or any(
            t in hay for t in _AUTHZ_TOKENS
        ):
            if kind in ("middleware", "auth_dependency", "route", "test"):
                authz_files.add(row["path"])
                if kind in ("middleware", "auth_dependency"):
                    authz_rows.append(row)

    if not admin_routes:
        return _not_applicable(
            definition,
            scan_id,
            "No administrative routes were found in the scanned files.",
            "An admin, staff, or back-office route.",
        )

    protected: list[sqlite3.Row] = []
    unprotected: list[sqlite3.Row] = []
    for row in admin_routes:
        hay = _hay(row)
        # Authorization evidence in the route's own file, or in the route itself.
        if row["path"] in authz_files or any(t in hay for t in _AUTHZ_TOKENS):
            protected.append(row)
        else:
            unprotected.append(row)

    supporting = [
        _ref(r, "Admin route shows an authorization check in its file.", "moderate")
        for r in protected[:5]
    ] + [
        _ref(r, "Authorization middleware or dependency.", "moderate")
        for r in authz_rows[:2]
    ]

    total = len(admin_routes)
    why = [f"{len(protected)} of {total} administrative route(s) show an "
           "authorization check."]
    missing: list[str] = []

    if not unprotected:
        status = SUPPORTED
        why.append("Every detected admin route has authorization evidence.")
    else:
        status = WEAK
        why.append(
            "No authorization evidence was found for the remaining admin route(s). "
            "This is missing evidence, not proof that they are unprotected."
        )
        missing.append(
            "Authorization evidence for: "
            + ", ".join(sorted({r["path"] for r in unprotected})[:6])
        )

    limitations = _LIMITATIONS + [
        "Authorization applied globally (a server-wide middleware, a router "
        "mount, or a framework decorator the scanner does not parse) is not "
        "detected. A WEAK result means DevTime found no evidence, never that a "
        "route is confirmed unprotected.",
    ]
    return VerificationResult(
        claim_slug=definition.slug,
        claim_name=definition.name,
        statement=definition.statement,
        status=status,
        why=why,
        supporting=supporting,
        contradictions=[],
        missing=missing,
        limitations=limitations,
        scan_id=scan_id,
        verified_at=_now(),
        engine_version=__version__,
    )


def _not_applicable(
    definition: ClaimDefinition, scan_id: str, reason: str, would_need: str
) -> VerificationResult:
    """This claim has no surface in this repository. Say so plainly."""
    return VerificationResult(
        claim_slug=definition.slug,
        claim_name=definition.name,
        statement=definition.statement,
        status=NOT_APPLICABLE,
        why=[reason, "This claim does not apply to this repository."],
        supporting=[],
        contradictions=[],
        missing=[f"Would become verifiable with: {would_need}"],
        limitations=_LIMITATIONS,
        scan_id=scan_id,
        verified_at=_now(),
        engine_version=__version__,
    )


_EVALUATORS = {
    "billing-webhook-signature": _verify_billing_webhook_signature,
    "jwt-authentication": _verify_jwt_authentication,
    "route-test-coverage": _verify_route_test_coverage,
    "admin-authorization": _verify_admin_authorization,
}


def _ref(row: sqlite3.Row, observation: str, strength: str) -> EvidenceRef:
    return EvidenceRef(
        path=row["path"],
        observation=observation,
        kind=row["kind"],
        strength=strength,
        start_line=row["start_line"],
        end_line=row["end_line"],
        sha256=row["sha256"],
    )


# --------------------------------------------------------------------------- #
# Persistence and freshness
# --------------------------------------------------------------------------- #

_VERIFICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS verifications (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    claim_slug TEXT NOT NULL,
    status TEXT NOT NULL,
    scan_id TEXT,
    result_json TEXT NOT NULL,
    evidence_fingerprints_json TEXT NOT NULL DEFAULT '[]',
    engine_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def ensure_verifications_table(conn: sqlite3.Connection) -> None:
    """Idempotent: safe for databases initialized before v0.2.0."""
    conn.execute(_VERIFICATIONS_TABLE)


def save_verification(conn: sqlite3.Connection, result: VerificationResult) -> str:
    """Store an immutable verification result with evidence fingerprints."""
    ensure_verifications_table(conn)
    repo = conn.execute("SELECT id FROM repositories LIMIT 1").fetchone()
    repo_id = repo["id"] if repo else "unknown"
    fingerprints = [
        {"path": e.path, "sha256": e.sha256}
        for e in result.supporting
        if e.sha256
    ]
    # Contradiction evidence participates in freshness too: if the stub changes,
    # the contradiction must be re-checked.
    for c in result.contradictions:
        fingerprints += [
            {"path": e.path, "sha256": e.sha256} for e in c.evidence if e.sha256
        ]
    vid = f"ver-{uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT INTO verifications"
        "(id, repository_id, claim_slug, status, scan_id, result_json, "
        " evidence_fingerprints_json, engine_version, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            vid,
            repo_id,
            result.claim_slug,
            result.status,
            result.scan_id,
            json.dumps(result.to_dict()),
            json.dumps(fingerprints),
            result.engine_version,
            result.verified_at,
        ),
    )
    conn.commit()
    return vid


def load_latest_verification(
    conn: sqlite3.Connection, slug: str
) -> tuple[dict, list[dict], str] | None:
    """Return (result_dict, fingerprints, created_at) for the newest verification."""
    ensure_verifications_table(conn)
    row = conn.execute(
        "SELECT result_json, evidence_fingerprints_json, created_at "
        "FROM verifications WHERE claim_slug = ? ORDER BY created_at DESC LIMIT 1",
        (slug,),
    ).fetchone()
    if row is None:
        return None
    return (
        json.loads(row["result_json"]),
        json.loads(row["evidence_fingerprints_json"]),
        row["created_at"],
    )


def claims_affected_by_paths(
    conn: sqlite3.Connection, changed_paths: list[str]
) -> list[dict]:
    """Claim impact for a set of changed paths (v0.4.0, diff integration).

    For every claim with a stored verification, report it when a changed path
    is one of its recorded evidence files. Only evidence files count: a diff
    touching unrelated files never flags a claim. Advisory output - the caller
    decides what to do with it.
    """
    changed = set(changed_paths)
    out: list[dict] = []
    for slug in BUILTIN_CLAIMS:
        latest = load_latest_verification(conn, slug)
        if latest is None:
            continue
        result, fingerprints, created_at = latest
        evidence_paths = {fp["path"] for fp in fingerprints}
        hits = sorted(evidence_paths & changed)
        if hits:
            out.append(
                {
                    "claim_id": slug,
                    "previous_status": result["status"],
                    "verified_at": created_at,
                    "changed_evidence": hits,
                    "suggested_action": f"dtc verify {slug}",
                }
            )
    return out


def freshness_for(conn: sqlite3.Connection, slug: str) -> tuple[str, list[str]]:
    """Compare stored evidence fingerprints against current file hashes.

    Returns (freshness, changed_paths). Never flags unrelated file changes:
    only files that were evidence for this claim participate.
    """
    latest = load_latest_verification(conn, slug)
    if latest is None:
        return NEEDS_VERIFICATION, []
    _, fingerprints, _ = latest
    changed: list[str] = []
    for fp in fingerprints:
        row = conn.execute(
            "SELECT sha256 FROM files WHERE path = ? ORDER BY last_seen_scan_id DESC LIMIT 1",
            (fp["path"],),
        ).fetchone()
        if row is None or row["sha256"] != fp["sha256"]:
            changed.append(fp["path"])
    if changed:
        return STALE, sorted(set(changed))
    return FRESH, []
