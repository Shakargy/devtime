"""Privacy and security implementation (Builder Edition, Chapter 19).

Privacy is architecture, not a footer.
"""

from __future__ import annotations

import re
from pathlib import Path

from devtime import config, paths

# Secret patterns (Chapter 19).
SECRET_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN PRIVATE KEY-----",
    r"sk-[A-Za-z0-9_-]{20,}",
    r"""(?i)(api_key|secret|token|password)\s*=\s*['"][^'"]+['"]""",
]


def redact_secret_like_values(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = re.sub(pattern, "<redacted-secret>", text)
    return text


def privacy_report(root: Path | None = None) -> dict:
    root = root or paths.repo_root()
    cfg = config.load_config(root)
    priv = cfg["privacy"]

    good: list[str] = []
    warning: list[str] = []
    recommended: list[str] = []

    good.append("AI disabled" if not priv["ai_enabled"] else "AI enabled")
    good.append("Cloud disabled" if not priv["cloud_enabled"] else "Cloud enabled")
    good.append("Telemetry off" if not priv["telemetry_enabled"] else "Telemetry on")

    if (root / ".devtimeignore").exists():
        good.append(".devtimeignore active")
    if (root / ".env").exists():
        good.append(".env ignored")

    status = _devtime_ignored(root)
    if status is True:
        good.append(".devtime/ is git-ignored")
    elif status is False:
        warning.append(".devtime/ is not ignored by git")
        recommended.append(
            "Add `.devtime/` to `.gitignore` unless you intentionally share local memory."
        )
    else:  # unknown (git unavailable)
        warning.append("Could not confirm whether .devtime/ is ignored (git unavailable)")
        recommended.append(
            "Verify `.devtime/` is ignored, e.g. add it to `.gitignore`."
        )

    return {"good": good, "warning": warning, "recommended": recommended}


def _devtime_ignored(root: Path) -> bool | None:
    """Return True/False if .devtime/ is git-ignored, or None if undeterminable.

    Trust Repair (v0.0.6): prefer `git check-ignore`, which honors parent
    .gitignore rules, so a nested repo whose parent ignores .devtime/ is not
    falsely warned. Falls back to a local .gitignore text check.
    """
    import subprocess

    # Probe a path *inside* .devtime/ so the dir-only pattern matches even when the
    # directory does not exist yet, and so parent .gitignore rules are honored.
    target = ".devtime/devtime.sqlite"
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", target],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        # exit 0 = ignored, 1 = not ignored, 128 = not a git repo / error.
        if proc.returncode == 0:
            return True
        if proc.returncode == 1:
            return False
    except FileNotFoundError:
        pass

    # Fallback: local .gitignore text only (cannot see parent rules).
    gitignore = root / ".gitignore"
    if gitignore.exists() and ".devtime/" in gitignore.read_text(
        encoding="utf-8", errors="ignore"
    ):
        return True
    return None
