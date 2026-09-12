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

import hashlib
import json
import re
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
    # v0.6.0: the complete set of files whose content justified this conclusion.
    # This is NOT the same as `supporting`, which is a bounded selection shown to
    # a human. Displayed evidence may be capped; the dependency set never is,
    # because it is what invalidation is computed from. A WEAK result has
    # dependencies too: the files it examined are exactly what would change the
    # answer.
    dependencies: list[str] = field(default_factory=list)
    # Fingerprint of the surface the claim reasoned about (e.g. the set of
    # application routes). A claim about "all routes" depends on the inventory,
    # so adding a new route must invalidate it even if no existing file changed.
    inventory: str | None = None

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
            # Bounded on purpose: the full dependency list is stored locally and
            # drives invalidation, but responses stay small.
            "dependency_count": len(self.dependencies),
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
    # Slug kept for compatibility; the name and statement no longer claim
    # execution coverage, which static association cannot establish (v0.5.1).
    "route-test-coverage": ClaimDefinition(
        slug="route-test-coverage",
        name="Route Test Association",
        statement="HTTP routes are referenced by tests that request or import them.",
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


def _inventory_fingerprint(items: list[str]) -> str:
    """Stable fingerprint of a surface set (routes, handlers).

    Deterministic and order-independent, so an unchanged repository always
    produces the same value while an added or removed member changes it.
    """
    joined = "\n".join(sorted(items))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _meta(row: sqlite3.Row) -> dict:
    try:
        return json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        return {}


def _route_label(row: sqlite3.Row) -> str:
    """Human-facing route identity: method, path, and file."""
    meta = _meta(row)
    name = row["name"] or meta.get("path") or "route"
    return f"{name} ({row['path']})"


def _hay(row: sqlite3.Row) -> str:
    return " ".join(
        str(x).lower()
        for x in (row["name"], row["value"], row["path"], row["metadata_json"])
        if x is not None
    )


def _is_test_path(path: str) -> bool:
    low = (path or "").lower().replace("\\", "/")
    if ".test." in low or ".spec." in low or "_test." in low:
        return True
    segments = low.split("/")
    return any(
        seg in ("test", "tests", "__tests__", "spec", "specs", "e2e")
        for seg in segments[:-1]
    )


# Directories whose routes are illustrations or fixtures, not application surface.
_NON_APP_SEGMENTS = ("examples", "example", "samples", "demo", "demos",
                     "fixtures", "benchmarks", "docs")


def _is_non_app_path(path: str) -> bool:
    """True for test, example, fixture, and benchmark code.

    A route defined in a test or an example is not part of the application's
    HTTP surface, so it does not belong in an inventory of routes that ought to
    have tests (v0.5.1: express reported 142 such "routes", nearly all of them
    from its own test/ and examples/ directories).
    """
    low = (path or "").lower().replace("\\", "/")
    if _is_test_path(low):
        return True
    return any(seg in _NON_APP_SEGMENTS for seg in low.split("/")[:-1])


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
    # v0.5.1: signature verification must be connected to a webhook handler.
    # Previously a verification helper anywhere in the repository - even one
    # nothing called - supported the claim for every webhook endpoint.
    verify_files: set[str] = set()  # non-test files containing a verification call
    verification_rows: list[sqlite3.Row] = []
    webhook_route_rows: list[sqlite3.Row] = []

    verifications: list[EvidenceRef] = []
    webhook_routes: list[EvidenceRef] = []
    stub_webhooks: list[EvidenceRef] = []
    signature_tests: list[EvidenceRef] = []
    provider_deps: list[EvidenceRef] = []

    for row in rows:
        hay = _hay(row)
        kind = row["kind"]

        if kind == "webhook_signature_verification":
            verification_rows.append(row)
            if not _is_test_path(row["path"]):
                verify_files.add(row["path"])
            verifications.append(
                _ref(row, "Verifies the provider's webhook signature.", "strong")
            )
        elif kind == "route" and "webhook" in hay and _is_billingish(hay):
            webhook_route_rows.append(row)
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

    # Connect each webhook handler to verification in its own file.
    connected = [r for r in webhook_route_rows if r["path"] in verify_files]
    unconnected = [r for r in webhook_route_rows if r["path"] not in verify_files]
    # A verification call that no webhook handler is connected to.
    orphan_verifications = sorted(
        verify_files - {r["path"] for r in webhook_route_rows}
    )

    if webhook_route_rows:
        n_total = len(webhook_route_rows)
        n_connected = len(connected)
        supporting = [
            _ref(
                r,
                "Webhook handler verifies the provider's signature in this file.",
                "strong",
            )
            for r in connected[:6]
        ] + signature_tests[:2]
        why.append(
            f"{n_connected} of {n_total} billing webhook handler(s) verify a "
            "provider signature in the handler's own file."
        )
        if unconnected:
            why.append(
                "The remaining handler(s) have no signature verification connected "
                "to them. This is missing evidence, not proof they are unverified."
            )
            missing.append(
                "Signature verification connected to: "
                + ", ".join(sorted({_route_label(r) for r in unconnected})[:6])
            )
        if orphan_verifications:
            why.append(
                "Signature verification exists in "
                + ", ".join(orphan_verifications[:3])
                + " but no webhook handler there was resolved, so it does not "
                "establish protection for the handlers above."
            )
        for stub in stub_webhooks:
            contradictions.append(
                Contradiction(
                    summary="One webhook endpoint is a disabled stub.",
                    claimed_side=f"{stub.path} is routed as a billing webhook.",
                    observed_side="Its only behavior is a 404/501 response. This "
                    "shows the endpoint is disabled; it is not evidence of a "
                    "runtime vulnerability.",
                    evidence=[stub],
                )
            )
        status = SUPPORTED if n_connected == n_total else WEAK
        if not signature_tests:
            missing.append("A test that exercises webhook signature verification.")
        dependencies = sorted(
            {r["path"] for r in webhook_route_rows}
            | verify_files
            | {r["path"] for r in verification_rows}
        )
        inventory = _inventory_fingerprint(
            [_route_label(r) for r in webhook_route_rows]
        )
        limitations = [
            "Signature verification is connected to a handler when both appear in "
            "the same file. Verification reached through an imported helper is not "
            "resolved yet and is reported as unconnected, never as protected.",
            "Recognized for known provider patterns (e.g. Stripe constructEvent); "
            "custom verification schemes are not detected.",
            "Static evidence does not establish that verification runs before the "
            "handler's side effects.",
            "Coverage follows scanner language support; see LIMITATIONS.md.",
        ]
        return VerificationResult(
            claim_slug=definition.slug,
            claim_name=definition.name,
            statement=definition.statement,
            status=status,
            why=why,
            supporting=supporting,
            contradictions=contradictions,
            missing=missing,
            limitations=limitations,
            scan_id=scan_id,
            verified_at=_now(),
            engine_version=__version__,
            dependencies=dependencies,
            inventory=inventory,
        )

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
        dependencies=sorted(
            {e.path for e in (supporting + verifications + stub_webhooks)}
        ),
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
        dependencies=sorted(
            {
                e.path
                for e in (
                    access_usage + invitation_usage + unclear_usage + jwt_docs + jwt_deps
                )
            }
        ),
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


def _is_prefix_relative(route_path: str) -> bool:
    """True when a route path cannot identify a full URL on its own.

    FastAPI and Express routers are commonly declared relative to a mount
    prefix (`APIRouter()` + `include_router(..., prefix="/api/v1/items")`), so a
    declared path of "/" or "/{id}" says nothing about the served URL.
    """
    p = (route_path or "").strip()
    return p in ("", "/") or p.startswith("/{") or p.startswith("/:")


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
    """Verify that HTTP routes have tests importing their implementation.

    v0.5.1 correction: static association is not execution coverage, and a test
    that merely shares a word with a route path proves nothing. Two evidence
    levels are now distinguished:

      import association - a test file imports the route's implementation
                           module (exact module-stem match, so `users` does not
                           match `superusers`). This is the only level that can
                           support the claim.
      name similarity    - a test name mentions a route segment. Reported as an
                           unverified suggestion; it can never raise the status.

    Route identity keeps the HTTP method, so a test touching GET does not
    establish anything about POST on the same path.

    Absence of tests is missing evidence, never a contradiction.
    """
    # Aggregate tests per file: imports + a single blob of test names.
    test_imports: dict[str, set[str]] = {}
    test_requests: dict[str, set[tuple[str, str]]] = {}
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
        reqs = test_requests.setdefault(path, set())
        for req in meta.get("requests") or []:
            reqs.add(
                (
                    str(req.get("method", "")).upper(),
                    str(req.get("path", "")).lower().rstrip("/") or "/",
                )
            )
        test_blobs.setdefault(path, []).append(str(row["name"] or "").lower())

    # One joined blob per test file keeps name matching linear in test FILES.
    test_name_blob = {p: " ".join(names) for p, names in test_blobs.items()}
    # Imports are reduced to exact module stems, so importing "superusers" is not
    # treated as importing "users" (v0.5.1: substring matching did exactly that).
    test_import_stems = {
        p: {_module_token(imp) for imp in imports} for p, imports in test_imports.items()
    }

    # Route identity keeps the HTTP method: a test touching GET establishes
    # nothing about POST on the same path.
    routes: dict[tuple[str, str, str], sqlite3.Row] = {}
    excluded_non_app = 0
    for row in rows:
        if row["kind"] != "route":
            continue
        # Routes defined inside tests, examples, or fixtures are not the
        # application's HTTP surface and must not be counted as untested.
        if _is_non_app_path(row["path"]):
            excluded_non_app += 1
            continue
        meta = _meta(row)
        route_path = str(meta.get("path") or row["name"] or "").strip()
        method = str(meta.get("method") or "ANY").upper()
        routes.setdefault((row["path"], route_path.lower(), method), row)

    if not routes:
        reason = "No application HTTP routes were found in the scanned files."
        if excluded_non_app:
            reason += (
                f" {excluded_non_app} route(s) were found only in test, example, "
                "or fixture files, which are not application surface."
            )
        return _not_applicable(
            definition,
            scan_id,
            reason,
            "Any HTTP route in application code (Express, Next.js, or FastAPI style).",
        )

    associated: list[tuple[str, str, str]] = []  # (impl path, label, reason)
    suggested: list[tuple[str, str, str]] = []  # name similarity only
    unassociated: list[tuple[str, str]] = []
    unresolved: list[tuple[str, str]] = []  # full URL cannot be determined
    for (impl_path, route_path, method), row in sorted(routes.items()):
        label = f"{method} {route_path}" if route_path else impl_path
        token = _module_token(impl_path)
        reason = ""
        # Strongest available level: a test that requests this exact endpoint.
        norm_path = route_path.rstrip("/") or "/"
        for test_path, reqs in test_requests.items():
            if (method, norm_path) in reqs or ("ANY", norm_path) in reqs:
                reason = f"{test_path} requests {method} {route_path}"
                break
            if method == "ANY" and any(p == norm_path for _m, p in reqs):
                reason = f"{test_path} requests {route_path}"
                break
        # Next level: a test importing this module.
        if not reason and token and len(token) >= 3:
            for test_path, stems in test_import_stems.items():
                if token in stems:
                    reason = f"{test_path} imports {token}"
                    break
        if reason:
            associated.append((impl_path, label, reason))
            continue
        # Name similarity is a suggestion, never support.
        hint = ""
        segments = _route_tokens(route_path)
        for test_path, blob in test_name_blob.items():
            if segments and any(seg in blob for seg in segments):
                hint = f"{test_path} mentions '{segments[0]}'"
                break
        if hint:
            suggested.append((impl_path, label, hint))
        # A prefix-relative path ("/" or "/{id}") does not identify a full URL:
        # the router's mount prefix was not resolved, so this is a gap in the
        # analysis, not evidence that the route lacks a test.
        if _is_prefix_relative(route_path):
            unresolved.append((impl_path, label))
        else:
            unassociated.append((impl_path, label))

    total = len(routes)
    n_assoc = len(associated)
    n_unresolved = len(unresolved)
    # Evidence shown to the user is bounded; the dependency set used for
    # invalidation is tracked separately and is not capped.
    _EVIDENCE_CAP = 25
    sha_by_path = {row["path"]: row["sha256"] for row in rows}
    supporting = [
        EvidenceRef(
            path=impl,
            observation=f"Route {label} has a test importing its implementation "
            f"({reason}).",
            kind="route",
            strength="moderate",
            sha256=sha_by_path.get(impl),
        )
        for impl, label, reason in associated[:_EVIDENCE_CAP]
    ]

    why = [
        f"{n_assoc} of {total} routes are referenced by a test that requests or "
        f"imports them."
    ]
    missing: list[str] = []
    if n_assoc == total:
        status = SUPPORTED
        why.append(
            "Every detected route is referenced by a test that requests or imports "
            "it. This is a static association, not proof the route was executed "
            "or that its assertions cover the behavior."
        )
    else:
        status = WEAK
        if unassociated:
            why.append(
                "Routes with no requesting or importing test have no established "
                "association."
            )
            shown = [label for _, label in unassociated[:8]]
            missing.append(
                f"A test requesting or importing {len(unassociated)} route(s): "
                + ", ".join(shown)
                + (" ..." if len(unassociated) > 8 else "")
            )
        if unresolved:
            why.append(
                f"{n_unresolved} route(s) are declared relative to a router mount "
                "prefix that DevTime did not resolve, so their full URL is unknown. "
                "That is a gap in this analysis, not evidence that they lack tests."
            )
            missing.append(
                "A resolvable full URL for: "
                + ", ".join(label for _, label in unresolved[:6])
            )
    if suggested:
        why.append(
            f"{len(suggested)} route(s) share vocabulary with a test name but no "
            "request or import was found. Name similarity is a suggestion, not "
            "evidence: "
            + suggested[0][2]
        )

    # Dependencies: every application route file and every test file that was
    # considered. Editing a test that justified an association must invalidate
    # the result, which v0.5.x did not do because only route files were stored.
    dependencies = sorted(
        {impl for (impl, _p, _m) in routes.keys()}
        | set(test_name_blob.keys())
        | set(test_requests.keys())
    )
    inventory = _inventory_fingerprint(
        [f"{m} {p} {impl}" for (impl, p, m) in routes.keys()]
    )

    limitations = [
        "Association is established from a test that requests the exact route "
        "path, or from a test that imports the route's implementation module. A "
        "test that reaches a route only through a variable URL, a helper, or a "
        "mounted prefix DevTime cannot resolve is reported as unassociated.",
        "A static import association is not execution coverage. It does not "
        "establish that the route ran, that assertions covered its behavior, or "
        "that the test passes.",
        "End-to-end specs are excluded from attribution because their names match "
        "by accident; a direct request made by an e2e test is not yet resolved.",
        "Coverage follows scanner language support; see LIMITATIONS.md.",
    ]
    if len(associated) > _EVIDENCE_CAP:
        limitations.append(
            f"Displayed evidence is capped at {_EVIDENCE_CAP} of {len(associated)} "
            "associated routes."
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
        dependencies=dependencies,
        inventory=inventory,
    )


# --------------------------------------------------------------------------- #
# Admin authorization (v0.5.0)
# --------------------------------------------------------------------------- #

_ADMIN_TOKENS = ("admin", "superuser", "staff", "backoffice", "back-office")

# Authorization: establishes a role or permission decision.
_AUTHZ_TOKENS = (
    "requireadmin", "require_admin", "isadmin", "is_admin", "adminonly",
    "admin_only", "hasrole", "has_role", "requirerole", "require_role",
    "authorize", "requirepermission", "require_permission", "checkpermission",
    "check_permission", "haspermission", "has_permission", "rbac", "withadmin",
    "with_admin", "adminguard", "admin_guard", "ensureadmin", "ensure_admin",
)

# Authentication: establishes identity only. Knowing WHO the caller is does not
# establish that they are ALLOWED to use an administrative endpoint, so these
# never satisfy the authorization claim on their own.
_AUTHN_ONLY_TOKENS = (
    "requireauth", "require_auth", "isauthenticated", "is_authenticated",
    "ensureauth", "ensure_auth", "authmiddleware", "auth_middleware",
    "current_user", "currentuser", "get_current_user", "getcurrentuser",
    "requirelogin", "require_login", "withauth", "with_auth",
)

_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def _executable_text(fragment: str) -> str:
    """Strip comments so commented-out guards cannot become evidence."""
    return _COMMENT_RE.sub(" ", fragment or "").lower()


def _verify_admin_authorization(
    definition: ClaimDefinition, rows: list[sqlite3.Row], scan_id: str
) -> VerificationResult:
    """Verify that administrative routes require an authorization check.

    Honesty rule for this claim: a missing authorization signal is WEAK, never
    CONTRADICTED. Authorization can be applied globally, by a decorator, or by a
    wrapper the scanner cannot see. Telling someone their admin endpoint is
    unprotected when it is not would destroy the trust this tool is built on.
    """
    # Surface detection uses the ROUTE PATH only. A file named permissions.ts is
    # not evidence about behavior (v0.5.1: it previously was, and produced
    # SUPPORTED on routes with no guard at all).
    admin_routes: list[sqlite3.Row] = []
    for row in rows:
        if row["kind"] != "route":
            continue
        meta = _meta(row)
        route_path = str(meta.get("path") or row["name"] or "").lower()
        if any(t in route_path for t in _ADMIN_TOKENS):
            admin_routes.append(row)

    if not admin_routes:
        return _not_applicable(
            definition,
            scan_id,
            "No administrative routes were found in the scanned files.",
            "An admin, staff, or back-office route.",
        )

    guarded: list[sqlite3.Row] = []
    identity_only: list[sqlite3.Row] = []
    unresolved: list[sqlite3.Row] = []  # no call-site evidence available
    no_guard: list[sqlite3.Row] = []

    for row in admin_routes:
        meta = _meta(row)
        if "handlers" not in meta:
            # Next.js and other file-based routes have no argument list to read.
            unresolved.append(row)
            continue
        call_site = _executable_text(str(meta.get("handlers") or ""))
        if any(t in call_site for t in _AUTHZ_TOKENS):
            guarded.append(row)
        elif any(t in call_site for t in _AUTHN_ONLY_TOKENS):
            identity_only.append(row)
        else:
            no_guard.append(row)

    supporting = [
        _ref(
            r,
            f"Authorization guard is applied at this route's own call site "
            f"({str(_meta(r).get('handlers') or '')[:80]}).",
            "strong",
        )
        for r in guarded[:5]
    ]

    total = len(admin_routes)
    why = [
        f"{len(guarded)} of {total} administrative route(s) have an authorization "
        "guard at their own call site."
    ]
    missing: list[str] = []

    if len(guarded) == total:
        status = SUPPORTED
        why.append("Every detected admin route applies an authorization guard directly.")
    else:
        status = WEAK
        if identity_only:
            why.append(
                f"{len(identity_only)} route(s) apply an authentication check but no "
                "role or permission check. Knowing who the caller is does not "
                "establish that they may use an administrative endpoint."
            )
            missing.append(
                "A role or permission check for: "
                + ", ".join(sorted({_route_label(r) for r in identity_only})[:6])
            )
        if no_guard:
            why.append(
                f"{len(no_guard)} route(s) have no guard at their call site. This is "
                "missing evidence, not proof that they are unprotected."
            )
            missing.append(
                "Authorization evidence for: "
                + ", ".join(sorted({_route_label(r) for r in no_guard})[:6])
            )
        if unresolved:
            why.append(
                f"{len(unresolved)} route(s) use a routing style whose guard "
                "association DevTime cannot resolve yet."
            )
            missing.append(
                "A resolvable guard association for: "
                + ", ".join(sorted({_route_label(r) for r in unresolved})[:6])
            )

    dependencies = sorted({r["path"] for r in admin_routes})
    inventory = _inventory_fingerprint([_route_label(r) for r in admin_routes])

    limitations = [
        "Authorization is established only from a guard applied at the route's own "
        "call site. Guards applied by a router mount, a server-wide middleware, or "
        "a framework decorator are not resolved yet and are reported as unresolved, "
        "never as protected.",
        "A WEAK result means DevTime found no connected authorization evidence. It "
        "is never proof that a route is unprotected.",
        "Coverage follows scanner language support; see LIMITATIONS.md.",
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
        dependencies=dependencies,
        inventory=inventory,
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
    inventory_fingerprint TEXT,
    engine_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def ensure_verifications_table(conn: sqlite3.Connection) -> None:
    """Idempotent: safe for databases initialized before v0.2.0.

    v0.6.0 adds inventory_fingerprint. Existing rows keep NULL, which is read as
    "inventory was not tracked when this was recorded" and triggers
    re-verification rather than an unjustified FRESH.
    """
    conn.execute(_VERIFICATIONS_TABLE)
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(verifications)")
    }
    if "inventory_fingerprint" not in columns:
        conn.execute("ALTER TABLE verifications ADD COLUMN inventory_fingerprint TEXT")
    conn.commit()


def save_verification(conn: sqlite3.Connection, result: VerificationResult) -> str:
    """Store an immutable verification result with its dependency fingerprints.

    v0.6.0: fingerprints come from the complete dependency set, not from the
    bounded list of evidence shown to the user. Previously a route/test claim
    stored only route files, so editing the test that justified the association
    left the result reported as FRESH.
    """
    ensure_verifications_table(conn)
    repo = conn.execute("SELECT id FROM repositories LIMIT 1").fetchone()
    repo_id = repo["id"] if repo else "unknown"

    paths: set[str] = set(result.dependencies)
    paths |= {e.path for e in result.supporting}
    # Contradiction evidence participates in freshness too: if the stub changes,
    # the contradiction must be re-checked.
    for c in result.contradictions:
        paths |= {e.path for e in c.evidence}

    sha_by_path = {
        row["path"]: row["sha256"]
        for row in conn.execute("SELECT path, sha256 FROM files").fetchall()
    }
    fingerprints = [
        {"path": p, "sha256": sha_by_path.get(p)} for p in sorted(paths)
    ]
    vid = f"ver-{uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT INTO verifications"
        "(id, repository_id, claim_slug, status, scan_id, result_json, "
        " evidence_fingerprints_json, inventory_fingerprint, engine_version, "
        " created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            vid,
            repo_id,
            result.claim_slug,
            result.status,
            result.scan_id,
            json.dumps(result.to_dict()),
            json.dumps(fingerprints),
            result.inventory,
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


def scan_state(conn: sqlite3.Connection, root=None) -> dict:
    """Describe the evidence snapshot a verification is about to be computed from.

    Verification recomputes conclusions from the last persisted scan. That is
    not the same as the working tree, and reporting a fresh evaluation timestamp
    without saying so implies evidence that was never collected. This returns
    the facts a caller needs to be honest about what was actually examined:

      scan_id / scanned_at  which snapshot was used
      files_scanned         its size
      working_tree          "unchecked", "matches_scan", or "changed_since_scan"
      changed_paths         files whose content no longer matches the snapshot
    """
    from pathlib import Path

    from devtime import paths as _paths

    row = conn.execute(
        "SELECT id, started_at, finished_at, file_count, status FROM scans "
        "WHERE status = 'completed' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return {
            "scan_id": None,
            "scanned_at": None,
            "files_scanned": 0,
            "working_tree": "never_scanned",
            "changed_paths": [],
        }

    state = {
        "scan_id": row["id"],
        "scanned_at": row["finished_at"] or row["started_at"],
        "files_scanned": row["file_count"],
        "working_tree": "unchecked",
        "changed_paths": [],
    }

    # A bounded, read-only check of the files this scan recorded. Hashing is
    # capped so a verification never turns into a second full scan.
    import hashlib as _hashlib

    repo_root = Path(root) if root else _paths.repo_root()
    rows = conn.execute(
        "SELECT path, sha256 FROM files WHERE last_seen_scan_id = ? AND sha256 IS NOT NULL",
        (row["id"],),
    ).fetchall()
    if not rows:
        return state

    _CHECK_CAP = 400
    changed: list[str] = []
    checked = 0
    for f in rows:
        if checked >= _CHECK_CAP:
            state["working_tree"] = "partially_checked"
            break
        target = repo_root / f["path"]
        checked += 1
        try:
            if not target.exists():
                changed.append(f["path"])
                continue
            digest = _hashlib.sha256(target.read_bytes()).hexdigest()
        except OSError:
            continue
        if digest != f["sha256"]:
            changed.append(f["path"])
    if changed:
        state["working_tree"] = "changed_since_scan"
        state["changed_paths"] = sorted(changed)[:20]
    elif state["working_tree"] == "unchecked":
        state["working_tree"] = "matches_scan"
    return state


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
    """Compare stored dependency fingerprints against the latest scan.

    Returns (freshness, changed_paths). Only files this claim actually depended
    on participate, so unrelated edits never mark a claim stale.

    v0.6.0 fixes three ways a result could look current when it was not:
      - a dependency file DELETED from the repository (its old row survived in
        `files`, so the hash still matched and the claim looked FRESH);
      - a dependency file that was never re-seen by the latest scan (ignored,
        renamed, or excluded by a policy change);
      - a change to the claim's INVENTORY, such as a new route appearing, which
        changes the answer without changing any previously recorded file.
    """
    latest = load_latest_verification(conn, slug)
    if latest is None:
        return NEEDS_VERIFICATION, []
    result_dict, fingerprints, _ = latest

    if not fingerprints:
        # Nothing was recorded to justify this result, so "fresh" cannot be
        # asserted. Re-verify rather than claim currency we cannot support.
        return NEEDS_VERIFICATION, []

    scan_id = _latest_scan_id(conn)
    if scan_id is None:
        return NEEDS_VERIFICATION, []

    current = {
        row["path"]: row
        for row in conn.execute(
            "SELECT path, sha256, last_seen_scan_id FROM files"
        ).fetchall()
    }

    changed: list[str] = []
    for fp in fingerprints:
        row = current.get(fp["path"])
        if row is None:
            changed.append(fp["path"])  # never seen again
            continue
        if row["last_seen_scan_id"] != scan_id:
            # Present in an older scan only: deleted, renamed, or now ignored.
            changed.append(fp["path"])
            continue
        if row["sha256"] != fp["sha256"]:
            changed.append(fp["path"])

    if changed:
        return STALE, sorted(set(changed))

    # The recorded surface set must still match what the repository has now.
    stored_inventory = conn.execute(
        "SELECT inventory_fingerprint FROM verifications WHERE claim_slug = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (slug,),
    ).fetchone()
    stored = stored_inventory["inventory_fingerprint"] if stored_inventory else None
    if stored is not None:
        try:
            current_result = verify_claim(conn, slug)
        except KeyError:
            return FRESH, []
        if current_result.inventory is not None and current_result.inventory != stored:
            return STALE, ["(the set of routes or handlers this claim covers changed)"]
    return FRESH, []
