"""Comments and string literals must never become behavior evidence (v0.7.0).

DevTime scanning its own repository found the literal
"stripe.Webhook.construct_event" inside its own Python extractor, where it is
the search pattern, and reported billing webhook signature verification as
SUPPORTED. These tests pin the fix.
"""

import re

from devtime.scanner.extractors import typescript as ts
from devtime.scanner.extractors.base import code_only

PY_CALL = re.compile(r"\bWebhook\.construct_event\s*\(")


def _ts_calls(src: str) -> bool:
    return bool(ts._SIGNATURE_CALL_RE.search(code_only(src, "typescript")))


def _py_calls(src: str) -> bool:
    return bool(PY_CALL.search(code_only(src, "python")))


def test_code_only_preserves_length_and_newlines():
    src = 'a = "x\ny"  # c\nb = 1'
    out = code_only(src, "python")
    assert len(out) == len(src)
    assert out.count("\n") == src.count("\n")
    assert "b = 1" in out


def test_real_typescript_calls_are_detected():
    assert _ts_calls("const e = stripe.webhooks.constructEvent(b, s, k);")
    assert _ts_calls("const e = stripeClient.webhooks.constructEvent(b, s, k);")
    assert _ts_calls("const e = await stripe.webhooks.constructEventAsync(b, s, k);")


def test_typescript_names_in_comments_and_strings_are_not_calls():
    assert not _ts_calls("// stripe.webhooks.constructEvent(b, s, k)")
    assert not _ts_calls("/* stripe.webhooks.constructEvent(b) */ const x = 1;")
    assert not _ts_calls('const s = "stripe.webhooks.constructEvent(b)";')
    assert not _ts_calls("const s = `stripe.webhooks.constructEvent(b)`;")
    assert not _ts_calls("const name = 'webhooks.constructEvent';")


def test_url_inside_a_string_does_not_start_a_comment():
    # "https://" contains "//"; treating it as a comment would hide real code.
    assert _ts_calls('const u = "https://api.x.io"; stripe.webhooks.constructEvent(a, b, c);')


def test_detectors_own_search_string_is_not_evidence():
    assert not _py_calls('if "stripe.Webhook.construct_event" in text:')
    assert not _py_calls('"""Calls stripe.Webhook.construct_event(p, s, k)."""')
    assert not _py_calls("# stripe.Webhook.construct_event(p, s, k)")
    assert _py_calls("event = stripe.Webhook.construct_event(p, s, k)")
