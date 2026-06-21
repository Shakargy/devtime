from conftest import FIXTURES_DIR
from devtime.fixtures.runner import run_devtime_scan


def test_ignored_env_secrets_never_become_evidence():
    """Secrets in an ignored secrets file must not leak into evidence or claims."""
    repo = FIXTURES_DIR / "privacy" / "ignored-env-file" / "repo"
    intelligence = run_devtime_scan(repo)
    blob = ""
    for ci in intelligence:
        blob += " ".join(c.text for c in ci.claims)
        blob += " ".join(e.summary for e in ci.evidence)
    assert "DTFIXTURE_jwt_secret_must_not_leak" not in blob
    assert "DTFIXTURE_stripe_key_must_not_leak" not in blob
