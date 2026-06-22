import subprocess

from devtime.privacy import privacy_report


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init")
    _git(path, "config", "user.email", "t@t.dev")
    _git(path, "config", "user.name", "t")


def test_local_gitignore_ignores_devtime(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".gitignore").write_text(".devtime/\n", encoding="utf-8")
    report = privacy_report(repo)
    assert any("git-ignored" in g for g in report["good"])
    assert not any(".devtime" in w for w in report["warning"])


def test_nested_parent_gitignore_prevents_false_warning(tmp_path):
    parent = tmp_path / "parent"
    _init_repo(parent)
    (parent / ".gitignore").write_text(".devtime/\n", encoding="utf-8")
    child = parent / "packages" / "app"
    child.mkdir(parents=True)
    # Child has no .gitignore of its own; parent's rule must still count.
    report = privacy_report(child)
    assert not any(".devtime" in w for w in report["warning"]), report["warning"]


def test_no_gitignore_warns(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    report = privacy_report(repo)
    assert any(".devtime" in w for w in report["warning"])
