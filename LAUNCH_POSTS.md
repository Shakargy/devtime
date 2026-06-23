# Launch Posts (drafts)

Draft copy for the public launch. Honest, no hype. Pick/edit before posting.

Links:
- Demo video (live): **https://youtu.be/1Hiu3Y9J_SI**
- GitHub: **https://github.com/Shakargy/devtime** — *use only after the repo is public.*

> Avoid: "revolutionary", "game-changing", "replaces developers", "AI understands your
> repo", "fully autonomous", "perfect". DevTime requires no AI and makes no such claims.

## 1. X / Twitter (short)

> DevTime: a local-first CLI that helps a codebase explain itself **from evidence**.
>
> It detects concepts, links every claim to files, and shows what the repo **can't**
> prove yet. Uncertainty is a feature, not a bug.
>
> No cloud. No telemetry. No code execution. No AI required.
>
> https://youtu.be/1Hiu3Y9J_SI

Alt one-liner:
> AI writes. EI remembers. DevTime is local-first repository memory from evidence —
> no cloud, no telemetry, no code execution, no AI required. https://youtu.be/1Hiu3Y9J_SI

## 2. LinkedIn

> **DevTime — repository memory from evidence**
>
> Git remembers code. It doesn't remember *understanding* — why a behavior exists,
> what evidence supports it, or what nobody has decided yet. As AI tools generate code
> faster than teams can review it, that missing understanding becomes the bottleneck.
>
> DevTime is a local-first CLI that scans a repository and helps it explain itself from
> evidence: it detects concepts, links each claim to the files behind it, surfaces
> uncertainty when reasoning is missing, and gives an advisory, narrow risk review of a
> diff. Every claim links to evidence; weak evidence produces uncertainty, not
> confidence.
>
> What it is **not**: it doesn't execute your code, send anything to the cloud, use
> telemetry, or require AI. It's a heuristic tool with a closed set of concept families
> in V0 — and it's honest about its limits.
>
> No cloud. No telemetry. No code execution. No AI required. Apache-2.0.
>
> Try it on one repo and tell me what it gets wrong: https://youtu.be/1Hiu3Y9J_SI (GitHub link after the repo is public)

## 3. Hacker News / Reddit-style intro

> **Show: DevTime — a local-first CLI that helps a repo explain itself from evidence**
>
> I built DevTime because Git remembers code but not *understanding* — why something
> exists, what evidence supports it, what nobody decided yet.
>
> DevTime scans a repository locally (no network, no code execution) into a local
> SQLite store, detects a small set of concepts (Authentication, Billing Webhooks,
> Background Jobs, …), links every claim to the files behind it, and **shows
> uncertainty** when the reasoning isn't there. It can review a git diff for a narrow
> set of risky changes (advisory only), and it produces governed "Context Packs" for
> humans and agents.
>
> Design choices I care about:
> - Evidence decides. No claim without evidence; weak evidence → uncertainty.
> - Local-first: no cloud, no telemetry, no code execution, no AI required.
> - Honest about limits: a heuristic scanner with a closed six-concept ontology in V0,
>   not a compiler and not a security tool.
> - "Uncertainty is a feature, not a bug." It shows what the repo can prove — and what
>   it can't prove yet.
>
> It's Apache-2.0. I validated it privately on several large real repos and turned the
> wrong outputs into regression fixtures. Feedback — especially "it got this wrong" —
> is exactly what I'm looking for.
>
> Demo: https://youtu.be/1Hiu3Y9J_SI · GitHub: https://github.com/Shakargy/devtime (after public)

---

## Private soft-launch message (5–10 reviewers / friends)

> Hey — I'd love your eyes on **DevTime** before I make it public. It's a local-first
> CLI that helps a repo explain itself from evidence (no cloud, no telemetry, no code
> execution, no AI). ~15 minutes:
>
> 1. Clone the repo: `https://github.com/Shakargy/devtime` (private — request access)
> 2. Follow **QUICKSTART.md** (install + `pytest`).
> 3. Watch the 2-minute demo video.
> 4. Run it on **one real repo** of yours: `dtc init && dtc scan && dtc concepts` then
>    `dtc explain "<a concept>"`.
> 5. If it gets anything wrong, open a **"DevTime got this wrong"** issue (there's a
>    template). Wrong outputs are the most useful thing you can give me — they become
>    regression fixtures.
>
> No pressure to be thorough — even one "this concept is wrong" report helps. Thanks!
