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
