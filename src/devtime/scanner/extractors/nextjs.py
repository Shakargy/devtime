"""Next.js App Router signal extractor.

Added during V0 Reality Validation: Snapilio and SaaSVoice are Next.js App Router
apps whose API surface is file-based (`app/api/**/route.ts` exporting HTTP method
handlers). The Express/FastAPI extractors saw none of it, so every concept
degraded to weak dependency evidence. This extractor parses route handlers and
derives the route path from the directory structure.
"""

from __future__ import annotations

import re

from devtime.scanner.extractors.base import Signal, read_text, signal
from devtime.scanner.file_walker import WalkedFile

# export async function GET(...) / export function POST(...) / export const DELETE = ...
_METHOD_RE = re.compile(
    r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b"
    r"|export\s+const\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s*=",
)

_ROUTE_FILES = {"route.ts", "route.js", "route.tsx", "route.jsx"}


def is_app_router_route(rel_path: str) -> bool:
    name = rel_path.rsplit("/", 1)[-1]
    if name not in _ROUTE_FILES:
        return False
    return "/app/" in rel_path or rel_path.startswith("app/")


def derive_route_path(rel_path: str) -> str:
    """Turn app/api/(payments)/checkout/[id]/route.ts -> /api/checkout/[id].

    Route groups like (payments) are stripped; dynamic segments like [id] and
    [...slug] are kept. Paths are normalised so no empty segments survive.
    """
    parts = rel_path.split("/")
    # Locate the segment named "app" (handles src/app/... too); start after it.
    try:
        app_idx = len(parts) - 1 - parts[::-1].index("app")
    except ValueError:
        app_idx = -1
    segments = parts[app_idx + 1 : -1]  # drop everything up to app/ and the route file

    cleaned: list[str] = []
    for seg in segments:
        if not seg:
            continue
        # Route groups (parentheses) and parallel/intercept routes do not affect the URL.
        if seg.startswith("(") and seg.endswith(")"):
            continue
        if seg.startswith("@"):
            continue
        cleaned.append(seg)
    return "/" + "/".join(cleaned)


def extract_nextjs_signals(file: WalkedFile) -> list[Signal]:
    if not is_app_router_route(file.rel_path):
        return []
    text = read_text(file)
    methods: list[str] = []
    for match in _METHOD_RE.finditer(text):
        methods.append(match.group(1) or match.group(2))
    if not methods:
        return []

    route_path = derive_route_path(file.rel_path)
    signals: list[Signal] = []
    for method in methods:
        signals.append(
            signal(
                "route",
                name=f"{method} {route_path}",
                file=file,
                confidence=0.82,
                metadata={"method": method, "path": route_path, "framework": "nextjs"},
            )
        )
    return signals
