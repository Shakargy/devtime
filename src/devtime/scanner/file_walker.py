"""Safe repository file walker (Builder Edition, Chapter 7).

Walks files without executing repository code. Ignored directories are pruned
*before* traversal (Reality Hardening): the walker never descends into
node_modules, .git, build output, .devtime, etc., instead of walking them and
filtering after the fact. Symlinks, large files, binaries, and ignored/secret
files are still skipped per file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from devtime.scanner import ignore as ignore_mod
from devtime.scanner.language import is_doc_path, is_test_path


@dataclass
class WalkedFile:
    path: Path
    rel_path: str
    size_bytes: int
    extension: str
    is_test: bool
    is_doc: bool


def _normalize(rel: str) -> str:
    while "//" in rel:
        rel = rel.replace("//", "/")
    return rel


def walk_repository(
    root: Path,
    ignore_matcher: ignore_mod.IgnoreMatcher,
    max_size_bytes: int,
    *,
    follow_symlinks: bool = False,
):
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        rel_dir = _normalize(Path(dirpath).relative_to(root).as_posix())

        # --- Prune ignored directories before descending into them. ---
        kept: list[str] = []
        for d in sorted(dirnames):
            if ignore_mod.is_pruned_dirname(d):
                continue
            child_rel = d if rel_dir in ("", ".") else f"{rel_dir}/{d}"
            child_rel = _normalize(child_rel)
            if ignore_matcher.match_dir(child_rel):
                continue
            child_path = Path(dirpath) / d
            if child_path.is_symlink() and not follow_symlinks:
                continue
            kept.append(d)
        dirnames[:] = kept  # in-place prune controls os.walk descent

        for fn in sorted(filenames):
            rel = _normalize(fn if rel_dir in ("", ".") else f"{rel_dir}/{fn}")
            if ignore_matcher.match(rel):
                continue
            path = Path(dirpath) / fn
            if path.is_symlink() and not follow_symlinks:
                continue
            extension = path.suffix.lower()
            if ignore_mod.is_binary_extension(extension):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > max_size_bytes:
                continue
            yield WalkedFile(
                path=path,
                rel_path=rel,
                size_bytes=size,
                extension=extension,
                is_test=is_test_path(rel),
                is_doc=is_doc_path(rel),
            )
