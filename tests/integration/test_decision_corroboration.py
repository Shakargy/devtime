import shutil

from conftest import FIXTURES_DIR
from devtime.db import connection, repository
from devtime.scanner.signals import run_scan

BILLING_FIXTURE = FIXTURES_DIR / "webhooks" / "billing-webhook-local-stripe" / "repo"


def _scan_temp(tmp_path):
    dest = tmp_path / "repo"
    shutil.copytree(BILLING_FIXTURE, dest)
    run_scan(root=dest)
    return dest


def test_uncorroborated_retry_decision_preserves_uncertainty(tmp_path):
    dest = _scan_temp(tmp_path)
    conn = connection.connect(dest)
    try:
        repository.add_decision(
            conn, "Webhook retry and idempotency strategy",
            "Retry subscription updates up to 3x and dedupe by event id.",
            "billing_webhooks",
        )
        ci = repository.load_concept(conn, "billing_webhooks")
    finally:
        conn.close()
    assert ci is not None
    texts = " ".join(u.text for u in ci.uncertainties).lower()
    assert "not corroborated" in texts
    # An uncorroborated decision must NOT count as decision evidence.
    assert not any(e.kind == "decision" for e in ci.evidence)


def test_arbitrary_decision_does_not_clear_via_uncorroborated_behavior(tmp_path):
    dest = _scan_temp(tmp_path)
    conn = connection.connect(dest)
    try:
        repository.add_decision(
            conn, "Idempotency", "We guarantee idempotency and deduplication.",
            "billing_webhooks",
        )
        ci = repository.load_concept(conn, "billing_webhooks")
    finally:
        conn.close()
    assert any("not corroborated" in u.text.lower() for u in ci.uncertainties)


def test_corroborated_generic_decision_improves_understanding(tmp_path):
    from devtime.intelligence.scoring import compute_understanding

    dest = _scan_temp(tmp_path)
    conn = connection.connect(dest)
    try:
        before = compute_understanding(repository.load_concept(conn, "billing_webhooks")).score
        repository.add_decision(
            conn, "Use Stripe for billing",
            "We use Stripe as the payment provider for subscriptions.",
            "billing_webhooks",
        )
        ci = repository.load_concept(conn, "billing_webhooks")
        after = compute_understanding(ci).score
    finally:
        conn.close()
    # A generic, non-contradictory decision corroborates and improves the score.
    assert any(e.kind == "decision" for e in ci.evidence)
    assert after > before
    assert not any("no decision was found" in u.text.lower() for u in ci.uncertainties)
