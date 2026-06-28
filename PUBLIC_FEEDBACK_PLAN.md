# Public Feedback Plan

Five GitHub issues to open after the v0.1.1 onboarding PR merges. These are drafts -
do not open them automatically. They seed a public backlog and invite contribution.

---

## 1. Improve first-run install flow

**Why it matters:** Right now install is `git clone` + `pip install -e ".[dev]"`,
which is fine for contributors but heavy for someone who just wants to try the tool.
A one-line install would meaningfully raise the number of people who actually run it.

**Suggested scope:**
- Investigate publishing to PyPI so `pip install devtime` / `pipx install devtime` works.
- Keep the editable dev install documented for contributors.
- Update README install instructions and badges once available.

**What not to do yet:** Do not change CLI behavior, commands, or scan logic. Packaging
only.

---

## 2. Add clearer line-number evidence

**Why it matters:** Evidence currently cites files; pointing to the specific
route/handler/line would make claims easier to audit and trust.

**Suggested scope:**
- Capture and surface start/end lines where the extractors already have them.
- Show line ranges in `dtc explain` and `dtc evidence` output.

**What not to do yet:** Do not expand the concept ontology or change detection. This
is presentation/precision of existing evidence, not new detection.

---

## 3. Add more real-world fixtures

**Why it matters:** DevTime gets more trustworthy as more real wrong/right outputs
become fixtures. Community repos are the best source.

**Suggested scope:**
- Add fixtures from frameworks and patterns not yet covered.
- Prioritize "DevTime got this wrong" reports from real users.

**What not to do yet:** Do not loosen the trust gates to make a repo pass. A fixture
should pin correct behavior, not paper over a bug.

---

## 4. Design GitHub Action advisory PR review

**Why it matters:** Running `dtc risk --diff` in pull requests is the natural team
on-ramp, and it stays advisory (the project's trust stance).

**Suggested scope:**
- Prototype an Action that runs `dtc init`, `dtc scan`, `dtc risk --diff` on a PR.
- Post advisory comments only.

**What not to do yet:** No blocking by default. No blocking on weak claims. No cloud
service. Keep it advisory and opt-in.

---

## 5. Improve README "why this matters" section

**Why it matters:** The clearer the problem framing (Git remembers code, not
understanding), the more a stranger self-identifies and tries the tool.

**Suggested scope:**
- Tighten the problem statement and the "Who it is for" examples.
- Consider an inline animated terminal demo at the top.

**What not to do yet:** Do not overclaim, do not imply AI/automation, and keep the
no-cloud/no-telemetry/no-code-execution/no-AI language.
