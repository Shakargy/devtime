"""Rendering for risk review results (Trust Repair v0.0.6)."""

from __future__ import annotations

from devtime.intelligence.risk import (
    STATE_FINDING,
    STATE_NO_FINDINGS,
    STATE_REVIEW_FAILED,
    STATE_UNSUPPORTED,
    RiskReview,
)


def render_risk_review(review: RiskReview) -> str:
    if review.state == STATE_REVIEW_FAILED:
        return (
            "Risk review failed: Git could not read the diff.\n"
            f"Reason: {review.reason or 'unknown'}"
        )

    if review.state == STATE_NO_FINDINGS:
        return (
            "DevTime Risk Review\n\n"
            "No memory-aware risk findings for this diff.\n"
            "Supported checks completed."
        )

    if review.state == STATE_UNSUPPORTED:
        concepts = ", ".join(review.affected_concepts) or "a known concept"
        return (
            "DevTime Risk Review\n\n"
            "Manual review required:\n"
            f"Changed files are linked to {concepts}, but V0 has no specific rule "
            "for this change class.\n"
            "No supported risk rule evaluated this diff."
        )

    # STATE_FINDING
    blocks = ["DevTime Risk Review", ""]
    for f in review.findings:
        blocks.append(f"Affected concept:\n  {f.concept}")
        blocks.append(f"Finding ({f.severity}):\n  {f.text}")
        if f.why_it_matters:
            blocks.append(f"Why this matters:\n  {f.why_it_matters}")
        if f.missing:
            blocks.append("Missing:")
            blocks += [f"  - {m}" for m in f.missing]
        blocks.append(f"Suggested action:\n  {f.suggested_action}")
        blocks.append("")
    return "\n".join(blocks)
