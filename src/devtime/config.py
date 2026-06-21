"""Configuration loading and defaults (Builder Edition, Chapter 5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from devtime import paths

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "repository": {
        "name": None,
        "root": ".",
    },
    "scanner": {
        "max_file_size_kb": 512,
        "follow_symlinks": False,
        "respect_gitignore": True,
        "respect_devtimeignore": True,
        "include_tests": True,
        "include_docs": True,
    },
    "privacy": {
        "ai_enabled": False,
        "cloud_enabled": False,
        "telemetry_enabled": False,
        "store_ask_history": False,
        "store_source_excerpts": False,
    },
    "context_packs": {
        "default_mode": "risk",
        "include_evidence_paths": True,
        "include_source_excerpts": False,
    },
    "mcp": {
        "enabled": False,
        "bind": "127.0.0.1",
        "read_only": True,
        "expose_source": False,
    },
}


def default_config_yaml() -> str:
    return yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(root: Path | None = None) -> dict[str, Any]:
    """Load config.yaml merged over defaults. Missing file returns defaults."""
    path = paths.config_path(root)
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _deep_merge(DEFAULT_CONFIG, loaded)
