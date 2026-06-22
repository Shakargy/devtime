"""v0.0.7 evidence-precision regressions."""

import shutil

import devtime
from conftest import FIXTURES_DIR
from devtime.fixtures.runner import run_devtime_scan
from devtime.intelligence.concepts import detect_concepts
from devtime.intelligence.context_pack import generate_context_pack
from devtime.intelligence.evidence import build_evidence
from devtime.intelligence.claims import build_concept_intelligence
from devtime.scanner.extractors.base import Signal


# --- P1 version ---------------------------------------------------------------

def test_version_is_not_0_1_0():
    assert devtime.__version__ != "0.1.0"
    assert devtime.__version__.startswith("0.0.")


# --- P0 Authentication headline precision ------------------------------------

def _auth_signals_langfuse_style():
    # Real auth route + token, plus peripheral lexical noise (trace + permalink test).
    return [
        Signal(kind="route", name="POST /api/auth/login",
               file_rel_path="src/auth/login.ts", confidence=0.8,
               metadata={"path": "/api/auth/login"}),
        Signal(kind="token_usage", name="jwt", file_rel_path="src/auth/tokens.ts",
               confidence=0.8, metadata={"purpose": "access"}),
        Signal(kind="test", name="captures session_id in trace",
               file_rel_path="src/monitor/trace.test.ts", confidence=0.8,
               metadata={"e2e": False, "imports": []}),
        Signal(kind="test", name="builds permalink from NEXTAUTH_URL",
               file_rel_path="src/monitor/permalink.test.ts", confidence=0.8,
               metadata={"e2e": False, "imports": []}),
    ]


def test_auth_evidence_excludes_session_id_and_nextauth_noise():
    cands = detect_concepts(_auth_signals_langfuse_style())
    auth = next(c for c in cands if c.name == "Authentication")
    paths = " ".join(s.file_rel_path for s in auth.signals)
    assert "trace.test.ts" not in paths
    assert "permalink.test.ts" not in paths
    # Headline presence claim cites the real auth evidence.
    ci = build_concept_intelligence(auth, build_evidence(auth))
    concept_claim = next(c for c in ci.claims if c.type == "concept")
    cited = " ".join(e.path or "" for e in concept_claim.evidence)
    assert "src/auth" in cited


def test_auth_not_high_confidence_from_weak_keywords_only():
    # Only a session_id trace test and a NEXTAUTH_URL permalink test -> dropped.
    signals = [
        Signal(kind="test", name="captures session_id in trace",
               file_rel_path="src/monitor/trace.test.ts", confidence=0.8,
               metadata={"e2e": False, "imports": []}),
        Signal(kind="test", name="permalink uses NEXTAUTH_URL",
               file_rel_path="src/monitor/permalink.test.ts", confidence=0.8,
               metadata={"e2e": False, "imports": []}),
    ]
    cands = detect_concepts(signals)
    assert not any(c.name == "Authentication" for c in cands)


# --- P0 Context Pack truthful reasons ----------------------------------------

def test_context_same_directory_reason_requires_path_locality():
    sig = [
        Signal(kind="route", name="POST /api/stripe/webhook",
               file_rel_path="src/billing/webhook.ts", confidence=0.8),
        Signal(kind="webhook_signature_verification", name="stripe",
               file_rel_path="src/billing/webhook.ts", confidence=0.9),
        Signal(kind="test", name="stripe webhook test",
               file_rel_path="src/billing/webhook.test.ts", confidence=0.8,
               metadata={"e2e": False, "imports": []}),
        Signal(kind="test", name="unrelated webhook test",
               file_rel_path="tests/misc/other.test.ts", confidence=0.4,
               metadata={"e2e": False, "imports": []}),
    ]
    from devtime.intelligence.concepts import ConceptCandidate
    cand = ConceptCandidate(slug="billing_webhooks", name="Billing Webhooks",
                            kind="system_concept", confidence=0.85, signals=sig)
    ci = build_concept_intelligence(cand, build_evidence(cand))
    pack = generate_context_pack(ci, mode="risk")
    for t in pack.tests_to_run:
        if "same directory" in t.reason:
            # Only allowed when the test is actually in an implementation directory.
            assert t.path.startswith("src/billing/")


def test_bg_tasks_test_attaches_with_import_reason(tmp_path):
    src = FIXTURES_DIR / "jobs" / "bg-tasks-test-attaches-to-background-jobs" / "repo"
    intelligence = run_devtime_scan(src)
    bg = next(ci for ci in intelligence if ci.concept.name == "Background Jobs")
    pack = generate_context_pack(bg, mode="risk")
    test_paths = " ".join(t.path for t in pack.tests_to_run)
    assert "bg_tasks" in test_paths
    assert any("imports or tests" in t.reason for t in pack.tests_to_run)
    # Must not say there are no tests.
    assert pack.tests_to_run


# --- P0 Billing negative contexts (corroborates the new fixtures) ------------

def test_cron_calendar_cleanup_is_not_billing():
    repo = FIXTURES_DIR / "billing" / "calendar-subscriptions-cleanup-not-billing" / "repo"
    intelligence = run_devtime_scan(repo)
    assert not any(ci.concept.name == "Billing Webhooks" for ci in intelligence)


# --- Codex blocker 1: Cal.com real paths -------------------------------------

def test_calcom_real_paths_are_not_billing():
    repo = FIXTURES_DIR / "billing" / "calcom-real-paths-not-billing" / "repo"
    intelligence = run_devtime_scan(repo)
    assert not any(ci.concept.name == "Billing Webhooks" for ci in intelligence)


def test_calcom_paths_plus_stripe_is_billing_anchored_on_stripe_only():
    repo = FIXTURES_DIR / "billing" / "calcom-real-paths-plus-stripe-is-billing" / "repo"
    intelligence = run_devtime_scan(repo)
    billing = next(ci for ci in intelligence if ci.concept.name == "Billing Webhooks")
    paths = " ".join(e.path or "" for e in billing.evidence)
    assert "stripe" in paths
    # The calendar/credential negative-context files must NOT be billing evidence.
    assert "calendar-subscriptions" not in paths
    assert "app-credential" not in paths


# --- Codex blocker 2: Langfuse S3 signing diagnostics not auth headline ------

def test_s3_signing_diagnostics_test_is_not_auth_headline():
    signals = [
        Signal(kind="route", name="GET /api/auth/[...nextauth]",
               file_rel_path="src/app/api/auth/[...nextauth]/route.ts", confidence=0.8,
               metadata={"path": "/api/auth/[...nextauth]"}),
        Signal(kind="test", name="signs s3 url for upload diagnostics",
               file_rel_path="packages/shared/src/server/services/s3SigningDiagnostics.test.ts",
               confidence=0.8, metadata={"e2e": False, "imports": []}),
    ]
    cands = detect_concepts(signals)
    auth = next(c for c in cands if c.name == "Authentication")
    paths = " ".join(s.file_rel_path for s in auth.signals)
    assert "s3SigningDiagnostics" not in paths
    ci = build_concept_intelligence(auth, build_evidence(auth))
    concept_claim = next(c for c in ci.claims if c.type == "concept")
    cited = " ".join(e.path or "" for e in concept_claim.evidence)
    assert "s3SigningDiagnostics" not in cited
    assert "auth" in cited.lower()


def test_s3_diagnostics_dropped_even_when_content_mentions_auth():
    # The s3 signing test name mentions "authentication", but its file path is a
    # storage/signing domain -> must be dropped from Authentication evidence.
    signals = [
        Signal(kind="route", name="GET /api/auth/[...nextauth]",
               file_rel_path="src/app/api/auth/[...nextauth]/route.ts", confidence=0.8),
        Signal(kind="test", name="signs s3 url and checks authentication header",
               file_rel_path="packages/shared/src/server/services/s3SigningDiagnostics.test.ts",
               confidence=0.8, metadata={"e2e": False, "imports": ["aws-sdk"]}),
        Signal(kind="test", name="user can log in",
               file_rel_path="web/src/__e2e__/auth.spec.ts", confidence=0.8,
               metadata={"e2e": False, "imports": []}),
    ]
    cands = detect_concepts(signals)
    auth = next(c for c in cands if c.name == "Authentication")
    paths = " ".join(s.file_rel_path for s in auth.signals)
    assert "s3SigningDiagnostics" not in paths
    assert "auth.spec.ts" in paths  # the real auth e2e spec is preferred


# --- Codex blocker 3: Context Pack reasons must be truthful ------------------

def test_cross_package_test_does_not_get_same_directory_reason():
    from devtime.intelligence.concepts import ConceptCandidate
    sig = [
        Signal(kind="route", name="POST /api/stripe/webhook",
               file_rel_path="apps/web/src/billing/webhook.ts", confidence=0.8),
        Signal(kind="webhook_signature_verification", name="stripe",
               file_rel_path="apps/web/src/billing/webhook.ts", confidence=0.9),
        # Unrelated test in a different package; no import of the implementation.
        Signal(kind="test", name="unrelated billing-ish test",
               file_rel_path="apps/api/tests/misc/other.test.ts", confidence=0.8,
               metadata={"e2e": False, "imports": ["lodash"]}),
    ]
    cand = ConceptCandidate(slug="billing_webhooks", name="Billing Webhooks",
                            kind="system_concept", confidence=0.85, signals=sig)
    ci = build_concept_intelligence(cand, build_evidence(cand))
    pack = generate_context_pack(ci, mode="risk")
    for t in pack.tests_to_run:
        if "other.test.ts" in t.path:
            assert "same directory" not in t.reason
    # The unrelated cross-package test should simply be omitted.
    assert not any("other.test.ts" in t.path for t in pack.tests_to_run)


# --- Codex blocker 4: Plane bg_tasks reason is import-based, not same-dir -----

def test_plane_bg_tasks_reason_is_import_not_same_directory():
    repo = FIXTURES_DIR / "jobs" / "bg-tasks-test-attaches-to-background-jobs" / "repo"
    intelligence = run_devtime_scan(repo)
    bg = next(ci for ci in intelligence if ci.concept.name == "Background Jobs")
    pack = generate_context_pack(bg, mode="risk")
    bg_recs = [t for t in pack.tests_to_run if "bg_tasks" in t.path]
    assert bg_recs, "bg_tasks test should be recommended"
    for t in bg_recs:
        assert "imports or tests the implementation" in t.reason
        assert "same directory" not in t.reason
