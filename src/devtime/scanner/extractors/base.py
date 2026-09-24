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


def _blank(segment: str) -> str:
    return "".join("\n" if c == "\n" else " " for c in segment)


def code_only(text: str, language: str) -> str:
    """Blank out comments and string literals, keeping executable code.

    Behavior evidence must come from code that runs. A call named in a comment,
    a docstring, an error message, or a detector's own search pattern is not a
    call (v0.7.0: DevTime scanning its own repository found the literal
    "stripe.Webhook.construct_event" inside its Python extractor and reported
    signature verification as SUPPORTED).

    Output has the same length and the same newlines as the input, so offsets
    and line numbers still map to the original file.

    This is a small lexer, not a parser. It errs toward hiding text: code inside
    template-literal interpolations is blanked too, which can hide evidence but
    never invents it.
    """
    python = language == "python"
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        two = text[i : i + 2]
        # Comments.
        if (python and ch == "#") or (not python and two == "//"):
            end = text.find("\n", i)
            end = n if end == -1 else end
            out.append(_blank(text[i:end]))
            i = end
            continue
        if not python and two == "/*":
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append(_blank(text[i:end]))
            i = end
            continue
        # Strings.
        if ch in "'\"" or (not python and ch == "`"):
            quote = ch
            if python and text[i : i + 3] in ('"""', "'''"):
                quote = text[i : i + 3]
            j = i + len(quote)
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text.startswith(quote, j):
                    j += len(quote)
                    break
                if len(quote) == 1 and quote != "`" and text[j] == "\n":
                    break  # unterminated single-line string
                j += 1
            j = min(j, n)
            out.append(_blank(text[i:j]))
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def classify_jwt_purpose(text: str, rel_path: str) -> str:
    """Classify what a JWT is used for (Trust Repair v0.0.6).

    Returns "access", "invitation", or "unclear". Invitation/verification tokens
    are not access tokens and must not be claimed as such.
    """
    hay = (text + " " + rel_path).lower()
    access_signals = (
        "access token", "accesstoken", "access_token", "bearer", "authorization",
        "login", "signin", "sign-in", "refresh token", "refresh_token",
        "req.cookies", "set-cookie", "auth middleware", "current_user",
        "get_current_user",
    )
    invitation_signals = (
        "invite", "invitation", "verify email", "verify-email", "email_verification",
        "password reset", "password-reset", "reset_token", "magic link", "magic-link",
        "one-time", "onetime",
    )
    has_access = any(s in hay for s in access_signals)
    has_invite = any(s in hay for s in invitation_signals)
    if has_access and not has_invite:
        return "access"
    if has_invite and not has_access:
        return "invitation"
    if has_access and has_invite:
        return "access"  # an access path that also issues invites still does access auth
    return "unclear"
