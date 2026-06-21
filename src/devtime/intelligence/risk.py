"""Risk review (Builder Edition, Chapter 13).

Risk review checks a change against repository memory. It does not prove a PR is
broken; it surfaces low-noise, specific, evidence-linked, actionable signals.
One precise warning beats ten vague warnings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from devtime.intelligence.claims import ConceptIntelligence

MAX_FINDINGS = 3


@dataclass
class RiskFinding:
    severity: str
    concept: str
    type: str
    text: str
    changed_files: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    suggested_action: str = ""
    human_review_required: bool = False


@dataclass
class DiffInfo:
    changed_files: list[str]
    added_lines: list[str]
    removed_lines: list[str]

    @property
    def changed_text(self) -> str:
        return "\n".join(self.added_lines + self.removed_lines).lower()


def parse_unified_diff(diff_text: str) -> DiffInfo:
    changed_files: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    for line in diff_text.splitlines():
        m = re.match(r"^\+\+\+ b/(.+)$", line)
        if m:
            changed_files.append(m.group(1))
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
    return DiffInfo(changed_files=changed_files, added_lines=added, removed_lines=removed)


def _concept_touched(ci: ConceptIntelligence, changed_files: list[str]) -> bool:
    paths = {e.path for e in ci.evidence if e.path}
    return any(cf in paths for cf in changed_files)


def _behavior_changed(diff: DiffInfo, *keywords: str) -> bool:
    text = diff.changed_text
    return any(k in text for k in keywords)


def _test_changed(diff: DiffInfo, patterns: list[str]) -> bool:
    for cf in diff.changed_files:
        low = cf.lower()
        if (".test." in low or ".spec." in low or "test" in low) and any(
            p in low for p in patterns
        ):
            return True
    # Also count test bodies touched in the diff.
    text = diff.changed_text
    return any(p in text for p in patterns) and "test" in text


def review_diff(
    diff: DiffInfo, intelligence: list[ConceptIntelligence]
) -> list[RiskFinding]:
    findings: list[RiskFinding] = []

    for ci in intelligence:
        if not _concept_touched(ci, diff.changed_files):
            continue
        name = ci.concept.name

        # Billing Webhooks: retry/idempotency behavior changed without matching tests.
        if name == "Billing Webhooks" and _behavior_changed(
            diff, "retry", "idempoten", "duplicate"
        ):
            if not _test_changed(diff, ["duplicate", "webhook", "retry"]):
                findings.append(
                    RiskFinding(
                        severity="high",
                        concept=name,
                        type="missing_test_update",
                        text="Retry behavior changed without duplicate-delivery test changes.",
                        changed_files=diff.changed_files,
                        missing=["duplicate-delivery test update", "retry strategy decision"],
                        suggested_action=(
                            "Update duplicate-delivery tests or record the retry "
                            "behavior decision before merge."
                        ),
                        human_review_required=True,
                    )
                )

        # Authentication: token behavior changed but no related decision exists.
        if name == "Authentication" and _behavior_changed(diff, "token", "jwt", "refresh"):
            has_decision = any(e.kind == "decision" for e in ci.evidence)
            if not has_decision:
                findings.append(
                    RiskFinding(
                        severity="medium",
                        concept=name,
                        type="missing_decision",
                        text="Token behavior changed but no related decision was found.",
                        changed_files=diff.changed_files,
                        missing=["token strategy decision"],
                        suggested_action="Record a token strategy decision or link an existing ADR.",
                        human_review_required=True,
                    )
                )

    severity_rank = {"high": 3, "medium": 2, "low": 1}
    findings.sort(key=lambda f: severity_rank.get(f.severity, 0), reverse=True)
    return findings[:MAX_FINDINGS]
