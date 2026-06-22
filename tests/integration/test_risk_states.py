from conftest import ROOT
from devtime.fixtures.runner import run_devtime_scan
from devtime.intelligence.risk import parse_unified_diff, review_diff, review_failed

DEMO = ROOT / "examples" / "demo-saas"


def _intel():
    return run_devtime_scan(DEMO)


def _diff(path: str, *added: str, removed: list[str] | None = None) -> str:
    lines = [f"--- a/{path}", f"+++ b/{path}", "@@"]
    for r in removed or []:
        lines.append(f"-{r}")
    for a in added:
        lines.append(f"+{a}")
    return "\n".join(lines) + "\n"


def test_review_failed_is_its_own_state():
    r = review_failed("Git could not read the diff")
    assert r.state == "review_failed"
    assert "Git could not read" in r.reason


def test_empty_diff_is_no_findings():
    r = review_diff(parse_unified_diff(""), _intel())
    assert r.state == "no_findings"


def test_comment_only_retry_does_not_trigger_behavior_risk():
    diff = _diff("src/billing/stripe-webhook.ts",
                 "    // TODO: add retry and duplicate-delivery handling later")
    r = review_diff(parse_unified_diff(diff), _intel())
    assert all(f.type != "missing_test_update" for f in r.findings)
    # Known billing file changed by comment only, no rule fired -> unsupported_change_class.
    assert r.state in ("unsupported_change_class", "no_findings")


def test_unsupported_change_class_for_known_auth_file():
    diff = _diff("src/auth/tokens.ts", "  const TTL_SECONDS = 1800;")
    r = review_diff(parse_unified_diff(diff), _intel())
    assert r.state == "unsupported_change_class"
    assert "Authentication" in r.affected_concepts


def test_background_job_batch_size_is_unsupported_change_class():
    diff = _diff("src/jobs/queues.ts", "const BATCH_SIZE = 500;")
    r = review_diff(parse_unified_diff(diff), _intel())
    assert r.state == "unsupported_change_class"
    assert "Background Jobs" in r.affected_concepts


def test_jwt_algorithm_hs256_to_none_is_high():
    diff = _diff("src/auth/tokens.ts",
                 "const ALGORITHM = 'none';",
                 removed=["const ALGORITHM = 'HS256';"])
    r = review_diff(parse_unified_diff(diff), _intel())
    assert r.state == "finding"
    algo = [f for f in r.findings if f.type == "jwt_algorithm_weakening"]
    assert algo and algo[0].severity == "high"


def test_jwt_asymmetric_es256_to_none_is_high():
    diff = _diff("src/auth/middleware.ts",
                 "JWT_ASYMMETRIC_ALGORITHM = 'none'",
                 removed=["JWT_ASYMMETRIC_ALGORITHM = 'ES256'"])
    r = review_diff(parse_unified_diff(diff), _intel())
    algo = [f for f in r.findings if f.type == "jwt_algorithm_weakening"]
    assert algo and algo[0].severity == "high"


def test_jwt_algorithm_line_without_jwt_keyword_still_flagged():
    # The changed line itself contains neither 'jwt' nor 'token'.
    diff = _diff("src/auth/login.ts",
                 "ALGORITHM = 'none'",
                 removed=["ALGORITHM = 'HS256'"])
    r = review_diff(parse_unified_diff(diff), _intel())
    assert any(f.type == "jwt_algorithm_weakening" for f in r.findings)


def test_safe_comment_mentioning_jwt_algorithm_does_not_flag():
    diff = _diff("src/auth/tokens.ts",
                 "  // we should review the jwt signing algorithm someday")
    r = review_diff(parse_unified_diff(diff), _intel())
    assert all(f.type != "jwt_algorithm_weakening" for f in r.findings)
