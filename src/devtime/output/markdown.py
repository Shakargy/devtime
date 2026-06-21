"""Markdown rendering helpers for risk findings and exports."""

from __future__ import annotations

from devtime.intelligence.risk import RiskFinding


def render_risk_findings(findings: list[RiskFinding]) -> str:
    if not findings:
        return "DevTime Risk Review\n\nNo memory-aware risk findings for this diff."
    blocks = ["DevTime Risk Review", ""]
    for f in findings:
        blocks.append(f"Affected concept:\n  {f.concept}")
        blocks.append(f"Finding ({f.severity}):\n  {f.text}")
        if f.missing:
            blocks.append("Missing:")
            blocks += [f"  - {m}" for m in f.missing]
        blocks.append(f"Suggested action:\n  {f.suggested_action}")
        blocks.append("")
    return "\n".join(blocks)
