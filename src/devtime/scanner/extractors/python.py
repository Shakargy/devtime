"""Python signal extractor (Builder Edition, Chapter 8)."""

from __future__ import annotations

import re

from devtime.scanner.extractors.base import Signal, read_text, signal
from devtime.scanner.file_walker import WalkedFile

_IMPORT_RE = re.compile(r"""^\s*(?:from\s+(\w[\w.]*)\s+import|import\s+(\w[\w.]*))""", re.M)
_ROUTE_RE = re.compile(
    r"""@(?:app|router)\.(get|post|put|patch|delete)\(\s*['"]([^'"]+)['"]"""
)


def extract_python_signals(file: WalkedFile) -> list[Signal]:
    text = read_text(file)
    signals: list[Signal] = []

    for match in _IMPORT_RE.finditer(text):
        module = (match.group(1) or match.group(2) or "").split(".")[0]
        if module:
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
                metadata={"method": method, "path": path, "framework": "fastapi"},
            )
        )

    if "Depends(" in text and ("current_user" in text or "get_current_user" in text):
        signals.append(
            signal("auth_dependency", name="current_user", file=file, confidence=0.75)
        )

    if "@celery.task" in text or ".task(" in text or "@shared_task" in text:
        signals.append(
            signal("background_job", name=file.rel_path, file=file, confidence=0.75)
        )

    if re.search(r"\bjwt\.(encode|decode)\b|\bPyJWT\b", text):
        signals.append(signal("token_usage", name="jwt", file=file, confidence=0.8))

    if "stripe.Webhook.construct_event" in text:
        signals.append(
            signal(
                "webhook_signature_verification",
                name="stripe",
                file=file,
                confidence=0.9,
            )
        )

    return signals
