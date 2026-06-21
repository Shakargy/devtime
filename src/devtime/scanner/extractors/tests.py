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


def extract_test_signals(file: WalkedFile) -> list[Signal]:
    text = read_text(file)
    signals: list[Signal] = []
    for match in _TEST_NAME_RE.finditer(text):
        name = match.group(1) or match.group(2)
        if name:
            signals.append(signal("test", name=name, file=file, confidence=0.8))
    return signals
