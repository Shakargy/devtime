"""Risk review (Builder Edition, Chapter 13; Trust Repair v0.0.6).

Risk review checks a change against repository memory. It does not prove a PR is
broken; it surfaces low-noise, specific, evidence-linked, actionable signals.

Trust Repair makes the result *honest* with explicit states:
  - review_failed          : DevTime could not read the diff (e.g. git failed).
  - no_findings            : the diff was inspected; no supported rule found a problem.
  - unsupported_change_class: known-concept files changed, but no rule covers this change.
  - finding                : a supported rule found a risk.

"No findings" never means "could not inspect" or "do not know this risk class".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from devtime.intelligence.claims import ConceptIntelligence

MAX_FINDINGS = 5

STATE_REVIEW_FAILED = "review_failed"
STATE_NO_FINDINGS = "no_findings"
STATE_UNSUPPORTED = "unsupported_change_class"
STATE_FINDING = "finding"


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
    why_it_matters: str = ""


@dataclass
class RiskReview:
    state: str
    findings: list[RiskFinding] = field(default_factory=list)
    affected_concepts: list[str] = field(default_factory=list)
    reason: str = ""  # populated for review_failed


@dataclass
class DiffInfo:
    changed_files: list[str]
    added_lines: list[str]
    removed_lines: list[str]

    @property
    def changed_text(self) -> str:
        return "\n".join(self.added_lines + self.removed_lines).lower()

    @property
    def code_lines(self) -> list[str]:
        return [ln for ln in (self.added_lines + self.removed_lines) if not _is_comment(ln)]

    @property
    def has_code_change(self) -> bool:
        """True if the diff contains at least one non-comment changed line."""
        return any(ln.strip() for ln in self.code_lines)


_COMMENT_RE = re.compile(r"""^\s*(//|#|/\*|\*|<!--|"""  r'"""' r"""|''')""")


def _is_comment(line: str) -> bool:
    return bool(_COMMENT_RE.match(line))


def review_failed(reason: str) -> RiskReview:
    return RiskReview(state=STATE_REVIEW_FAILED, reason=reason)


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


def _concept_evidence_paths(ci: ConceptIntelligence) -> set[str]:
    return {e.path for e in ci.evidence if e.path}


def _concept_touched(ci: ConceptIntelligence, changed_files: list[str]) -> bool:
    paths = _concept_evidence_paths(ci)
    return any(cf in paths for cf in changed_files)


def _behavior_changed(diff: DiffInfo, *keywords: str) -> bool:
    # A comment-only diff is never a behavior change (Trust Repair). When there is
    # real code change, keyword matches (including in adjacent comments) count.
    if not diff.has_code_change:
        return False
    return any(k in diff.changed_text for k in keywords)


def _test_changed(diff: DiffInfo, patterns: list[str]) -> bool:
    for cf in diff.changed_files:
        low = cf.lower()
        if (".test." in low or ".spec." in low or "test" in low) and any(
            p in low for p in patterns
        ):
            return True
    return any(p in diff.changed_text for p in patterns) and "test" in diff.changed_text


# --- JWT algorithm weakening (P0-2) ------------------------------------------

_ALGO_UNSAFE_RE = re.compile(
    r"""(?i)\b(alg|algorithm|jwt[_a-z]*algorithm|signing[_a-z]*algorithm)\b\s*[:=]\s*"""
    r"""['"]?\s*(none|null)\s*['"]?""",
)
_ALGO_EMPTY_RE = re.compile(
    r"""(?i)\b(alg|algorithm|jwt[_a-z]*algorithm|signing[_a-z]*algorithm)\b\s*[:=]\s*['"]\s*['"]""",
)


def _auth_evidence_files(intelligence: list[ConceptIntelligence]) -> set[str]:
    files: set[str] = set()
    for ci in intelligence:
        if ci.concept.name == "Authentication":
            files |= _concept_evidence_paths(ci)
    return files


def _looks_auth_path(path: str) -> bool:
    low = path.lower()
    return any(t in low for t in ("auth", "jwt", "token", "security", "login", "session"))


def detect_jwt_algorithm_risk(
    diff: DiffInfo, intelligence: list[ConceptIntelligence]
) -> list[RiskFinding]:
    """Value-aware: an algorithm constant changed to an unsafe value (none/empty).

    Comment lines are excluded, and the changed line need not mention 'jwt'/'token'.
    """
    auth_files = _auth_evidence_files(intelligence)
    findings: list[RiskFinding] = []
    for line in diff.added_lines:
        if _is_comment(line):
            continue
        if not (_ALGO_UNSAFE_RE.search(line) or _ALGO_EMPTY_RE.search(line)):
            continue
        in_auth = any(cf in auth_files for cf in diff.changed_files) or any(
            _looks_auth_path(cf) for cf in diff.changed_files
        )
        severity = "high" if in_auth else "medium"
        nearby_tests = _test_changed(diff, ["jwt", "token", "auth", "verify"])
        suggested = "Run JWT verification/key-rotation tests and require human security review."
        if not nearby_tests:
            suggested += " No nearby JWT verification tests were found in this diff."
        findings.append(
            RiskFinding(
                severity=severity,
                concept="Authentication",
                type="jwt_algorithm_weakening",
                text="JWT signing algorithm appears to change to an unsafe value: none.",
                changed_files=diff.changed_files,
                missing=["security review", "JWT verification tests"],
                suggested_action=suggested,
                human_review_required=True,
                why_it_matters="This may disable or weaken token signing/verification.",
            )
        )
        break  # one precise finding is enough
    return findings


# --- Main entry --------------------------------------------------------------

def review_diff(
    diff: DiffInfo, intelligence: list[ConceptIntelligence]
) -> RiskReview:
    if not diff.changed_files:
        return RiskReview(state=STATE_NO_FINDINGS)

    affected = [ci for ci in intelligence if _concept_touched(ci, diff.changed_files)]

    findings: list[RiskFinding] = []

    # Value-aware JWT algorithm weakening can fire even when Authentication evidence
    # is only path-adjacent (auth-looking file).
    findings += detect_jwt_algorithm_risk(diff, intelligence)

    for ci in affected:
        name = ci.concept.name

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
                        why_it_matters=(
                            "Billing webhooks may receive duplicate events; retry without "
                            "dedupe tests risks double-processing."
                        ),
                    )
                )

        if name == "Authentication" and _behavior_changed(diff, "token", "jwt", "refresh"):
            has_decision = any(e.kind == "decision" for e in ci.evidence)
            already_algo = any(f.type == "jwt_algorithm_weakening" for f in findings)
            if not has_decision and not already_algo:
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

    if findings:
        severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        findings.sort(key=lambda f: severity_rank.get(f.severity, 0), reverse=True)
        return RiskReview(
            state=STATE_FINDING,
            findings=findings[:MAX_FINDINGS],
            affected_concepts=sorted({f.concept for f in findings}),
        )

    if affected:
        # Known-concept files changed but no supported rule evaluated this change.
        return RiskReview(
            state=STATE_UNSUPPORTED,
            affected_concepts=sorted({ci.concept.name for ci in affected}),
        )

    # Diff inspected; nothing DevTime tracks was touched.
    return RiskReview(state=STATE_NO_FINDINGS)
