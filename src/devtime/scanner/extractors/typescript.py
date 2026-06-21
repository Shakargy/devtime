"""TypeScript / JavaScript signal extractor (Builder Edition, Chapter 8)."""

from __future__ import annotations

import re

from devtime.scanner.extractors.base import Signal, read_text, signal
from devtime.scanner.file_walker import WalkedFile

_IMPORT_RE = re.compile(r"""import\s+.*?from\s+['"]([^'"]+)['"]""")
# Match app/router as well as named routers (authRouter, exportRouter, etc).
_ROUTE_RE = re.compile(
    r"""\b(?:app|\w*[Rr]outer)\.(get|post|put|patch|delete)\(\s*['"]([^'"]+)['"]""",
    re.I,
)
_MIDDLEWARE_RE = re.compile(
    r"""\b(requireAuth|authMiddleware|isAuthenticated|ensureAuth|requireAdmin)\b"""
)
_BULLMQ_WORKER_RE = re.compile(r"""new\s+Worker\(\s*['"]([^'"]+)['"]""")
_BULLMQ_QUEUE_RE = re.compile(r"""new\s+Queue\(\s*['"]([^'"]+)['"]""")


def extract_typescript_signals(file: WalkedFile) -> list[Signal]:
    text = read_text(file)
    signals: list[Signal] = []

    for match in _IMPORT_RE.finditer(text):
        module = match.group(1)
        # Skip relative imports; external dependencies are the useful signal.
        if module.startswith("."):
            continue
        signals.append(signal("dependency", name=module, file=file, confidence=0.6))

    for match in _ROUTE_RE.finditer(text):
        method = match.group(1).upper()
        path = match.group(2)
        signals.append(
            signal(
                "route",
                name=f"{method} {path}",
                file=file,
                confidence=0.8,
                metadata={"method": method, "path": path, "framework": "express"},
            )
        )

    if _MIDDLEWARE_RE.search(text):
        signals.append(
            signal("middleware", name="auth", file=file, confidence=0.7)
        )

    if "stripe.webhooks.constructEvent" in text:
        signals.append(
            signal(
                "webhook_signature_verification",
                name="stripe",
                file=file,
                confidence=0.9,
            )
        )

    if re.search(r"\bjsonwebtoken\b|\bjwt\.(sign|verify)\b", text):
        signals.append(signal("token_usage", name="jwt", file=file, confidence=0.8))

    for match in _BULLMQ_WORKER_RE.finditer(text):
        signals.append(
            signal(
                "background_job",
                name=f"worker:{match.group(1)}",
                file=file,
                confidence=0.8,
            )
        )
    for match in _BULLMQ_QUEUE_RE.finditer(text):
        signals.append(
            signal("queue", name=f"queue:{match.group(1)}", file=file, confidence=0.8)
        )

    return signals
