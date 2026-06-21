"""Config and dependency-manifest extractor (Builder Edition, Chapter 8)."""

from __future__ import annotations

import json
import re

from devtime.scanner.extractors.base import Signal, read_text, signal
from devtime.scanner.file_walker import WalkedFile

_ENV_REF_RE = re.compile(r"\b([A-Z][A-Z0-9_]{3,})\b")


def extract_config_signals(file: WalkedFile) -> list[Signal]:
    name = file.path.name.lower()
    text = read_text(file)
    signals: list[Signal] = []

    # package.json / requirements: dependency signals.
    if name == "package.json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        for section in ("dependencies", "devDependencies"):
            for dep in (data.get(section) or {}):
                signals.append(signal("dependency", name=dep, file=file, confidence=0.6))
    elif name in ("requirements.txt", "requirements-dev.txt"):
        for line in text.splitlines():
            dep = re.split(r"[=<>!~ ]", line.strip(), 1)[0]
            if dep and not dep.startswith("#"):
                signals.append(signal("dependency", name=dep, file=file, confidence=0.6))

    # .env.example and config files: env var names are concept hints (never values).
    if name.startswith(".env") or name.endswith((".env", ".env.example")):
        for match in _ENV_REF_RE.finditer(text):
            signals.append(
                signal("config", name=match.group(1), file=file, confidence=0.5)
            )

    return signals
