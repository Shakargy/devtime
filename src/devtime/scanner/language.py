"""Language and file-role classification (Builder Edition, Chapter 7)."""

from __future__ import annotations

TEST_HINTS = (".test.", ".spec.", "_test.", "test_")
TEST_DIRS = ("/tests/", "/test/", "/__tests__/", "tests/", "test/")
DOC_DIRS = ("/docs/", "docs/")
DOC_EXTS = (".md", ".mdx", ".rst")


def classify_language(path: str) -> str | None:
    if path.endswith((".ts", ".tsx", ".js", ".jsx")):
        return "typescript"
    if path.endswith(".py"):
        return "python"
    if path.endswith((".md", ".mdx")):
        return "markdown"
    if path.endswith((".yml", ".yaml")):
        return "yaml"
    if path.endswith(".json"):
        return "json"
    return None


def is_test_path(rel_path: str) -> bool:
    lower = rel_path.lower()
    if any(hint in lower for hint in TEST_HINTS):
        return True
    return any(d in lower for d in TEST_DIRS)


def is_doc_path(rel_path: str) -> bool:
    lower = rel_path.lower()
    if lower.endswith(DOC_EXTS):
        return True
    return any(d in lower for d in DOC_DIRS)
