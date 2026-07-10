"""Next.js App Router and Pages Router API signal extractor.

Added during V0 Reality Validation: Snapilio and SaaSVoice are Next.js App Router
apps whose API surface is file-based (`app/api/**/route.ts` exporting HTTP method
handlers). The Express/FastAPI extractors saw none of it, so every concept
degraded to weak dependency evidence. This extractor parses route handlers and
derives the route path from the directory structure.

v0.1.3 (Cal.com proof run): Pages Router API files (`pages/api/**/*.ts`) are also
routes; without them, admin/trpc surfaces were invisible. Disabled-endpoint stubs
(handlers whose only behavior is a 404/501 response, e.g. features stripped from a
community edition) are NOT route behavior and are skipped - a permanently-404
endpoint must not confirm a concept.
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


_PAGES_API_EXTS = (".ts", ".js", ".tsx", ".jsx")

# Pages Router handlers: export default function handler(...) / export default handler
_PAGES_HANDLER_RE = re.compile(r"export\s+default\s+(?:async\s+)?(?:function\b|\w+)")

_STATUS_RE = re.compile(r"(?:res\.status|new\s+Response\s*\([^)]*status\s*:)\s*\(?\s*(\d{3})")


def is_pages_api_route(rel_path: str) -> bool:
    if not rel_path.endswith(_PAGES_API_EXTS):
        return False
    return "pages/api/" in rel_path or rel_path.startswith("pages/api/")


def derive_pages_route_path(rel_path: str) -> str:
    """Turn apps/web/pages/api/trpc/admin/[trpc].ts -> /api/trpc/admin/[trpc]."""
    marker = "pages/api/"
    idx = rel_path.find(marker)
    tail = rel_path[idx + len(marker):]
    # Strip the extension; index files map to their directory.
    for ext in _PAGES_API_EXTS:
        if tail.endswith(ext):
            tail = tail[: -len(ext)]
            break
    if tail.endswith("/index") or tail == "index":
        tail = tail[: -len("index")].rstrip("/")
    return "/api/" + tail if tail else "/api"


def _is_disabled_stub(text: str) -> bool:
    """A handler whose only responses are 404/501 is a disabled-endpoint stub.

    Cal.com's community edition ships pages/api/stripe/webhook.ts as a handler
    that always returns 404 ("not available in community edition"). A route that
    can never do anything is not behavior evidence for any concept.
    """
    statuses = _STATUS_RE.findall(text)
    if not statuses:
        return False
    if not set(statuses) <= {"404", "501"}:
        return False
    # Real handlers verify, branch, or delegate; stubs are tiny and self-contained.
    if len(text) > 800:
        return False
    return "constructEvent" not in text


def _extract_pages_api(file: WalkedFile) -> list[Signal]:
    text = read_text(file)
    if not _PAGES_HANDLER_RE.search(text):
        return []
    route_path = derive_pages_route_path(file.rel_path)
    if _is_disabled_stub(text):
        # v0.2.0: a stub is not a route, but it IS a fact worth remembering - the
        # verification engine uses it as contradiction evidence ("the endpoint
        # exists in name; its only behavior is a 404/501"). Concept detection
        # ignores this kind entirely.
        return [
            signal(
                "disabled_endpoint",
                name=f"STUB {route_path}",
                file=file,
                confidence=0.8,
                metadata={"path": route_path, "framework": "nextjs-pages"},
            )
        ]
    return [
        signal(
            "route",
            name=f"ANY {route_path}",
            file=file,
            confidence=0.78,
            metadata={"method": "ANY", "path": route_path, "framework": "nextjs-pages"},
        )
    ]


def extract_nextjs_signals(file: WalkedFile) -> list[Signal]:
    if is_pages_api_route(file.rel_path):
        return _extract_pages_api(file)
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
