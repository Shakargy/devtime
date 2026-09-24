"""Isolated git snapshots for base/head review (v0.7.0).

A review compares claims at two commits. Both are materialized with
`git archive` into a temporary directory created by DevTime, scanned there with
their own local memory, and removed afterwards. Nothing in the user's working
tree, index, branch, worktree list, or `.devtime/` is read from or written to
for the snapshots.

Only committed, tracked files are part of a snapshot. Uncommitted changes are
reported as a warning rather than silently mixed in, so a review always
describes two exact commits.

No repository code is executed: `git archive` copies file contents, and the
scanner reads them as text.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tarfile
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class GitError(RuntimeError):
    """A git operation failed. Carries a reason and an actionable hint."""

    def __init__(self, reason: str, hint: str = "") -> None:
        self.reason = reason
        self.hint = hint
        super().__init__(reason)


def _git(args: list[str], cwd: Path, *, binary: bool = False):
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            check=False,
            text=not binary,
        )
    except FileNotFoundError as exc:
        raise GitError("git executable not found", "Install git and retry.") from exc
    if proc.returncode != 0:
        stderr = proc.stderr if isinstance(proc.stderr, str) else proc.stderr.decode(
            "utf-8", "replace"
        )
        raise GitError(stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def repo_toplevel(cwd: Path) -> Path:
    try:
        return Path(_git(["rev-parse", "--show-toplevel"], cwd).strip())
    except GitError as exc:
        raise GitError(
            "not inside a git repository",
            "Run dtc review from inside the repository you want to review.",
        ) from exc


def scope_prefix(cwd: Path) -> str:
    """Path of cwd relative to the repository root, without a trailing slash.

    `dtc scan` scans the current directory, so a review run from a subdirectory
    reviews that subdirectory. An empty string means the repository root.
    """
    return _git(["rev-parse", "--show-prefix"], cwd).strip().rstrip("/")


def is_shallow(cwd: Path) -> bool:
    try:
        return _git(["rev-parse", "--is-shallow-repository"], cwd).strip() == "true"
    except GitError:
        return False


def resolve_commit(ref: str, cwd: Path) -> str:
    try:
        return _git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd).strip()
    except GitError as exc:
        hint = f"Fetch it first (for example: git fetch origin), or check the spelling of '{ref}'."
        if is_shallow(cwd):
            hint = (
                "This clone is shallow, so the ref may not be available. In GitHub "
                "Actions use actions/checkout with fetch-depth: 0."
            )
        raise GitError(f"unknown revision '{ref}'", hint) from exc


def merge_base(base: str, head: str, cwd: Path) -> str:
    try:
        return _git(["merge-base", base, head], cwd).strip()
    except GitError as exc:
        hint = "The two commits share no history."
        if is_shallow(cwd):
            hint = (
                "This clone is shallow, so the common ancestor is not available. In "
                "GitHub Actions use actions/checkout with fetch-depth: 0."
            )
        raise GitError("could not compute a merge base", hint) from exc


def has_uncommitted_changes(cwd: Path) -> bool:
    try:
        return bool(_git(["status", "--porcelain", "--untracked-files=no"], cwd).strip())
    except GitError:
        return False


@dataclass(frozen=True)
class ChangedFile:
    status: str  # A, M, D, R, C, T
    path: str
    old_path: str | None = None

    def to_dict(self) -> dict:
        d = {"status": self.status, "path": self.path}
        if self.old_path:
            d["old_path"] = self.old_path
        return d


def changed_files(base: str, head: str, cwd: Path) -> list[ChangedFile]:
    """Files changed between two commits, relative to the review scope."""
    out = _git(
        ["diff", "--name-status", "-M", "--relative", "--no-color", base, head], cwd
    )
    files: list[ChangedFile] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code = parts[0][:1]
        if code in ("R", "C") and len(parts) >= 3:
            files.append(ChangedFile(code, parts[2].replace("\\", "/"), parts[1].replace("\\", "/")))
        else:
            files.append(ChangedFile(code, parts[1].replace("\\", "/")))
    return sorted(files, key=lambda f: (f.path, f.status))


def _safe_member(member: tarfile.TarInfo) -> bool:
    """Only plain files and directories that stay inside the snapshot."""
    if not (member.isfile() or member.isdir()):
        return False  # links and devices are not needed for a text scan
    p = PurePosixPath(member.name)
    return not p.is_absolute() and ".." not in p.parts


def extract_snapshot(commit: str, prefix: str, dest: Path, cwd: Path) -> int:
    """Write the tracked files of `commit` (limited to `prefix`) into `dest`.

    Returns the number of files written.

    git archive is run from the repository root on purpose. Run from a
    subdirectory, git archive already limits itself to that subtree, so an
    explicit `commit:prefix` would be limited twice and silently produce an
    empty snapshot - a review of two empty trees that looks clean (found while
    testing v0.7.0).
    """
    treeish = f"{commit}:{prefix}" if prefix else commit
    top = repo_toplevel(cwd)
    try:
        data = _git(["archive", "--format=tar", treeish], top, binary=True)
    except GitError as exc:
        raise GitError(
            f"could not read the snapshot at {commit[:12]}"
            + (f" for '{prefix}'" if prefix else ""),
            "The review scope may not exist at that commit.",
        ) from exc
    dest.mkdir(parents=True, exist_ok=True)
    written = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        for member in archive.getmembers():
            if not _safe_member(member):
                continue
            target = dest.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                continue
            with open(target, "wb") as fh:
                shutil.copyfileobj(source, fh)
            written += 1
    return written


@contextmanager
def review_workspace():
    """A temporary directory owned by this review, always removed afterwards.

    Only this directory is ever deleted. It is created by the review itself, so
    cleanup can never touch user files.
    """
    root = Path(tempfile.mkdtemp(prefix="devtime-review-"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def analyze_snapshot(root: Path) -> list:
    """Scan a materialized snapshot with its own memory and verify every claim.

    Returns the list of VerificationResult. The snapshot's memory lives inside
    the snapshot directory and is discarded with it.
    """
    from devtime.db import connection, migrations
    from devtime.intelligence import verification as ver
    from devtime.scanner.signals import run_scan

    migrations.init_repo(root)
    run_scan(root, progress=False)
    conn = connection.connect(root)
    try:
        return ver.verify_all(conn)
    finally:
        conn.close()
