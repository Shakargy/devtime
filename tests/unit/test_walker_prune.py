from pathlib import Path

from devtime.scanner import ignore as ignore_mod
from devtime.scanner.file_walker import walk_repository


def _build_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.ts").write_text("export const x = 1;", encoding="utf-8")

    # Directories that must be pruned, each holding a file that must never be yielded.
    for d in ("node_modules", ".next", ".devtime", ".git", "dist", "build", "__pycache__"):
        (root / d).mkdir(parents=True, exist_ok=True)
        (root / d / "junk.ts").write_text("junk", encoding="utf-8")

    # A secret file under an ignored directory must never be visited.
    (root / "node_modules" / ".env").write_text("SECRET=leak_me", encoding="utf-8")
    # A top-level secret must also be skipped by hard-deny.
    (root / ".env").write_text("TOP_SECRET=leak_me_too", encoding="utf-8")
    return root


def _walk(root: Path):
    matcher = ignore_mod.build_matcher(root, respect_gitignore=False, respect_devtimeignore=False)
    return list(walk_repository(root, matcher, max_size_bytes=512 * 1024))


def test_ignored_directories_are_pruned(tmp_path):
    root = _build_repo(tmp_path)
    rels = {wf.rel_path for wf in _walk(root)}
    assert "src/app.ts" in rels
    for pruned in ("node_modules", ".next", ".devtime", ".git", "dist", "build", "__pycache__"):
        assert not any(r.startswith(pruned + "/") for r in rels), f"{pruned} was traversed"


def test_secrets_under_ignored_paths_never_yielded(tmp_path):
    root = _build_repo(tmp_path)
    rels = {wf.rel_path for wf in _walk(root)}
    assert "node_modules/.env" not in rels
    assert ".env" not in rels
    assert not any(r.endswith(".env") for r in rels)


def test_gitignore_dir_pruned(tmp_path):
    root = tmp_path / "repo"
    (root / "keep").mkdir(parents=True)
    (root / "keep" / "a.ts").write_text("a", encoding="utf-8")
    (root / "generated").mkdir()
    (root / "generated" / "b.ts").write_text("b", encoding="utf-8")
    (root / ".gitignore").write_text("generated/\n", encoding="utf-8")

    matcher = ignore_mod.build_matcher(root, respect_gitignore=True, respect_devtimeignore=False)
    rels = {wf.rel_path for wf in walk_repository(root, matcher, 512 * 1024)}
    assert "keep/a.ts" in rels
    assert not any(r.startswith("generated/") for r in rels)
