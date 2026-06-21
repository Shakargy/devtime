"""Fixture runner (Builder Edition, Chapter 17).

Scans a fixture repo in an isolated temp copy (so fixtures are never mutated),
then asserts allowed claims, forbidden claims, required uncertainty, and concepts.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from devtime.fixtures import assertions
from devtime.fixtures.loader import Fixture, load_fixture
from devtime.scanner.signals import run_scan


@dataclass
class FixtureResult:
    fixture_id: str
    passed: bool
    missing_concepts: list[str] = field(default_factory=list)
    missing_allowed: list[str] = field(default_factory=list)
    present_forbidden: list[str] = field(default_factory=list)
    missing_uncertainty: list[str] = field(default_factory=list)

    def failures(self) -> list[str]:
        out: list[str] = []
        for label, items in (
            ("missing concept", self.missing_concepts),
            ("missing allowed claim", self.missing_allowed),
            ("forbidden claim present", self.present_forbidden),
            ("missing required uncertainty", self.missing_uncertainty),
        ):
            out += [f"{label}: {i}" for i in items]
        return out


def run_devtime_scan(repo: Path):
    """Scan a repo in an isolated temp copy and return its intelligence."""
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "repo"
        shutil.copytree(repo, dest)
        result = run_scan(root=dest)
        return result.intelligence


def run_fixture(directory: Path) -> FixtureResult:
    fixture: Fixture = load_fixture(directory)
    intelligence = run_devtime_scan(fixture.repo_path)
    exp = fixture.expected

    missing_concepts = assertions.assert_expected_concepts(intelligence, exp.concepts)
    missing_allowed = assertions.assert_allowed_claims(intelligence, exp.allowed_claims)
    present_forbidden = assertions.assert_forbidden_claims_absent(
        intelligence, exp.forbidden_claims
    )
    missing_uncertainty = assertions.assert_required_uncertainty(
        intelligence, exp.required_uncertainty
    )

    passed = not (
        missing_concepts or missing_allowed or present_forbidden or missing_uncertainty
    )
    return FixtureResult(
        fixture_id=fixture.id,
        passed=passed,
        missing_concepts=missing_concepts,
        missing_allowed=missing_allowed,
        present_forbidden=present_forbidden,
        missing_uncertainty=missing_uncertainty,
    )
