"""Tests for the claim verification engine (v0.2.0 verification slice).

Covers the four statuses, both-sided contradictions, fingerprint freshness,
CLI surface, JSON schema stability, and MCP tool registration.
"""

import asyncio
import json

from typer.testing import CliRunner

from devtime.cli import app
from devtime.db import connection
from devtime.intelligence import verification as ver

runner = CliRunner()


def _repo(tmp_path, files: dict[str, str]):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _init_scan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["scan"]).exit_code == 0


STRIPE_HANDLER = """
import Stripe from "stripe";
const stripe = new Stripe(process.env.KEY);
export default async function handler(req, res) {
  const event = stripe.webhooks.constructEvent(req.body, req.headers["stripe-signature"], secret);
  res.json({ received: true });
}
"""

SIGNATURE_TEST = """
import { describe, it } from "vitest";
describe("stripe webhook signature", () => {
  it("rejects an invalid signature", () => {});
});
"""

STUB_HANDLER = """
import type { NextApiRequest, NextApiResponse } from "next";
export default function handler(_req: NextApiRequest, res: NextApiResponse) {
  res.status(404).json({ message: "Billing webhooks are not available in this edition" });
}
"""

PACKAGE_WITH_STRIPE = '{ "name": "x", "dependencies": { "stripe": "^14.0.0" } }'


def _verify(slug="billing-webhook-signature"):
    conn = connection.connect()
    try:
        return ver.verify_claim(conn, slug)
    finally:
        conn.close()


# --- statuses -----------------------------------------------------------------

def test_supported_when_signature_verification_exists(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/billing/stripe-webhook.ts": STRIPE_HANDLER,
        "tests/stripe-signature.test.ts": SIGNATURE_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify()
    assert result.status == ver.SUPPORTED
    paths = {e.path for e in result.supporting}
    assert any("stripe-webhook" in p for p in paths)


def test_weak_when_surface_exists_without_verification(tmp_path, monkeypatch):
    _repo(tmp_path, {"package.json": PACKAGE_WITH_STRIPE})
    _init_scan(tmp_path, monkeypatch)
    result = _verify()
    assert result.status == ver.WEAK
    assert any("verification" in m.lower() for m in result.missing)


def test_contradicted_on_disabled_stub(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "apps/web/pages/api/stripe/webhook.ts": STUB_HANDLER,
        "package.json": PACKAGE_WITH_STRIPE,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify()
    assert result.status == ver.CONTRADICTED
    assert result.contradictions
    c = result.contradictions[0]
    # A contradiction must always show both sides.
    assert c.claimed_side and c.observed_side
    assert "stub" in c.summary.lower() or "stub" in c.observed_side.lower()


def test_unknown_when_no_billing_surface(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/util/math.ts": "export const add = (a, b) => a + b;\n"})
    _init_scan(tmp_path, monkeypatch)
    result = _verify()
    assert result.status == ver.UNKNOWN


def test_supported_with_stub_elsewhere_reports_contradiction_but_stays_supported(
    tmp_path, monkeypatch
):
    _repo(tmp_path, {
        "src/billing/stripe-webhook.ts": STRIPE_HANDLER,
        "apps/web/pages/api/stripe/webhook.ts": STUB_HANDLER,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify()
    assert result.status == ver.SUPPORTED
    assert result.contradictions  # surfaced, not fatal


# --- freshness ------------------------------------------------------------------

def test_freshness_needs_verification_then_fresh_then_stale(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/billing/stripe-webhook.ts": STRIPE_HANDLER,
    })
    _init_scan(tmp_path, monkeypatch)

    conn = connection.connect()
    try:
        freshness, _ = ver.freshness_for(conn, "billing-webhook-signature")
        assert freshness == ver.NEEDS_VERIFICATION

        result = ver.verify_claim(conn, "billing-webhook-signature")
        ver.save_verification(conn, result)
        freshness, changed = ver.freshness_for(conn, "billing-webhook-signature")
        assert freshness == ver.FRESH
        assert changed == []
    finally:
        conn.close()

    # Change the supporting evidence file and rescan.
    handler = tmp_path / "src/billing/stripe-webhook.ts"
    handler.write_text(STRIPE_HANDLER + "\n// changed\n", encoding="utf-8")
    assert runner.invoke(app, ["scan", "--refresh"]).exit_code == 0

    conn = connection.connect()
    try:
        freshness, changed = ver.freshness_for(conn, "billing-webhook-signature")
        assert freshness == ver.STALE
        assert any("stripe-webhook" in p for p in changed)
    finally:
        conn.close()


def test_unrelated_change_does_not_go_stale(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/billing/stripe-webhook.ts": STRIPE_HANDLER,
        "README.md": "# App\n",
    })
    _init_scan(tmp_path, monkeypatch)
    conn = connection.connect()
    try:
        ver.save_verification(conn, ver.verify_claim(conn, "billing-webhook-signature"))
    finally:
        conn.close()

    (tmp_path / "README.md").write_text("# App changed\n", encoding="utf-8")
    assert runner.invoke(app, ["scan", "--refresh"]).exit_code == 0

    conn = connection.connect()
    try:
        freshness, _ = ver.freshness_for(conn, "billing-webhook-signature")
        assert freshness == ver.FRESH
    finally:
        conn.close()


# --- determinism ----------------------------------------------------------------

def test_repeated_verification_is_deterministic(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/billing/stripe-webhook.ts": STRIPE_HANDLER,
        "tests/stripe-signature.test.ts": SIGNATURE_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    a, b = _verify(), _verify()
    da, db = a.to_dict(), b.to_dict()
    for k in ("status", "why", "missing_evidence", "supporting_evidence", "contradictions"):
        assert da[k] == db[k]


# --- CLI surface -----------------------------------------------------------------

def test_cli_verify_json_schema(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/billing/stripe-webhook.ts": STRIPE_HANDLER})
    _init_scan(tmp_path, monkeypatch)
    result = runner.invoke(app, ["verify", "billing-webhook-signature", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1"
    r = payload["results"][0]
    for key in ("claim_id", "status", "why", "supporting_evidence",
                "contradictions", "missing_evidence", "limitations"):
        assert key in r


def test_cli_verify_list_shows_freshness(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/billing/stripe-webhook.ts": STRIPE_HANDLER})
    _init_scan(tmp_path, monkeypatch)
    result = runner.invoke(app, ["verify", "--list"])
    assert result.exit_code == 0
    assert "billing-webhook-signature" in result.stdout
    assert "NEEDS_VERIFICATION" in result.stdout


def test_cli_verify_unknown_claim_exits_nonzero(tmp_path, monkeypatch):
    _repo(tmp_path, {"README.md": "# x\n"})
    _init_scan(tmp_path, monkeypatch)
    result = runner.invoke(app, ["verify", "not-a-claim"])
    assert result.exit_code == 1


def test_cli_verify_uninitialized_exits_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 2


# --- MCP surface -----------------------------------------------------------------

def test_mcp_exposes_verify_claim(tmp_path, monkeypatch):
    from devtime.mcp.transport import IMPLEMENTED_TOOLS, build_server

    assert "verify_claim" in IMPLEMENTED_TOOLS
    server = build_server()
    tools = asyncio.run(server.list_tools())
    assert "verify_claim" in {t.name for t in tools}

    _repo(tmp_path, {"src/billing/stripe-webhook.ts": STRIPE_HANDLER})
    _init_scan(tmp_path, monkeypatch)
    result = asyncio.run(
        server.call_tool("verify_claim", {"claim_id": "billing-webhook-signature"})
    )
    text = str(result)
    assert "SUPPORTED" in text
    assert "stripe-webhook" in text
