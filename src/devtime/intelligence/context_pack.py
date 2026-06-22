"""Context Packs (Builder Edition, Chapter 14; Trust Repair v0.0.6).

Context Packs are governed repository memory for humans and AI agents. Trust Repair
makes them: (1) refuse to be authoritative when concept evidence is weak, (2) cap
and rank recommended tests, and (3) attach a reason to every recommended test.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from datetime import datetime, timezone

from devtime.intelligence.claims import ConceptIntelligence

MODES = ("overview", "risk", "implementation", "testing", "onboarding", "security")
MAX_TESTS = 8

# Domain terms used to rank/justify test relevance per concept.
DOMAIN_TERMS = {
    "Billing Webhooks": ("stripe", "paypal", "billing", "payment", "invoice", "checkout", "webhook"),
    "Authentication": ("auth", "jwt", "token", "login", "session", "oauth", "password"),
    "Background Jobs": ("job", "queue", "worker", "task", "celery", "bullmq", "cron"),
    "Data Export": ("export", "download", "csv", "report", "backup"),
    "Admin Permissions": ("admin", "permission", "role", "rbac", "superuser"),
    "File Uploads": ("upload", "multipart", "file", "attachment", "storage"),
}


@dataclass
class TestRec:
    path: str
    reason: str
    rank: int


@dataclass
class ContextPack:
    concept: str
    mode: str
    purpose: str
    limited: bool = False
    supported_claims: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    uncertainty: list[str] = field(default_factory=list)
    do_not_change: list[str] = field(default_factory=list)
    tests_to_run: list[TestRec] = field(default_factory=list)
    agent_guidance: str = ""
    generated_at: str = ""


def _is_weak(ci: ConceptIntelligence) -> bool:
    return getattr(ci.concept, "weak_only", False) or ci.concept.confidence < 0.5


def _do_not_change_warnings(ci: ConceptIntelligence) -> list[str]:
    """Derive 'do not change' warnings from actual evidence, never a hardcoded table.
    Weak/false concepts must not produce authoritative warnings."""
    if _is_weak(ci):
        return [
            "Evidence weak — manual validation required before using this as agent context."
        ]
    kinds = {e.signal.kind for e in ci.evidence}
    warnings: list[str] = []
    if "webhook_signature_verification" in kinds:
        warnings.append("Webhook signature verification behavior.")
    if "token_usage" in kinds:
        warnings.append("Token issuing and verification behavior.")
    if "auth_dependency" in kinds or "middleware" in kinds:
        warnings.append("Authorization / protected-route behavior.")
    if "route" in kinds:
        warnings.append(f"Request handling behavior for {ci.concept.name}.")
    if "background_job" in kinds or "queue" in kinds:
        warnings.append("Job/queue processing behavior.")
    if not warnings:
        warnings.append(f"Core behavior of {ci.concept.name} without a reviewer.")
    return warnings


# Generic path/monorepo tokens that are not specific enough to prove an import
# relation (avoids "imports" matching on "src", "plane", "packages", etc).
_COMMON_PATH_TOKENS = {
    "app", "apps", "api", "src", "lib", "libs", "server", "servers", "service",
    "services", "test", "tests", "spec", "specs", "package", "packages", "shared",
    "web", "core", "common", "utils", "util", "index", "main", "models", "model",
    "types", "type", "components", "component", "pages", "routes", "route",
    "handlers", "handler", "dist", "build", "internal", "backend", "frontend",
    "plane", "modules", "module", "config", "configs",
}


def _impl_modules(ci: ConceptIntelligence) -> set[str]:
    """Specific identifier tokens from non-test evidence paths, for import matching.
    Common monorepo/path tokens are excluded so an import match is meaningful."""
    mods: set[str] = set()
    for e in ci.evidence:
        if e.path and e.signal.kind != "test":
            stem = e.path.lower().replace("\\", "/").replace(".py", "").replace(".ts", "")
            for part in stem.split("/"):
                if len(part) >= 4 and part not in _COMMON_PATH_TOKENS:
                    mods.add(part)
    return mods


def _rank_tests(ci: ConceptIntelligence) -> list[TestRec]:
    """Recommend a test ONLY when the relation is provable, with a true reason
    (Codex blockers 3 & 4): an import relation, or a genuine same-directory relation.
    Otherwise omit it — a missing recommendation beats a false reason."""
    impl_dirs = {
        posixpath.dirname(e.path)
        for e in ci.evidence
        if e.path and e.signal.kind != "test"
    }
    impl_modules = _impl_modules(ci)

    recs: list[TestRec] = []
    seen: set[str] = set()
    for e in ci.evidence:
        if e.signal.kind != "test" or not e.path or e.path in seen:
            continue
        seen.add(e.path)
        d = posixpath.dirname(e.path)
        imports = [str(i).lower() for i in e.signal.metadata.get("imports", [])]

        imported = any(any(m in imp for m in impl_modules) for imp in imports)
        if imported:
            recs.append(TestRec(
                e.path,
                "Recommended because it imports or tests the implementation.",
                4,
            ))
        elif impl_dirs and d in impl_dirs:
            recs.append(TestRec(
                e.path,
                "Recommended because it is in the same directory as the implementation.",
                3,
            ))
        # No provable relation -> omit (do not invent a reason).

    recs.sort(key=lambda r: r.rank, reverse=True)
    return recs[:MAX_TESTS]


def generate_context_pack(ci: ConceptIntelligence, mode: str = "risk") -> ContextPack:
    if mode not in MODES:
        mode = "risk"
    weak = _is_weak(ci)

    supported = [
        f"{c.text} Evidence: "
        f"{', '.join(dict.fromkeys(e.path for e in c.evidence if e.path)) or 'n/a'}"
        for c in ci.claims
        if c.type != "uncertainty" and c.state in ("supported", "weak", "partial")
    ]
    decisions = [
        e.summary for e in ci.evidence if e.kind == "decision"
    ] or ["No corroborated decision record found."]
    uncertainty = [u.text for u in ci.uncertainties]
    tests = _rank_tests(ci)

    if weak:
        purpose = (
            f"Context Pack is limited because {ci.concept.name} evidence is weak. "
            "Validate before using as authoritative agent context."
        )
        guidance = (
            "Evidence is weak or generic. Do not treat this concept as established. "
            "Validate against the implementation before acting."
        )
    else:
        purpose = f"{ci.concept.name} is detected from repository evidence."
        guidance = (
            "Do not invent rationale for missing decisions. Ask a human or record a "
            "corroborated decision before changing core behavior."
            if ci.uncertainties
            else "Preserve existing behavior and keep evidence links intact."
        )

    return ContextPack(
        concept=ci.concept.name,
        mode=mode,
        purpose=purpose,
        limited=weak,
        supported_claims=supported,
        decisions=decisions,
        uncertainty=uncertainty,
        do_not_change=_do_not_change_warnings(ci),
        tests_to_run=tests,
        agent_guidance=guidance,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def render_markdown(pack: ContextPack) -> str:
    lines = [
        f"# Context Pack: {pack.concept}",
        f"Mode: {pack.mode}" + ("  (LIMITED — weak evidence)" if pack.limited else ""),
        "Generated by: DevTime",
        "Source: local repository memory",
        "",
        "## Purpose",
        pack.purpose,
        "",
        "## Supported Claims",
    ]
    lines += [f"- {c}" for c in pack.supported_claims] or ["- None"]
    lines += ["", "## Decisions"]
    lines += [f"- {d}" for d in pack.decisions]
    lines += ["", "## Uncertainty"]
    lines += [f"- {u}" for u in pack.uncertainty] or ["- None"]
    lines += ["", "## Do Not Change Without Review"]
    lines += [f"- {w}" for w in pack.do_not_change]
    lines += ["", f"## Tests To Run (top {MAX_TESTS}, ranked)"]
    if pack.tests_to_run:
        for t in pack.tests_to_run:
            lines.append(f"- {t.path}")
            lines.append(f"  - {t.reason}")
    else:
        lines.append("- No behavior-specific tests found.")
    lines += ["", "## Agent Instruction", pack.agent_guidance]
    return "\n".join(lines)
