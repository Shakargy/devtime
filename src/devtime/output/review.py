"""Human and Markdown rendering for `dtc review` (v0.7.0).

Presentation only: every fact rendered here comes from the report produced by
devtime.review_flow. Markdown is written for a GitHub step summary, so a
reviewer can read the result without opening raw job logs.
"""

from __future__ import annotations

_LABEL = {
    "regression": "Regression",
    "newly_applicable": "Newly applicable",
    "no_longer_applicable": "No longer applicable",
    "improvement": "Improvement",
    "evidence_changed": "Evidence changed",
}


def _short(commit: str | None) -> str:
    return (commit or "")[:12]


def _unchanged_count(report: dict) -> int:
    return int(report.get("summary", {}).get("unchanged", 0))


def render_text(report: dict) -> str:
    if report.get("status") != "completed":
        err = report.get("error") or {}
        lines = [
            "DevTime review could not be completed.",
            f"  reason: {err.get('reason', 'unknown error')}",
        ]
        if err.get("hint"):
            lines.append(f"  hint:   {err['hint']}")
        lines.append("This is a failed review, not a clean one. No findings were produced.")
        return "\n".join(lines)

    base, head = report["base"], report["head"]
    lines = [
        "DevTime review",
        f"  base   {base['ref']}  (merge base {_short(base.get('merge_base'))})",
        f"  head   {head['ref']}  ({_short(head.get('commit'))})",
        f"  scope  {report.get('scope', '.')}   "
        f"{report.get('changed_files_total', 0)} file(s) changed",
        "",
    ]
    for w in report.get("warnings", []):
        lines += [f"Warning: {w}", ""]

    transitions = report.get("transitions", [])
    if not transitions:
        lines.append(
            "No claim changed status, and no evidence behind an applicable claim "
            "changed."
        )
        lines.append("")
    for t in transitions:
        label = _LABEL.get(t["kind"], t["kind"])
        lines.append(
            f"{label}: {t['claim_id']}  {t['base_status']} -> {t['head_status']}"
        )
        if t.get("base_summary"):
            lines.append(f"  base: {t['base_summary']}")
        if t.get("head_summary") and t["head_summary"] != t.get("base_summary"):
            lines.append(f"  head: {t['head_summary']}")
        for p in t.get("changed_evidence", [])[:5]:
            lines.append(f"  changed evidence: {p}")
        if t["kind"] == "regression":
            for m in t.get("head_missing_evidence", [])[:3]:
                lines.append(f"  missing now: {m}")
        if t.get("note"):
            lines.append(f"  {t['note']}")
        lines.append("")

    unchanged = _unchanged_count(report)
    if unchanged:
        lines.append(f"{unchanged} claim(s) unchanged and unaffected by this change.")
    lines.append(
        "Advisory: statuses come from static analysis. They are not a merge gate "
        "or proof of runtime behavior."
    )
    return "\n".join(lines)


def _cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict) -> str:
    if report.get("status") != "completed":
        err = report.get("error") or {}
        out = [
            "### DevTime review: failed",
            "",
            f"**Reason:** {_cell(err.get('reason', 'unknown error'))}",
        ]
        if err.get("hint"):
            out.append(f"**Hint:** {_cell(err['hint'])}")
        out += ["", "_This review did not run. It is not a clean result._"]
        return "\n".join(out)

    base, head = report["base"], report["head"]
    out = [
        "### DevTime review",
        "",
        f"`{base['ref']}` (merge base `{_short(base.get('merge_base'))}`) -> "
        f"`{head['ref']}` (`{_short(head.get('commit'))}`), "
        f"{report.get('changed_files_total', 0)} file(s) changed",
        "",
    ]
    for w in report.get("warnings", []):
        out += [f"> {_cell(w)}", ""]

    transitions = report.get("transitions", [])
    if not transitions:
        out += [
            "No claim changed status, and no evidence behind an applicable claim "
            "changed.",
            "",
        ]
    else:
        out += [
            "| Change | Claim | Base | Head | Now |",
            "|---|---|---|---|---|",
        ]
        for t in transitions:
            out.append(
                f"| {_LABEL.get(t['kind'], t['kind'])} | `{t['claim_id']}` | "
                f"{t['base_status']} | {t['head_status']} | "
                f"{_cell(t.get('head_summary') or t.get('base_summary', ''))} |"
            )
        out.append("")
        detailed = [t for t in transitions if t.get("changed_evidence") or t.get("note")]
        if detailed:
            out += ["<details><summary>Evidence behind these changes</summary>", ""]
            for t in detailed:
                out.append(f"**`{t['claim_id']}`**: {_cell(t.get('note', ''))}")
                for p in t.get("changed_evidence", [])[:10]:
                    out.append(f"- changed: `{p}`")
                if t["kind"] == "regression":
                    for m in t.get("head_missing_evidence", [])[:3]:
                        out.append(f"- missing now: {_cell(m)}")
                out.append("")
            out += ["</details>", ""]

    unchanged = _unchanged_count(report)
    if unchanged:
        out += [f"{unchanged} claim(s) unchanged and unaffected by this change.", ""]
    out.append(
        "_Advisory: statuses come from static analysis. They are not a merge gate "
        "or proof of runtime behavior._"
    )
    return "\n".join(out)
