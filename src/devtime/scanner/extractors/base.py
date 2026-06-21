"""Shared signal model for extractors (Builder Edition, Chapter 8).

A signal is a small extracted fact. It does not have to be perfect, but it must
be typed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from devtime.scanner.file_walker import WalkedFile


@dataclass
class Signal:
    kind: str
    name: str | None
    file_rel_path: str
    value: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


def signal(
    kind: str,
    *,
    name: str | None = None,
    file: WalkedFile,
    value: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
    confidence: float = 0.5,
    metadata: dict[str, Any] | None = None,
) -> Signal:
    return Signal(
        kind=kind,
        name=name,
        file_rel_path=file.rel_path,
        value=value,
        start_line=start_line,
        end_line=end_line,
        confidence=confidence,
        metadata=metadata or {},
    )


def read_text(file: WalkedFile) -> str:
    try:
        return file.path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
