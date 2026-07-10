"""Claim verification engine (v0.2.0 - the verification slice).

DevTime's evolution target: the verification layer for repository understanding.
A claim is a statement about the repository; verification evaluates it against
persisted scan evidence and answers with a status, both-sided contradictions,
missing evidence, coverage limitations, and freshness - never with confidence
the evidence cannot back.

V0.2 scope, deliberately narrow:
  - Built-in claims only (no user-defined claim files yet).
  - One claim domain: billing webhook signature verification.
  - Four statuses: SUPPORTED, WEAK, CONTRADICTED, UNKNOWN.
  - Freshness from file fingerprints: FRESH, STALE, NEEDS_VERIFICATION.
  - Deterministic and rule-driven. No AI, no network, no code execution.

Statuses (documented meaning, per repository evidence policy - not formal proof):
  SUPPORTED     required behavior evidence exists in the current scan.
  WEAK          the claim's surface exists, but the proving evidence is missing.
  CONTRADICTED  credible evidence conflicts with the claim; both sides are shown.
  UNKNOWN       the repository shows no relevant surface, or coverage cannot
                responsibly decide.

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
        return {
            "schema_version": "1",
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
}

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

def verify_claim(conn: sqlite3.Connection, slug: str) -> VerificationResult:
    """Verify one built-in claim against the latest completed scan."""
    definition = BUILTIN_CLAIMS.get(slug)
    if definition is None:
        raise KeyError(slug)

    scan_id = _latest_scan_id(conn)
    if scan_id is None:
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

    rows = _load_signals(conn, scan_id)
    return _verify_billing_webhook_signature(definition, rows, scan_id)


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
        status = UNKNOWN
        why.append(
            "No billing webhook surface was found in the scanned files. "
            "The claim does not apply, or the surface is outside scanner coverage."
        )
        missing.append("Any billing webhook route, handler, or provider dependency.")

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
