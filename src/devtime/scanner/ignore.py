"""Ignore-rule matching (Builder Edition, Chapter 7).

Respects .gitignore and .devtimeignore, and always refuses secrets, VCS internals,
and common generated directories even if the ignore files are missing.
"""

from __future__ import annotations

from pathlib import Path

import pathspec

# Always-on safety net. These must never become evidence (Chapter 7 safety rules).
HARD_DENY = [
    ".git/",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_ed25519",
    "secrets.*",
    "credentials.*",
    "service-account*.json",
    ".devtime/",
]

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".pdf", ".zip", ".gz", ".tar", ".7z", ".rar",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".mov", ".avi", ".wav",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".o", ".a",
    ".lock", ".sqlite", ".db",
}


class IgnoreMatcher:
    def __init__(self, patterns: list[str]):
        self._spec = pathspec.PathSpec.from_lines("gitignore", patterns)

    def match(self, rel_path: str) -> bool:
        return self._spec.match_file(rel_path)


def _read_patterns(path: Path) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def build_matcher(
    root: Path,
    *,
    respect_gitignore: bool = True,
    respect_devtimeignore: bool = True,
) -> IgnoreMatcher:
    patterns = list(HARD_DENY)
    if respect_gitignore:
        patterns += _read_patterns(root / ".gitignore")
    if respect_devtimeignore:
        patterns += _read_patterns(root / ".devtimeignore")
    return IgnoreMatcher(patterns)


def is_binary_extension(extension: str) -> bool:
    return extension.lower() in BINARY_EXTENSIONS
