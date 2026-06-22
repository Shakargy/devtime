from conftest import ROOT
from devtime.fixtures.runner import run_devtime_scan
from devtime.intelligence.risk import parse_unified_diff, review_diff

RETRY_DIFF = """\
--- a/src/billing/stripe-webhook.ts
+++ b/src/billing/stripe-webhook.ts
@@
-    await updateSubscriptionState(event.data.object);
+    for (let attempt = 0; attempt < 3; attempt++) {
+      // retry the subscription update on transient failures
+      await updateSubscriptionState(event.data.object);
+    }
"""


def test_retry_change_without_test_is_flagged():
    repo = ROOT / "examples" / "demo-saas"
    intelligence = run_devtime_scan(repo)
    info = parse_unified_diff(RETRY_DIFF)
    review = review_diff(info, intelligence)
    assert review.state == "finding", review.state
    top = review.findings[0]
    assert top.concept == "Billing Webhooks"
    assert top.severity == "high"
