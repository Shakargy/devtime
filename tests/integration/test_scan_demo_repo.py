from pathlib import Path

from conftest import ROOT
from devtime.fixtures.runner import run_devtime_scan


def test_scan_demo_repo_detects_core_concepts():
    repo = ROOT / "examples" / "demo-saas"
    intelligence = run_devtime_scan(repo)
    names = {ci.concept.name for ci in intelligence}
    assert "Authentication" in names
    assert "Billing Webhooks" in names


def test_billing_webhooks_has_missing_decision_uncertainty():
    repo = ROOT / "examples" / "demo-saas"
    intelligence = run_devtime_scan(repo)
    billing = next(ci for ci in intelligence if ci.concept.name == "Billing Webhooks")
    assert any("decision" in u.text.lower() for u in billing.uncertainties)
