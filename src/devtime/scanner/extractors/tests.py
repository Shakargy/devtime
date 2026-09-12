"""Test-file extractor (Builder Edition, Chapter 8).

Behavior-specific tests are strong evidence, so test names are first-class signals.
"""

from __future__ import annotations

import re

from devtime.scanner.extractors.base import Signal, read_text, signal
from devtime.scanner.file_walker import WalkedFile

_TEST_NAME_RE = re.compile(
    r"""(?:it|test|describe)\(\s*['"]([^'"]+)['"]"""  # JS/TS
    r"""|def\s+(test_\w+)"""  # pytest
)
# Imports a test references - used to attach tests to the implementation they cover
# (Evidence Precision v0.0.7): a truthful "imports the implementation" reason.
_IMPORT_RE = re.compile(
    r"""from\s+([\w.]+)\s+import|import\s+([\w.]+)"""  # python
    r"""|from\s+['"]([^'"]+)['"]""",  # JS/TS
)


# HTTP requests made by a test: supertest `request(app).get("/users")`, FastAPI
# `client.post("/items")`, fetch-style helpers. Only literals that look like a
# URL path count, so `map.get("key")` is not mistaken for a request (v0.6.0).
_REQUEST_RE = re.compile(
    r"""\.(get|post|put|patch|delete|head|options)\(\s*['"](/[^'"]*)['"]""",
    re.I,
)


def _extract_requests(text: str) -> list[dict]:
    seen: list[dict] = []
    for match in _REQUEST_RE.finditer(text):
        entry = {"method": match.group(1).upper(), "path": match.group(2)}
        if entry not in seen:
            seen.append(entry)
    return seen[:50]


def _extract_imports(text: str) -> list[str]:
    mods: list[str] = []
    for m in _IMPORT_RE.finditer(text):
        mod = m.group(1) or m.group(2) or m.group(3)
        if mod:
            mods.append(mod.lower())
    return mods


def _is_e2e(rel_path: str) -> bool:
    """E2E UI specs match concept keywords by accident and should be weak evidence.

    Reality Validation finding: `tests-e2e/specs/sidebar-navigation.e2e.spec.ts`
    was defining File Uploads, and other e2e specs polluted Data Export.
    """
    low = rel_path.lower()
    return ".e2e." in low or "/tests-e2e/" in low or "/e2e/" in low or "playwright" in low


def extract_test_signals(file: WalkedFile) -> list[Signal]:
    text = read_text(file)
    e2e = _is_e2e(file.rel_path)
    imports = _extract_imports(text)
    requests = _extract_requests(text)
    signals: list[Signal] = []
    for match in _TEST_NAME_RE.finditer(text):
        name = match.group(1) or match.group(2)
        if name:
            signals.append(
                signal(
                    "test",
                    name=name,
                    file=file,
                    confidence=0.4 if e2e else 0.8,
                    metadata={"e2e": e2e, "imports": imports, "requests": requests},
                )
            )
    return signals
