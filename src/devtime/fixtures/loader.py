"""Fixture loading (Builder Edition, Chapter 17 / Appendix D)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class FixtureExpectation:
    concepts: list[str] = field(default_factory=list)
    allowed_claims: list[str] = field(default_factory=list)
    forbidden_claims: list[str] = field(default_factory=list)
    required_uncertainty: list[str] = field(default_factory=list)


@dataclass
class Fixture:
    id: str
    type: str
    repo_path: Path
    expected: FixtureExpectation
    contains_secrets: bool = False
    language: str | None = None
    framework: str | None = None


def load_fixture(directory: Path) -> Fixture:
    spec_path = directory / "fixture.yaml"
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    expected = data.get("expected", {}) or {}
    privacy = data.get("privacy", {}) or {}
    return Fixture(
        id=data["id"],
        type=data.get("type", "claim"),
        repo_path=directory / "repo",
        language=data.get("language"),
        framework=data.get("framework"),
        contains_secrets=bool(privacy.get("contains_secrets", False)),
        expected=FixtureExpectation(
            concepts=expected.get("concepts", []) or [],
            allowed_claims=expected.get("allowed_claims", []) or [],
            forbidden_claims=expected.get("forbidden_claims", []) or [],
            required_uncertainty=expected.get("required_uncertainty", []) or [],
        ),
    )


def discover_fixtures(root: Path) -> list[Path]:
    return sorted(p.parent for p in root.rglob("fixture.yaml"))
