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

    gitignore = root / ".gitignore"
    devtime_in_gitignore = (
        gitignore.exists()
        and ".devtime/" in gitignore.read_text(encoding="utf-8", errors="ignore")
    )
    if not devtime_in_gitignore:
        warning.append(".devtime/ is not in .gitignore")
        recommended.append(
            "Add `.devtime/` to `.gitignore` unless you intentionally share local memory."
        )

    return {"good": good, "warning": warning, "recommended": recommended}
