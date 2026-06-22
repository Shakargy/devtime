from devtime.intelligence.claims import build_concept_intelligence
from devtime.intelligence.concepts import ConceptCandidate
from devtime.intelligence.context_pack import MAX_TESTS, generate_context_pack
from devtime.intelligence.evidence import build_evidence
from devtime.scanner.extractors.base import Signal


def _ci(name, slug, signals, confidence, weak_only=False):
    cand = ConceptCandidate(slug=slug, name=name, kind="system_concept",
                            confidence=confidence, signals=signals, weak_only=weak_only)
    return build_concept_intelligence(cand, build_evidence(cand))


def test_weak_concept_pack_is_limited_not_authoritative():
    sig = [Signal(kind="dependency", name="stripe", file_rel_path="package.json", confidence=0.5)]
    ci = _ci("Billing Webhooks", "billing_webhooks", sig, 0.4, weak_only=True)
    pack = generate_context_pack(ci, mode="risk")
    assert pack.limited is True
    assert "limited" in pack.purpose.lower()
    joined = " ".join(pack.do_not_change).lower()
    assert "manual validation required" in joined
    assert "core behavior" not in joined


def test_strong_concept_pack_is_authoritative():
    sig = [
        Signal(kind="webhook_signature_verification", name="stripe",
               file_rel_path="src/billing/webhook.ts", confidence=0.9),
        Signal(kind="route", name="POST /api/stripe/webhook",
               file_rel_path="src/billing/webhook.ts", confidence=0.8),
    ]
    ci = _ci("Billing Webhooks", "billing_webhooks", sig, 0.85)
    pack = generate_context_pack(ci, mode="risk")
    assert pack.limited is False


def test_tests_are_capped_and_have_reasons():
    sig = [Signal(kind="route", name="POST /api/stripe/webhook",
                  file_rel_path="src/billing/webhook.ts", confidence=0.8)]
    # Many keyword-ish tests; only some are in the same module.
    for i in range(20):
        sig.append(Signal(kind="test", name=f"webhook test {i}",
                          file_rel_path=f"tests/misc/t{i}.test.ts", confidence=0.4,
                          metadata={"e2e": False}))
    sig.append(Signal(kind="test", name="stripe signature test",
                      file_rel_path="src/billing/webhook.test.ts", confidence=0.8))
    ci = _ci("Billing Webhooks", "billing_webhooks", sig, 0.85)
    pack = generate_context_pack(ci, mode="risk")
    assert len(pack.tests_to_run) <= MAX_TESTS
    assert all(t.reason for t in pack.tests_to_run)
