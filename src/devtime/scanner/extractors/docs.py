"""Docs and decision-record extractor (Builder Edition, Chapter 8)."""

from __future__ import annotations

import re

from devtime.scanner.extractors.base import Signal, read_text, signal
from devtime.scanner.file_walker import WalkedFile

_HEADING_RE = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.M)


def extract_doc_signals(file: WalkedFile) -> list[Signal]:
    text = read_text(file)
    signals: list[Signal] = []

    is_decision = "/decisions/" in file.rel_path.lower() or re.match(
        r"^\d{3,4}-", file.path.name
    )

    for match in _HEADING_RE.finditer(text):
        heading = match.group(1).strip()
        line = text.count("\n", 0, match.start()) + 1
        kind = "decision" if is_decision else "doc"
        signals.append(
            signal(
                kind,
                name=heading,
                file=file,
                start_line=line,
                confidence=0.7 if is_decision else 0.4,
            )
        )

    return signals
