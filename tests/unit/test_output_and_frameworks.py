from conftest import ROOT
from devtime.fixtures.runner import run_devtime_scan
from devtime.intelligence.claims import build_concept_intelligence
from devtime.intelligence.concepts import ConceptCandidate
from devtime.intelligence.evidence import build_evidence
from devtime.intelligence.scoring import compute_understanding
from devtime.scanner.extractors.base import Signal
from devtime.scanner.signals import detect_framework_warnings


def _ci(signals, confidence, weak_only=False, name="File Uploads", slug="file_uploads"):
    cand = ConceptCandidate(slug=slug, name=name, kind="system_concept",
                            confidence=confidence, signals=signals, weak_only=weak_only)
    return build_concept_intelligence(cand, build_evidence(cand))


def test_freshness_is_not_scored():
    sig = [Signal(kind="dependency", name="multer", file_rel_path="package.json", confidence=0.5)]
    us = compute_understanding(_ci(sig, 0.4, weak_only=True))
    assert us.dimensions["freshness"] == "not measured in V0"


def test_low_confidence_concept_does_not_claim_is_present():
    sig = [Signal(kind="dependency", name="multer", file_rel_path="package.json", confidence=0.5)]
    ci = _ci(sig, 0.4, weak_only=True)
    concept_claim = next(c for c in ci.claims if c.type == "concept")
    assert "is present" not in concept_claim.text.lower()
    assert "possible" in concept_claim.text.lower()


def test_uncertainty_does_not_contradict_presence():
    sig = [Signal(kind="dependency", name="multer", file_rel_path="package.json", confidence=0.5)]
    ci = _ci(sig, 0.4, weak_only=True)
    claim_text = " ".join(c.text.lower() for c in ci.claims)
    # Must never assert presence AND say presence is not confirmed.
    if "presence is not confirmed" in " ".join(u.text.lower() for u in ci.uncertainties):
        assert "is present" not in claim_text


def test_django_framework_warning():
    sig = [Signal(kind="dependency", name="django", file_rel_path="requirements.txt", confidence=0.6)]
    warnings = detect_framework_warnings(sig)
    assert any("django" in w.lower() for w in warnings)


def test_nestjs_framework_warning():
    sig = [Signal(kind="dependency", name="@nestjs/core", file_rel_path="package.json", confidence=0.6)]
    warnings = detect_framework_warnings(sig)
    assert any("nestjs" in w.lower() for w in warnings)


def test_scan_reports_pruned_and_skipped_counts():
    result = run_devtime_scan_with_result()
    assert result.pruned_dirs >= 0
    assert result.skipped_files >= 0
    assert result.duration_seconds >= 0


def run_devtime_scan_with_result():
    # Helper: scan the demo in an isolated copy and return the ScanResult.
    import shutil
    import tempfile
    from pathlib import Path

    from devtime.scanner.signals import run_scan

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "repo"
        shutil.copytree(ROOT / "examples" / "demo-saas", dest)
        return run_scan(root=dest)
