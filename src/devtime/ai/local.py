"""Placeholder for a local model provider (e.g. Ollama) - disabled in V0."""

from __future__ import annotations

from devtime.ai.providers import DisabledProvider


class LocalModelProvider(DisabledProvider):
    """Local provider stub. Stays disabled until a user explicitly configures it."""

    name = "local"
