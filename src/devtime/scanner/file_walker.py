"""Safe repository file walker (Builder Edition, Chapter 7).

Walks files without executing repository code, skipping ignored files,
symlinks, large files, and binaries.
"""

from __future__ import annotations

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


def walk_repository(
    root: Path,
    ignore_matcher: ignore_mod.IgnoreMatcher,
    max_size_bytes: int,
    *,
    follow_symlinks: bool = False,
):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if ignore_matcher.match(rel):
            continue
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
