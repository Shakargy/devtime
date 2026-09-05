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
