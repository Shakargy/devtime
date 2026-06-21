# DevTime

DevTime builds evidence-backed repository memory.

It scans your repository locally, detects meaningful concepts, links claims to evidence,
surfaces missing decisions, and prepares Context Packs for humans and AI agents.

## Quickstart

```
dtc init
dtc scan
dtc concepts
dtc explain Authentication
dtc context "Billing Webhooks" --mode risk
dtc risk --diff
```

## Trust model

- Local-first by default.
- AI optional.
- Cloud disabled by default.
- No source upload required.
- Telemetry off or explicit.

## Core law

No claim without evidence.

---

*Git remembers code. DevTime remembers understanding.*
