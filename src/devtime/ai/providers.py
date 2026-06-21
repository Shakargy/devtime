"""Local AI provider layer (Builder Edition, Chapter 15).

AI is optional, explicit, and never the truth layer. V0 ships a disabled provider
by default and never calls AI automatically.
"""

from __future__ import annotations

from typing import Protocol


class AIProvider(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    def generate(self, prompt: str, *, max_tokens: int) -> str: ...


class DisabledProvider:
    name = "none"

    def is_configured(self) -> bool:
        return False

    def generate(self, prompt: str, *, max_tokens: int) -> str:
        raise RuntimeError("AI is disabled. Enable explicitly before generating.")


def default_provider() -> AIProvider:
    return DisabledProvider()


def ai_status() -> dict:
    provider = default_provider()
    return {
        "ai": "Disabled" if not provider.is_configured() else "Enabled",
        "provider": provider.name,
        "automatic_ai_calls": "Disabled",
        "data_sent": "Nothing",
    }
