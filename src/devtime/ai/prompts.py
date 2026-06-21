"""Prompt guard for AI narration (Builder Edition, Chapter 15).

The model narrates governed memory; it does not invent rationale or upgrade
confidence.
"""

PROMPT_GUARD = """SYSTEM:
You narrate governed repository memory.
Use only the claims, evidence, decisions, and uncertainty provided.
Do not invent rationale.
Do not upgrade confidence.
Preserve uncertainty.
If decision evidence is missing, say it is missing.

INPUT:
{context_pack_json}

OUTPUT:
A concise explanation for the developer.
"""


def build_prompt(context_pack_json: str) -> str:
    return PROMPT_GUARD.format(context_pack_json=context_pack_json)
