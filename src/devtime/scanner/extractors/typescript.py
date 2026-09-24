"""TypeScript / JavaScript signal extractor (Builder Edition, Chapter 8)."""

from __future__ import annotations

import re

from devtime.scanner.extractors.base import (
    Signal,
    classify_jwt_purpose,
    code_only,
    read_text,
    signal,
)
from devtime.scanner.file_walker import WalkedFile

_IMPORT_RE = re.compile(r"""import\s+.*?from\s+['"]([^'"]+)['"]""")
# Match app/router as well as named routers (authRouter, exportRouter, etc).
_ROUTE_RE = re.compile(
    r"""\b(?:app|\w*[Rr]outer)\.(get|post|put|patch|delete)(\()\s*['"]([^'"]+)['"]""",
    re.I,
)
_MIDDLEWARE_RE = re.compile(
    r"""\b(requireAuth|authMiddleware|isAuthenticated|ensureAuth|requireAdmin)\b"""
)


def _call_arguments(text: str, open_paren: int, limit: int = 600) -> str:
    """Return the argument text of a call whose '(' is at ``open_paren``.

    v0.5.1: evidence about a route must come from that route's own call site,
    not from anywhere in the file. Walking the balanced parentheses is enough
    to capture `router.get("/admin", requireAdmin, handler)` without pulling in
    unrelated code, comments, or other routes further down the file.
    """
    depth = 0
    end = min(len(text), open_paren + limit)
    for i in range(open_paren, end):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1 : i]
    return text[open_paren + 1 : end]
_SIGNATURE_CALL_RE = re.compile(r"\bwebhooks\.constructEvent(?:Async)?\s*\(")
_BULLMQ_WORKER_RE = re.compile(r"""new\s+Worker\(\s*['"]([^'"]+)['"]""")
_BULLMQ_QUEUE_RE = re.compile(r"""new\s+Queue\(\s*['"]([^'"]+)['"]""")
# Custom task-runner infrastructure (v0.1.3, Cal.com proof run): Cal.com's Tasker
# (InternalTasker / RedisTasker / task-processor) is real background-job behavior
# that the BullMQ-only patterns above cannot see. Matches task-runner classes and
# enqueue/task-processing verbs - NOT bare "task"/"job" words (todo apps,
# employment taxonomy) and NOT service workers.
# NOTE: no `\w*` prefixes here - `\w*Tasker` backtracks catastrophically on long
# identifiers in bundled/minified files (took a 4s Cal.com scan to 135s).
_TASK_RUNNER_RE = re.compile(
    r"Tasker|task[-_]processor|\btask_queue\b|\.enqueue\s*\(|\bprocessTasks?\s*\("
)


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
        path = match.group(3)
        # v0.5.1: the route's own arguments are what can protect it. Everything
        # else in the file is a different route's business.
        handlers = _call_arguments(text, match.start(2))
        signals.append(
            signal(
                "route",
                name=f"{method} {path}",
                file=file,
                start_line=text.count("\n", 0, match.start()) + 1,
                confidence=0.8,
                metadata={
                    "method": method,
                    "path": path,
                    "framework": "express",
                    "handlers": handlers.strip(),
                },
            )
        )

    if _MIDDLEWARE_RE.search(text):
        signals.append(
            signal("middleware", name="auth", file=file, confidence=0.7)
        )

    # v0.7.0: a verification CALL in executable code, never the name alone in a
    # comment or string. Any client variable (stripe, stripeClient, ...).
    verify_call = _SIGNATURE_CALL_RE.search(code_only(text, "typescript"))
    if verify_call:
        signals.append(
            signal(
                "webhook_signature_verification",
                name="stripe",
                file=file,
                start_line=text.count(chr(10), 0, verify_call.start()) + 1,
                confidence=0.9,
            )
        )

    if re.search(r"\bjsonwebtoken\b|\bjwt\.(sign|verify)\b", text):
        purpose = classify_jwt_purpose(text, file.rel_path)
        signals.append(
            signal(
                "token_usage",
                name="jwt",
                file=file,
                confidence=0.8,
                metadata={"purpose": purpose},
            )
        )

    # File uploads: multipart / multer / busboy / formData with a file part.
    if re.search(r"multipart/form-data|\bmulter\b|\bbusboy\b|\.formData\(", text):
        signals.append(
            signal("upload_endpoint", name="upload", file=file, confidence=0.75)
        )

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

    if _TASK_RUNNER_RE.search(text):
        signals.append(
            signal("background_job", name="task-runner", file=file, confidence=0.75)
        )

    return signals
