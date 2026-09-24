"""End-to-end tests for `dtc review` against real git repositories (v0.7.0).

Every test builds a small repository with real commits, so the full path is
exercised: git refs -> merge base -> snapshot extraction -> scan -> verify ->
transitions -> CLI output and exit code.
"""

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devtime.cli import app
from devtime.review_flow import run_review
from devtime.snapshots import review_workspace

runner = CliRunner()

GUARDED = (
    'import express from "express";\n'
    'import { requireAdmin } from "../auth";\n'
    "const router = express.Router();\n"
    'router.get("/admin/users", requireAdmin, listUsers);\n'
)
GUARDED_PLUS_BARE = GUARDED + 'router.get("/admin/export", exportAll);\n'
UNGUARDED = (
    'import express from "express";\n'
    "const router = express.Router();\n"
    'router.get("/admin/users", listUsers);\n'
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "core.autocrlf", "false")
    _write(r, "src/admin/panel.ts", GUARDED)
    _commit(r, "base")
    return r


def _branch(repo: Path, name: str = "feature") -> None:
    _git(repo, "checkout", "-q", "-b", name)


# --- the core workflow ----------------------------------------------------------

def test_review_reports_a_regression_introduced_by_the_change(repo, monkeypatch):
    _branch(repo)
    _write(repo, "src/admin/panel.ts", GUARDED_PLUS_BARE)
    _commit(repo, "add an unguarded admin route")

    report = run_review(repo, "main")

    assert report["status"] == "completed"
    assert report["comparison"] == "merge-base..head"
    regressions = [t for t in report["transitions"] if t["kind"] == "regression"]
    assert [t["claim_id"] for t in regressions] == ["admin-authorization"]
    t = regressions[0]
    assert (t["base_status"], t["head_status"]) == ("SUPPORTED", "WEAK")
    assert t["changed_evidence"] == ["src/admin/panel.ts"]
    assert any("/admin/export" in m for m in t["head_missing_evidence"])


def test_review_does_not_touch_the_users_repository(repo):
    _branch(repo)
    _write(repo, "src/admin/panel.ts", GUARDED_PLUS_BARE)
    _commit(repo, "change")
    before_status = _git(repo, "status", "--porcelain")
    before_worktrees = _git(repo, "worktree", "list")

    run_review(repo, "main")

    assert not (repo / ".devtime").exists()
    assert _git(repo, "status", "--porcelain") == before_status
    assert _git(repo, "worktree", "list") == before_worktrees
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "feature"


def test_review_workspace_is_removed_afterwards():
    with review_workspace() as ws:
        created = ws
        (ws / "marker").write_text("x")
    assert not created.exists()


# --- comparison semantics -------------------------------------------------------

def test_changes_on_the_base_branch_are_not_attributed_to_the_head(repo):
    # merge-base..head: a guard removed on main AFTER the feature branched is not
    # something the feature did, so it must not show up as the feature's
    # regression.
    _branch(repo)
    _write(repo, "README.md", "# feature docs\n")
    _commit(repo, "feature commit")
    _git(repo, "checkout", "-q", "main")
    _write(repo, "src/admin/panel.ts", UNGUARDED)
    _commit(repo, "main drops the guard")
    _git(repo, "checkout", "-q", "feature")

    report = run_review(repo, "main")

    assert report["status"] == "completed"
    assert report["summary"]["regression"] == 0
    assert report["changed_files_total"] == 1  # only README.md


def test_multi_commit_pull_request_is_reviewed_as_one_change(repo):
    _branch(repo)
    _write(repo, "src/admin/panel.ts", GUARDED_PLUS_BARE)
    _commit(repo, "first")
    _write(repo, "src/routes/users.ts",
           'import express from "express";\nconst r = express.Router();\n'
           'r.get("/users", listUsers);\n')
    _commit(repo, "second")

    report = run_review(repo, "main")

    assert report["status"] == "completed"
    paths = {f["path"] for f in report["changed_files"]}
    assert paths == {"src/admin/panel.ts", "src/routes/users.ts"}
    assert report["summary"]["regression"] == 1


def test_identical_base_and_head_is_a_completed_empty_review(repo):
    report = run_review(repo, "main")
    assert report["status"] == "completed"
    assert report["changed_files_total"] == 0
    assert report["transitions"] == []


def test_renamed_evidence_file_is_attributed_through_both_paths(repo):
    _branch(repo)
    _git(repo, "mv", "src/admin/panel.ts", "src/admin/console.ts")
    _commit(repo, "rename")

    report = run_review(repo, "main")

    assert report["status"] == "completed"
    renamed = [f for f in report["changed_files"] if f["status"] == "R"]
    assert renamed and renamed[0]["old_path"] == "src/admin/panel.ts"
    admin = next(t for t in report["transitions"] if t["claim_id"] == "admin-authorization")
    assert admin["kind"] == "evidence_changed"
    assert set(admin["changed_evidence"]) == {"src/admin/console.ts", "src/admin/panel.ts"}


def test_deleting_the_only_admin_route_is_no_longer_applicable(repo):
    _branch(repo)
    _git(repo, "rm", "-q", "src/admin/panel.ts")
    _write(repo, "README.md", "# no admin surface now\n")
    _commit(repo, "delete")

    report = run_review(repo, "main")

    admin = next(t for t in report["transitions"] if t["claim_id"] == "admin-authorization")
    assert admin["kind"] == "no_longer_applicable"


def test_subdirectory_scope_reviews_that_subdirectory(tmp_path):
    # Regression test for a bug found while building v0.7.0: git archive is
    # cwd-relative, so archiving `commit:prefix` from inside the prefix produced
    # EMPTY snapshots and a review that looked clean.
    r = tmp_path / "mono"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    _write(r, "apps/api/src/admin/panel.ts", GUARDED)
    _write(r, "docs/README.md", "# docs\n")
    _commit(r, "base")
    _git(r, "checkout", "-q", "-b", "pr")
    _write(r, "apps/api/src/admin/panel.ts", UNGUARDED)
    _write(r, "docs/README.md", "# docs changed\n")
    _commit(r, "drop guard")

    report = run_review(r / "apps" / "api", "main")

    assert report["status"] == "completed"
    assert report["scope"] == "apps/api"
    assert report["changed_files_total"] == 1  # docs/ is outside the scope
    assert report["summary"]["regression"] == 1


# --- failures are failures ------------------------------------------------------

def test_unknown_base_ref_fails_and_never_looks_clean(repo, monkeypatch):
    monkeypatch.chdir(repo)
    result = runner.invoke(app, ["review", "--base", "origin/does-not-exist"])
    assert result.exit_code == 1
    assert "could not be completed" in result.stdout
    assert "No claim changed status" not in result.stdout

    report = run_review(repo, "origin/does-not-exist")
    assert report["status"] == "failed"
    assert report["error"]["reason"]
    assert report["transitions"] == []


def test_review_outside_a_git_repository_fails_clearly(tmp_path):
    report = run_review(tmp_path, "main")
    assert report["status"] == "failed"
    assert "git repository" in report["error"]["reason"]


# --- CLI surface ----------------------------------------------------------------

def test_cli_is_advisory_by_default_and_opt_in_policy_exits_7(repo, monkeypatch):
    _branch(repo)
    _write(repo, "src/admin/panel.ts", GUARDED_PLUS_BARE)
    _commit(repo, "regress")
    monkeypatch.chdir(repo)

    assert runner.invoke(app, ["review", "--base", "main"]).exit_code == 0
    strict = runner.invoke(app, ["review", "--base", "main", "--fail-on-regression"])
    assert strict.exit_code == 7


def test_cli_json_and_json_out(repo, monkeypatch, tmp_path):
    _branch(repo)
    _write(repo, "src/admin/panel.ts", GUARDED_PLUS_BARE)
    _commit(repo, "regress")
    monkeypatch.chdir(repo)
    out_file = tmp_path / "review.json"

    result = runner.invoke(
        app, ["review", "--base", "main", "--format", "json", "--json-out", str(out_file)]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    for key in ("schema_version", "status", "comparison", "base", "head",
                "changed_files", "summary", "transitions", "limitations", "error"):
        assert key in payload
    assert payload["base"]["merge_base"]
    assert json.loads(out_file.read_text(encoding="utf-8"))["status"] == "completed"


def test_cli_markdown_is_a_readable_summary(repo, monkeypatch):
    _branch(repo)
    _write(repo, "src/admin/panel.ts", GUARDED_PLUS_BARE)
    _commit(repo, "regress")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["review", "--base", "main", "--format", "markdown"])
    assert result.exit_code == 0
    assert "### DevTime review" in result.stdout
    assert "| Regression | `admin-authorization` | SUPPORTED | WEAK |" in result.stdout
    assert "Advisory" in result.stdout


def test_cli_warns_about_uncommitted_changes(repo, monkeypatch):
    _branch(repo)
    _write(repo, "src/admin/panel.ts", GUARDED_PLUS_BARE)
    _commit(repo, "regress")
    _write(repo, "src/admin/panel.ts", GUARDED_PLUS_BARE + "// wip\n")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["review", "--base", "main"])
    out = " ".join(result.stdout.split())
    assert "uncommitted changes" in out
    assert "not part of this review" in out
