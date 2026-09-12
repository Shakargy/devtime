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


def test_not_applicable_when_no_billing_surface(tmp_path, monkeypatch):
    # v0.5.0: a repo with no billing code is NOT_APPLICABLE, not an ominous
    # UNKNOWN, and it says what would make the claim verifiable.
    _repo(tmp_path, {"src/util/math.ts": "export const add = (a, b) => a + b;\n"})
    _init_scan(tmp_path, monkeypatch)
    result = _verify()
    assert result.status == ver.NOT_APPLICABLE
    assert any("would become verifiable" in m.lower() for m in result.missing)


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
    assert payload["schema_version"] == "2"
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


# --- jwt-authentication claim (v0.3.0) -------------------------------------------

ACCESS_JWT = """
import jwt from "jsonwebtoken";
export function login(user) {
  return jwt.sign({ sub: user.id }, process.env.SECRET, { expiresIn: "1h" });
}
"""

INVITE_JWT = """
import jwt from "jsonwebtoken";
export function createInviteToken(email) {
  // invitation link token for email verification
  return jwt.sign({ email, invite: true }, process.env.SECRET);
}
"""

JWT_DOC = "# Authentication\n\n## Use JWT for API authentication\n\nWe sign JWTs.\n"


def test_jwt_supported_with_access_usage(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/auth/login.ts": ACCESS_JWT})
    _init_scan(tmp_path, monkeypatch)
    result = _verify("jwt-authentication")
    assert result.status == ver.SUPPORTED


def test_jwt_docs_only_is_weak_not_contradicted(tmp_path, monkeypatch):
    # Absence of usage is missing evidence, never a contradiction.
    _repo(tmp_path, {"docs/auth.md": JWT_DOC})
    _init_scan(tmp_path, monkeypatch)
    result = _verify("jwt-authentication")
    assert result.status == ver.WEAK
    assert not result.contradictions


def test_jwt_docs_vs_invitation_only_is_contradicted(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "docs/auth.md": JWT_DOC,
        "src/tokens/invite.ts": INVITE_JWT,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("jwt-authentication")
    assert result.status == ver.CONTRADICTED
    c = result.contradictions[0]
    assert c.claimed_side and c.observed_side
    assert "invitation" in c.observed_side.lower()


def test_jwt_not_applicable_without_any_jwt_surface(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/util/math.ts": "export const add = (a, b) => a + b;\n"})
    _init_scan(tmp_path, monkeypatch)
    result = _verify("jwt-authentication")
    assert result.status == ver.NOT_APPLICABLE


def test_signal_metadata_survives_persistence(tmp_path, monkeypatch):
    # Regression: metadata_json was hardcoded to '{}' at INSERT, silently
    # dropping the JWT purpose classification the verifier reads back.
    _repo(tmp_path, {"src/auth/login.ts": ACCESS_JWT})
    _init_scan(tmp_path, monkeypatch)
    conn = connection.connect()
    try:
        row = conn.execute(
            "SELECT metadata_json FROM signals WHERE kind='token_usage' LIMIT 1"
        ).fetchone()
        assert row is not None
        assert json.loads(row["metadata_json"]).get("purpose") == "access"
    finally:
        conn.close()


def test_verify_all_returns_both_claims(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/auth/login.ts": ACCESS_JWT})
    _init_scan(tmp_path, monkeypatch)
    result = runner.invoke(app, ["verify", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    ids = {r["claim_id"] for r in payload["results"]}
    assert ids == set(ver.BUILTIN_CLAIMS)


# --- diff-aware claim impact (v0.4.0) ---------------------------------------------

def test_claims_affected_by_changed_evidence(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/billing/stripe-webhook.ts": STRIPE_HANDLER})
    _init_scan(tmp_path, monkeypatch)
    conn = connection.connect()
    try:
        ver.save_verification(conn, ver.verify_claim(conn, "billing-webhook-signature"))
        impact = ver.claims_affected_by_paths(conn, ["src/billing/stripe-webhook.ts"])
        assert len(impact) == 1
        item = impact[0]
        assert item["claim_id"] == "billing-webhook-signature"
        assert item["previous_status"] == ver.SUPPORTED
        assert item["changed_evidence"] == ["src/billing/stripe-webhook.ts"]
        assert "dtc verify" in item["suggested_action"]
    finally:
        conn.close()


def test_unrelated_diff_affects_no_claims(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/billing/stripe-webhook.ts": STRIPE_HANDLER})
    _init_scan(tmp_path, monkeypatch)
    conn = connection.connect()
    try:
        ver.save_verification(conn, ver.verify_claim(conn, "billing-webhook-signature"))
        impact = ver.claims_affected_by_paths(conn, ["README.md", "src/util/other.ts"])
        assert impact == []
    finally:
        conn.close()


def test_no_verifications_means_no_impact(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/billing/stripe-webhook.ts": STRIPE_HANDLER})
    _init_scan(tmp_path, monkeypatch)
    conn = connection.connect()
    try:
        impact = ver.claims_affected_by_paths(conn, ["src/billing/stripe-webhook.ts"])
        assert impact == []
    finally:
        conn.close()


# --- v0.5.0: claims that fire on ordinary repositories ---------------------------

EXPRESS_ROUTES = """
import express from "express";
import { listUsers } from "../services/users";
const router = express.Router();
router.get("/api/users", listUsers);
router.post("/api/reports", createReport);
export default router;
"""

USERS_TEST = """
import { listUsers } from "../src/routes/users-router";
import { describe, it } from "vitest";
describe("users", () => { it("lists users", () => {}); });
"""

ADMIN_ROUTES_PROTECTED = """
import express from "express";
import { requireAdmin } from "./require-admin";
const router = express.Router();
router.get("/admin/users", requireAdmin, listAdminUsers);
export default router;
"""

ADMIN_ROUTES_BARE = """
import express from "express";
const router = express.Router();
router.get("/admin/users", listAdminUsers);
export default router;
"""


def test_route_test_coverage_supported_when_all_routes_covered(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/routes/users-router.ts": EXPRESS_ROUTES,
        "tests/users.test.ts": USERS_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("route-test-coverage")
    assert result.status == ver.SUPPORTED
    assert any(" of " in w for w in result.why)  # reports the ratio


def test_route_test_coverage_weak_and_names_uncovered_routes(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/routes/users-router.ts": EXPRESS_ROUTES,
        "src/routes/billing-router.ts":
            'import express from "express";\n'
            'const router = express.Router();\n'
            'router.get("/api/invoices", listInvoices);\n',
        "tests/users.test.ts": USERS_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("route-test-coverage")
    assert result.status == ver.WEAK
    # Absence of tests is missing evidence, never a contradiction.
    assert result.contradictions == []
    assert any("invoices" in m for m in result.missing)


def test_route_test_coverage_not_applicable_without_routes(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/util/math.ts": "export const add = (a, b) => a + b;\n"})
    _init_scan(tmp_path, monkeypatch)
    result = _verify("route-test-coverage")
    assert result.status == ver.NOT_APPLICABLE


def test_route_test_coverage_ignores_e2e_specs(tmp_path, monkeypatch):
    # E2E specs match by accident, so they must not count as route attribution.
    _repo(tmp_path, {
        "src/routes/users-router.ts": EXPRESS_ROUTES,
        "tests-e2e/users.e2e.spec.ts": USERS_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("route-test-coverage")
    assert result.status == ver.WEAK


def test_admin_authorization_supported_with_authz_evidence(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/routes/admin-router.ts": ADMIN_ROUTES_PROTECTED,
        "src/routes/require-admin.ts":
            "export function requireAdmin(req, res, next) { return next(); }\n",
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("admin-authorization")
    assert result.status == ver.SUPPORTED


def test_admin_authorization_missing_authz_is_weak_never_contradicted(
    tmp_path, monkeypatch
):
    # The honesty rule for this claim: authorization can be applied globally or
    # by a wrapper the scanner cannot see, so a missing signal is WEAK.
    _repo(tmp_path, {"src/routes/admin-router.ts": ADMIN_ROUTES_BARE})
    _init_scan(tmp_path, monkeypatch)
    result = _verify("admin-authorization")
    assert result.status == ver.WEAK
    assert result.contradictions == []
    assert any("not proof" in w.lower() for w in result.why)
    # The safety-critical disclosures: guards DevTime cannot resolve are named,
    # and WEAK is never presented as proof that a route is unprotected.
    blob = " ".join(result.limitations).lower()
    assert "server-wide" in blob or "router mount" in blob
    assert "never proof" in blob or "not proof" in blob


def test_admin_authorization_not_applicable_without_admin_routes(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/routes/users-router.ts": EXPRESS_ROUTES})
    _init_scan(tmp_path, monkeypatch)
    result = _verify("admin-authorization")
    assert result.status == ver.NOT_APPLICABLE


# --- verify_all and the report card ----------------------------------------------

def test_verify_all_returns_every_claim_contradictions_first(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "apps/web/pages/api/stripe/webhook.ts": STUB_HANDLER,
        "package.json": PACKAGE_WITH_STRIPE,
        "src/routes/users-router.ts": EXPRESS_ROUTES,
    })
    _init_scan(tmp_path, monkeypatch)
    conn = connection.connect()
    try:
        results = ver.verify_all(conn)
    finally:
        conn.close()
    assert {r.claim_slug for r in results} == set(ver.BUILTIN_CLAIMS)
    assert results[0].status == ver.CONTRADICTED  # most important finding first
    # NOT_APPLICABLE results sort last.
    assert results[-1].status == ver.NOT_APPLICABLE


def test_not_applicable_results_are_not_saved(tmp_path, monkeypatch):
    # Storing a claim that does not apply would pollute freshness and diff impact.
    _repo(tmp_path, {"src/util/math.ts": "export const add = (a, b) => a + b;\n"})
    _init_scan(tmp_path, monkeypatch)
    assert runner.invoke(app, ["verify"]).exit_code == 0
    conn = connection.connect()
    try:
        ver.ensure_verifications_table(conn)
        rows = conn.execute(
            "SELECT status FROM verifications WHERE status = ?", (ver.NOT_APPLICABLE,)
        ).fetchall()
        assert rows == []
    finally:
        conn.close()


def test_cli_report_never_dead_ends(tmp_path, monkeypatch):
    # A repository where nothing applies must still explain itself.
    _repo(tmp_path, {"src/util/math.ts": "export const add = (a, b) => a + b;\n"})
    _init_scan(tmp_path, monkeypatch)
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 0
    out = result.stdout
    assert "No built-in claim applies" in out
    assert "become verifiable" in out
    assert "coverage limit" in out
    assert "github.com/Shakargy/devtime/issues" in out


def test_cli_report_lists_not_applicable_reasons(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/routes/users-router.ts": EXPRESS_ROUTES,
        "tests/users.test.ts": USERS_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 0
    assert "Not applicable to this repository" in result.stdout
    assert "billing-webhook-signature" in result.stdout


def test_cli_list_marks_applicability(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/routes/users-router.ts": EXPRESS_ROUTES,
        "tests/users.test.ts": USERS_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    result = runner.invoke(app, ["verify", "--list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "2"
    by_id = {c["claim_id"]: c for c in payload["claims"]}
    assert by_id["route-test-coverage"]["applies_here"] is True
    assert by_id["billing-webhook-signature"]["applies_here"] is False


def test_single_claim_that_does_not_apply_still_explains_itself(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/util/math.ts": "export const add = (a, b) => a + b;\n"})
    _init_scan(tmp_path, monkeypatch)
    result = runner.invoke(app, ["verify", "billing-webhook-signature"])
    assert result.exit_code == 0
    assert "NOT_APPLICABLE" in result.stdout
    assert "does not apply" in result.stdout


# --- v0.5.1: false-SUPPORTED regressions -----------------------------------------
#
# Each of these produced SUPPORTED in v0.5.0 with no justifying evidence. They
# are the reason this release exists; none of them may ever pass again.

ADMIN_NO_GUARD = """
import express from "express";
const router = express.Router();
router.get("/admin/permissions", listPermissions);
export default router;
"""

ADMIN_AUTHN_ONLY = """
import express from "express";
import { requireAuth } from "./auth";
const router = express.Router();
router.get("/admin/settings", requireAuth, editSettings);
"""

ADMIN_FAKE_GUARDS = """
import express from "express";
import { requireAdmin } from "./auth";
const router = express.Router();
// TODO: add requireAdmin here
const note = "requireAdmin hasRole";
router.get("/admin/a", handler);
"""

ADMIN_GUARDED = """
import express from "express";
import { requireAdmin } from "./auth";
const router = express.Router();
router.get("/admin/a", requireAdmin, handler);
"""

ADMIN_MIXED = """
import express from "express";
import { requireAdmin } from "./auth";
const router = express.Router();
router.get("/admin/users", requireAdmin, listUsers);
router.get("/admin/logs", readLogs);
"""


def test_admin_filename_is_not_authorization_evidence(tmp_path, monkeypatch):
    # v0.5.0 bug: the evaluator matched combined text that included the FILE
    # PATH, so src/admin/permissions.ts satisfied the "permission" token and
    # reported "1 of 1 administrative route(s) show an authorization check"
    # on a repository containing no guard at all.
    _repo(tmp_path, {"src/admin/permissions.ts": ADMIN_NO_GUARD})
    _init_scan(tmp_path, monkeypatch)
    result = _verify("admin-authorization")
    assert result.status == ver.WEAK
    assert "0 of 1" in " ".join(result.why)


def test_admin_authentication_alone_is_not_authorization(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/admin/settings.ts": ADMIN_AUTHN_ONLY})
    _init_scan(tmp_path, monkeypatch)
    result = _verify("admin-authorization")
    assert result.status == ver.WEAK
    assert any("role or permission" in w.lower() for w in result.why)


def test_admin_commented_and_unused_guards_are_not_evidence(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/admin/a.ts": ADMIN_FAKE_GUARDS})
    _init_scan(tmp_path, monkeypatch)
    assert _verify("admin-authorization").status == ver.WEAK


def test_admin_guard_at_call_site_is_supported(tmp_path, monkeypatch):
    # The legitimate pattern must keep working, or the fix is useless.
    _repo(tmp_path, {"src/admin/a.ts": ADMIN_GUARDED})
    _init_scan(tmp_path, monkeypatch)
    assert _verify("admin-authorization").status == ver.SUPPORTED


def test_admin_two_routes_one_guarded_is_not_supported(tmp_path, monkeypatch):
    # A guard on one route does not protect its neighbour in the same file.
    _repo(tmp_path, {"src/admin/a.ts": ADMIN_MIXED})
    _init_scan(tmp_path, monkeypatch)
    result = _verify("admin-authorization")
    assert result.status == ver.WEAK
    assert "1 of 2" in " ".join(result.why)
    assert any("/admin/logs" in m for m in result.missing)


ROUTE_USERS = """
import express from "express";
const router = express.Router();
router.get("/users", listUsers);
"""

UNRELATED_USERS_TEST = """
import { describe, it } from "vitest";
describe("display", () => { it("formats users display names", () => {}); });
"""

SUPERUSERS_TEST = """
import { listSuperusers } from "../src/routes/superusers";
import { describe, it } from "vitest";
describe("superusers", () => { it("lists", () => {}); });
"""

IMPORTING_USERS_TEST = """
import router from "../src/routes/users";
import { describe, it } from "vitest";
describe("users", () => { it("lists", () => {}); });
"""


def test_name_similarity_alone_does_not_associate_a_test(tmp_path, monkeypatch):
    # v0.5.0 bug: a test merely sharing the word "users" produced SUPPORTED.
    _repo(tmp_path, {
        "src/routes/users.ts": ROUTE_USERS,
        "tests/display.test.ts": UNRELATED_USERS_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("route-test-coverage")
    assert result.status == ver.WEAK
    assert "0 of 1" in " ".join(result.why)
    # The similarity may be offered as a suggestion, but never as support.
    assert any("suggestion" in w.lower() for w in result.why)


def test_import_stem_collision_does_not_associate(tmp_path, monkeypatch):
    # Importing "superusers" is not importing "users".
    _repo(tmp_path, {
        "src/routes/users.ts": ROUTE_USERS,
        "tests/superusers.test.ts": SUPERUSERS_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    assert _verify("route-test-coverage").status == ver.WEAK


def test_importing_test_associates_and_never_claims_execution(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/routes/users.ts": ROUTE_USERS,
        "tests/users.test.ts": IMPORTING_USERS_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("route-test-coverage")
    assert result.status == ver.SUPPORTED
    blob = (" ".join(result.why) + " " + " ".join(result.limitations)).lower()
    assert "not execution coverage" in blob or "not proof the route was executed" in blob
    assert "exercised by tests" not in result.statement.lower()


WEBHOOK_ROUTE_BARE = """
import express from "express";
const router = express.Router();
router.post("/api/stripe/webhook", (req, res) => { res.json({ ok: true }); });
"""

UNUSED_SIG_HELPER = """
import Stripe from "stripe";
const stripe = new Stripe(process.env.KEY);
export function verifyIt(body, sig, secret) {
  return stripe.webhooks.constructEvent(body, sig, secret);
}
"""

WEBHOOK_ROUTE_VERIFIED = """
import express from "express";
import Stripe from "stripe";
const stripe = new Stripe(process.env.KEY);
const router = express.Router();
router.post("/api/stripe/webhook", (req, res) => {
  const event = stripe.webhooks.constructEvent(req.body, sig, secret);
  res.json({ received: true });
});
"""

WEBHOOK_ROUTE_PAYPAL_BARE = """
import express from "express";
const router = express.Router();
router.post("/api/paypal/webhook", (req, res) => { res.json({ ok: true }); });
"""


def test_unconnected_signature_helper_does_not_support_handler(tmp_path, monkeypatch):
    # v0.5.0 bug: a verification helper anywhere in the repo - even one nothing
    # calls - reported SUPPORTED for every billing webhook endpoint.
    _repo(tmp_path, {
        "src/billing/webhook-route.ts": WEBHOOK_ROUTE_BARE,
        "src/util/sig-helper.ts": UNUSED_SIG_HELPER,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("billing-webhook-signature")
    assert result.status == ver.WEAK
    assert "0 of 1" in " ".join(result.why)


def test_handler_local_verification_is_supported(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/billing/stripe-webhook.ts": WEBHOOK_ROUTE_VERIFIED})
    _init_scan(tmp_path, monkeypatch)
    assert _verify("billing-webhook-signature").status == ver.SUPPORTED


def test_partial_webhook_coverage_is_reported_per_handler(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/billing/stripe-webhook.ts": WEBHOOK_ROUTE_VERIFIED,
        "src/billing/paypal-webhook.ts": WEBHOOK_ROUTE_PAYPAL_BARE,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("billing-webhook-signature")
    assert result.status == ver.WEAK
    assert "1 of 2" in " ".join(result.why)
    assert any("paypal" in m.lower() for m in result.missing)


def test_signature_call_in_test_file_does_not_protect_production(tmp_path, monkeypatch):
    # A verification call inside a test fixture is not handler protection.
    _repo(tmp_path, {
        "src/billing/webhook-route.ts": WEBHOOK_ROUTE_BARE,
        "tests/webhook.test.ts": UNUSED_SIG_HELPER,
    })
    _init_scan(tmp_path, monkeypatch)
    assert _verify("billing-webhook-signature").status == ver.WEAK


def test_routes_in_tests_and_examples_are_not_application_surface(tmp_path, monkeypatch):
    # v0.5.1: express reported "142 routes", nearly all of them defined inside
    # its own test/ and examples/ directories. Those are fixtures, not the
    # application's HTTP surface, and counting them as untested is noise.
    _repo(tmp_path, {
        "test/acceptance/auth.js":
            'const express = require("express");\n'
            "const app = express();\n"
            'app.get("/fixture-route", handler);\n',
        "examples/hello/index.js":
            'const express = require("express");\n'
            "const app = express();\n"
            'app.get("/example-route", handler);\n',
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("route-test-coverage")
    assert result.status == ver.NOT_APPLICABLE
    assert any("test, example" in w for w in result.why)


def test_application_routes_are_still_counted_alongside_fixtures(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/routes/users.ts": ROUTE_USERS,
        "test/acceptance/auth.js":
            'const express = require("express");\n'
            "const app = express();\n"
            'app.get("/fixture-route", handler);\n',
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("route-test-coverage")
    # Only the application route is in the inventory.
    assert "of 1 routes" in " ".join(result.why)


# --- v0.6.0: complete freshness dependencies -------------------------------------
#
# v0.5.x stored only the bounded evidence shown to the user, so results stayed
# FRESH after the files that justified them changed or disappeared.

ROUTE_USERS_V6 = """
import express from "express";
const router = express.Router();
router.get("/users", listUsers);
"""

TEST_IMPORTS_USERS = """
import router from "../src/routes/users";
import { describe, it } from "vitest";
describe("users", () => { it("lists", () => {}); });
"""

WEBHOOK_VERIFIED_V6 = """
import express from "express";
import Stripe from "stripe";
const stripe = new Stripe(process.env.KEY);
const router = express.Router();
router.post("/api/stripe/webhook", (req, res) => {
  stripe.webhooks.constructEvent(req.body, sig, secret);
});
"""


def _freshness(slug):
    conn = connection.connect()
    try:
        return ver.freshness_for(conn, slug)
    finally:
        conn.close()


def _record(slug):
    conn = connection.connect()
    try:
        ver.save_verification(conn, ver.verify_claim(conn, slug))
    finally:
        conn.close()


def test_editing_the_justifying_test_marks_the_claim_stale(tmp_path, monkeypatch):
    # v0.5.x bug: only route files were fingerprinted, so changing the test that
    # established the association left the result reported as FRESH.
    _repo(tmp_path, {
        "src/routes/users.ts": ROUTE_USERS_V6,
        "tests/users.test.ts": TEST_IMPORTS_USERS,
    })
    _init_scan(tmp_path, monkeypatch)
    _record("route-test-coverage")
    assert _freshness("route-test-coverage")[0] == ver.FRESH

    (tmp_path / "tests/users.test.ts").write_text(
        TEST_IMPORTS_USERS.replace("lists", "renamed"), encoding="utf-8"
    )
    assert runner.invoke(app, ["scan", "--refresh"]).exit_code == 0

    freshness, changed = _freshness("route-test-coverage")
    assert freshness == ver.STALE
    assert any("users.test.ts" in p for p in changed)


def test_deleting_an_evidence_file_marks_the_claim_stale(tmp_path, monkeypatch):
    # v0.5.x bug: the old files row survived, so the hash still matched and a
    # deleted dependency looked current.
    _repo(tmp_path, {"src/billing/wh.ts": WEBHOOK_VERIFIED_V6})
    _init_scan(tmp_path, monkeypatch)
    _record("billing-webhook-signature")
    assert _freshness("billing-webhook-signature")[0] == ver.FRESH

    (tmp_path / "src/billing/wh.ts").unlink()
    assert runner.invoke(app, ["scan", "--refresh"]).exit_code == 0

    freshness, changed = _freshness("billing-webhook-signature")
    assert freshness == ver.STALE
    assert any("wh.ts" in p for p in changed)


def test_a_new_route_invalidates_a_set_level_claim(tmp_path, monkeypatch):
    # A claim about "all routes" depends on the route inventory, not only on the
    # files that existed when it was recorded.
    _repo(tmp_path, {
        "src/routes/users.ts": ROUTE_USERS_V6,
        "tests/users.test.ts": TEST_IMPORTS_USERS,
    })
    _init_scan(tmp_path, monkeypatch)
    _record("route-test-coverage")
    assert _freshness("route-test-coverage")[0] == ver.FRESH

    _repo(tmp_path, {
        "src/routes/orders.ts":
            'import express from "express";\n'
            "const router = express.Router();\n"
            'router.post("/orders", createOrder);\n',
    })
    assert runner.invoke(app, ["scan", "--refresh"]).exit_code == 0
    assert _freshness("route-test-coverage")[0] == ver.STALE


def test_unrelated_change_still_does_not_invalidate(tmp_path, monkeypatch):
    # Precision matters as much as completeness: staleness that fires on every
    # commit teaches people to ignore staleness.
    _repo(tmp_path, {
        "src/routes/users.ts": ROUTE_USERS_V6,
        "tests/users.test.ts": TEST_IMPORTS_USERS,
        "NOTES.md": "# notes\n",
    })
    _init_scan(tmp_path, monkeypatch)
    _record("route-test-coverage")

    (tmp_path / "NOTES.md").write_text("# notes changed\n", encoding="utf-8")
    assert runner.invoke(app, ["scan", "--refresh"]).exit_code == 0
    assert _freshness("route-test-coverage")[0] == ver.FRESH


def test_dependencies_exceed_displayed_evidence(tmp_path, monkeypatch):
    # The dependency set must include the test files, which are not part of the
    # bounded evidence list shown to a user.
    _repo(tmp_path, {
        "src/routes/users.ts": ROUTE_USERS_V6,
        "tests/users.test.ts": TEST_IMPORTS_USERS,
    })
    _init_scan(tmp_path, monkeypatch)
    conn = connection.connect()
    try:
        result = ver.verify_claim(conn, "route-test-coverage")
    finally:
        conn.close()
    assert any("users.test.ts" in d for d in result.dependencies)
    assert result.inventory  # a set-level claim records its inventory


def test_verification_with_no_recorded_dependencies_is_not_fresh(tmp_path, monkeypatch):
    # A result that recorded nothing cannot justify a FRESH label.
    _repo(tmp_path, {"src/routes/users.ts": ROUTE_USERS_V6})
    _init_scan(tmp_path, monkeypatch)
    conn = connection.connect()
    try:
        ver.ensure_verifications_table(conn)
        conn.execute(
            "INSERT INTO verifications(id, repository_id, claim_slug, status, "
            "scan_id, result_json, evidence_fingerprints_json, engine_version, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("ver-empty", "r", "route-test-coverage", ver.SUPPORTED, "s",
             "{}", "[]", "0.0.0", "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()
    assert _freshness("route-test-coverage")[0] == ver.NEEDS_VERIFICATION


def test_verifications_table_migrates_idempotently(tmp_path, monkeypatch):
    # Databases created before v0.6.0 lack inventory_fingerprint.
    _repo(tmp_path, {"src/routes/users.ts": ROUTE_USERS_V6})
    _init_scan(tmp_path, monkeypatch)
    conn = connection.connect()
    try:
        conn.execute("DROP TABLE IF EXISTS verifications")
        conn.execute(
            "CREATE TABLE verifications (id TEXT PRIMARY KEY, repository_id TEXT "
            "NOT NULL, claim_slug TEXT NOT NULL, status TEXT NOT NULL, scan_id "
            "TEXT, result_json TEXT NOT NULL, evidence_fingerprints_json TEXT "
            "NOT NULL DEFAULT '[]', engine_version TEXT NOT NULL, created_at "
            "TEXT NOT NULL)"
        )
        conn.commit()
        ver.ensure_verifications_table(conn)
        ver.ensure_verifications_table(conn)  # idempotent
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(verifications)")}
        assert "inventory_fingerprint" in cols
        # And it still accepts writes.
        ver.save_verification(conn, ver.verify_claim(conn, "route-test-coverage"))
    finally:
        conn.close()


# --- v0.6.0: scan staleness is explicit ------------------------------------------

def test_scan_state_reports_working_tree_drift(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/billing/wh.ts": WEBHOOK_VERIFIED_V6})
    _init_scan(tmp_path, monkeypatch)
    conn = connection.connect()
    try:
        assert ver.scan_state(conn)["working_tree"] == "matches_scan"
    finally:
        conn.close()

    (tmp_path / "src/billing/wh.ts").write_text(
        WEBHOOK_VERIFIED_V6 + "\n// edited\n", encoding="utf-8"
    )
    conn = connection.connect()
    try:
        state = ver.scan_state(conn)
        assert state["working_tree"] == "changed_since_scan"
        assert any("wh.ts" in p for p in state["changed_paths"])
        assert state["scan_id"]
    finally:
        conn.close()


def test_cli_warns_when_results_come_from_a_stale_scan(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/billing/wh.ts": WEBHOOK_VERIFIED_V6})
    _init_scan(tmp_path, monkeypatch)
    (tmp_path / "src/billing/wh.ts").write_text(
        WEBHOOK_VERIFIED_V6 + "\n// edited after the scan\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["verify", "billing-webhook-signature"])
    assert result.exit_code == 0
    # Terminal wrapping is not behavior: compare on normalized whitespace.
    out = " ".join(result.stdout.split())
    assert "no longer matches your working tree" in out
    assert "dtc scan" in out
    assert "wh.ts" in out


def test_json_output_carries_the_evidence_snapshot(tmp_path, monkeypatch):
    _repo(tmp_path, {"src/billing/wh.ts": WEBHOOK_VERIFIED_V6})
    _init_scan(tmp_path, monkeypatch)
    result = runner.invoke(app, ["verify", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    snap = payload["evidence_snapshot"]
    assert snap["scan_id"]
    assert snap["working_tree"] in ("matches_scan", "partially_checked")
    assert "dependency_count" in payload["results"][0]


def test_mcp_verify_claim_discloses_stale_snapshot(tmp_path, monkeypatch):
    from devtime.mcp.transport import build_server

    _repo(tmp_path, {"src/billing/wh.ts": WEBHOOK_VERIFIED_V6})
    _init_scan(tmp_path, monkeypatch)
    (tmp_path / "src/billing/wh.ts").write_text(
        WEBHOOK_VERIFIED_V6 + "\n// edited\n", encoding="utf-8"
    )
    server = build_server()
    out = str(asyncio.run(
        server.call_tool("verify_claim", {"claim_id": "billing-webhook-signature"})
    ))
    assert "staleness_warning" in out
    assert "dtc scan" in out


# --- v0.6.0: request-based association -------------------------------------------
#
# v0.5.1 removed the false positives but could only see imports, so it abstained
# on the common real pattern: a test that drives a running app by URL.

SUPERTEST_TEST = """
import request from "supertest";
import { app } from "../src/app";
describe("api", () => {
  it("returns users", async () => { await request(app).get("/users").expect(200); });
});
"""

TWO_METHOD_ROUTES = """
import express from "express";
const router = express.Router();
router.get("/users", listUsers);
router.post("/users", createUser);
"""

FASTAPI_ROUTE = """
from fastapi import APIRouter
router = APIRouter()

@router.get("/items")
def list_items():
    return []
"""

FASTAPI_CLIENT_TEST = """
from fastapi.testclient import TestClient

def test_list_items():
    r = client.get("/items")
    assert r.status_code == 200
"""


def test_supertest_request_associates_the_exact_route(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/routes/users.ts": TWO_METHOD_ROUTES,
        "tests/api.test.ts": SUPERTEST_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("route-test-coverage")
    # GET is requested by the test; POST on the same path is not.
    assert result.status == ver.WEAK
    assert "1 of 2" in " ".join(result.why)
    assert any("POST /users" in m for m in result.missing)
    assert any("requests" in e.observation for e in result.supporting)


def test_fastapi_testclient_request_associates(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "app/api/items.py": FASTAPI_ROUTE,
        "tests/test_items.py": FASTAPI_CLIENT_TEST,
    })
    _init_scan(tmp_path, monkeypatch)
    assert _verify("route-test-coverage").status == ver.SUPPORTED


def test_non_url_get_calls_are_not_requests(tmp_path, monkeypatch):
    # `map.get("key")` is not an HTTP request: only literals starting with "/"
    # are treated as route paths.
    _repo(tmp_path, {
        "src/routes/users.ts": ROUTE_USERS_V6,
        "tests/util.test.ts":
            'import { describe, it } from "vitest";\n'
            'describe("cache", () => { it("reads", () => { cache.get("users"); }); });\n',
    })
    _init_scan(tmp_path, monkeypatch)
    assert _verify("route-test-coverage").status == ver.WEAK


def test_request_to_a_different_path_does_not_associate(tmp_path, monkeypatch):
    _repo(tmp_path, {
        "src/routes/users.ts": ROUTE_USERS_V6,
        "tests/api.test.ts":
            'import request from "supertest";\n'
            'describe("api", () => { it("x", async () => '
            '{ await request(app).get("/orders"); }); });\n',
    })
    _init_scan(tmp_path, monkeypatch)
    assert _verify("route-test-coverage").status == ver.WEAK


def test_prefix_relative_routes_are_unresolved_not_untested(tmp_path, monkeypatch):
    # A route declared as "/" or "/{id}" on a router that is mounted elsewhere
    # has no knowable full URL. Reporting it as "no test found" would blame the
    # repository for a gap in DevTime's analysis.
    _repo(tmp_path, {
        "app/api/items.py":
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n\n"
            '@router.get("/")\n'
            "def list_items():\n"
            "    return []\n",
    })
    _init_scan(tmp_path, monkeypatch)
    result = _verify("route-test-coverage")
    assert result.status == ver.WEAK
    blob = " ".join(result.why).lower()
    assert "mount prefix" in blob
    assert "not evidence that they lack tests" in blob
