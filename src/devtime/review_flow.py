"""Base/head advisory review (v0.7.0).

Workflow:
  1. Resolve the base and head refs to commits.
  2. Compare merge-base(base, head)..head - the same range a pull request shows.
  3. Materialize both commits in a temporary workspace and scan each one with
     its own memory.
  4. Verify every built-in claim at both commits.
  5. Report claim transitions, with the changed files that caused them.

The review is advisory. It never modifies the repository, never executes
repository code, and reports operational failures as failures: a review that
could not run must never look like a review that found nothing.
"""

from __future__ import annotations

from pathlib import Path

from devtime import __version__
from devtime.intelligence import review as rv
from devtime.snapshots import (
    GitError,
    analyze_snapshot,
    changed_files,
    extract_snapshot,
    has_uncommitted_changes,
    merge_base,
    repo_toplevel,
    resolve_commit,
    review_workspace,
    scope_prefix,
)

SCHEMA_VERSION = "1"
COMPARISON = "merge-base..head"
_CHANGED_FILES_CAP = 200

LIMITATIONS = [
    "Advisory only: claim statuses come from static analysis and are not a merge "
    "gate, a security review, or proof of runtime behavior.",
    "Only committed, tracked files are compared. Uncommitted changes are not part "
    "of either snapshot.",
    "Each snapshot is scanned with the ignore rules committed at that snapshot. A "
    "local, untracked .devtimeignore is not applied.",
    "Files excluded by export-ignore in .gitattributes are not part of a snapshot.",
]


def _failed(base_ref: str, head_ref: str, reason: str, hint: str = "") -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "review",
        "devtime_version": __version__,
        "status": "failed",
        "comparison": COMPARISON,
        "base": {"ref": base_ref},
        "head": {"ref": head_ref},
        "error": {"reason": reason, "hint": hint},
        "transitions": [],
        "limitations": LIMITATIONS,
    }


def run_review(cwd: Path, base_ref: str, head_ref: str = "HEAD") -> dict:
    """Run a review and return its report. Never raises for operational
    failures; the report's `status` says whether the review completed."""
    try:
        repo_toplevel(cwd)
        prefix = scope_prefix(cwd)
        head_commit = resolve_commit(head_ref, cwd)
        base_commit = resolve_commit(base_ref, cwd)
        mb = merge_base(base_commit, head_commit, cwd)
        files = changed_files(mb, head_commit, cwd)
    except GitError as exc:
        return _failed(base_ref, head_ref, exc.reason, exc.hint)

    warnings: list[str] = []
    if head_ref == "HEAD" and has_uncommitted_changes(cwd):
        warnings.append(
            "Your working tree has uncommitted changes. They are not part of this "
            "review, which compares commits. Commit them to include them."
        )

    changed_paths: set[str] = set()
    for f in files:
        changed_paths.add(f.path)
        if f.old_path:
            changed_paths.add(f.old_path)

    try:
        with review_workspace() as ws:
            base_dir = ws / "base"
            head_dir = ws / "head"
            n_base = extract_snapshot(mb, prefix, base_dir, cwd)
            n_head = extract_snapshot(head_commit, prefix, head_dir, cwd)
            # An empty comparison must never read as a clean review.
            if n_base == 0 and n_head == 0:
                return _failed(
                    base_ref,
                    head_ref,
                    f"both snapshots are empty for scope '{prefix or '.'}'",
                    "Run dtc review from the directory you want to review.",
                )
            if n_base == 0:
                warnings.append(
                    f"The base snapshot has no files in scope '{prefix or '.'}', so "
                    "every applicable claim will appear newly applicable."
                )
            if n_head == 0:
                warnings.append(
                    f"The head snapshot has no files in scope '{prefix or '.'}', so "
                    "every claim will appear no longer applicable."
                )
            base_results = analyze_snapshot(base_dir)
            head_results = analyze_snapshot(head_dir)
    except GitError as exc:
        return _failed(base_ref, head_ref, exc.reason, exc.hint)
    except Exception as exc:  # noqa: BLE001 - a failed scan must be reported
        return _failed(
            base_ref,
            head_ref,
            f"a snapshot could not be scanned: {exc}",
            "Run dtc scan in the repository to see the underlying error.",
        )

    transitions = rv.compute_transitions(base_results, head_results, changed_paths)
    counts = rv.summarize(transitions)

    return {
        "schema_version": SCHEMA_VERSION,
        "command": "review",
        "devtime_version": __version__,
        "status": "completed",
        "comparison": COMPARISON,
        "scope": prefix or ".",
        "base": {"ref": base_ref, "commit": base_commit, "merge_base": mb},
        "head": {"ref": head_ref, "commit": head_commit},
        "changed_files_total": len(files),
        "changed_files": [f.to_dict() for f in files[:_CHANGED_FILES_CAP]],
        "summary": counts,
        "transitions": [t.to_dict() for t in rv.reportable(transitions)],
        "warnings": warnings,
        "limitations": LIMITATIONS,
        "error": None,
    }


def has_regression(report: dict) -> bool:
    return report.get("status") == "completed" and bool(
        report.get("summary", {}).get(rv.REGRESSION)
    )
