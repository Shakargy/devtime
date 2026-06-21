"""MCP tool schemas (Full Book Appendix C; Builder Edition Chapter 16)."""

from __future__ import annotations

TOOLS = {
    "read": [
        "list_concepts",
        "explain_concept",
        "show_evidence",
        "get_claims",
        "get_decisions",
        "get_understanding_debt",
    ],
    "context": [
        "get_context_pack",
        "get_onboarding_pack",
        "get_risk_context",
    ],
    "review": [
        "review_diff",
        "check_sensitive_concepts",
    ],
    "write_later": [
        "add_decision",
        "challenge_claim",
        "confirm_claim",
    ],
}

DEFAULT_PERMISSIONS = {
    "read_memory": True,
    "read_evidence_metadata": True,
    "read_source": False,
    "generate_context_pack": True,
    "review_diff": True,
    "write_decisions": False,
    "challenge_claims": False,
    "export_memory": False,
}
