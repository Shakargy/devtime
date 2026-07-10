# DevTime v0.2.0 - claim verification (experimental)

DevTime's next step: the verification layer for repository understanding.
Instead of only detecting concepts, DevTime can now verify a claim about the
repository and answer with a status, evidence, both-sided contradictions,
missing evidence, and freshness. No cloud, no telemetry, no AI, no code
execution - unchanged.

## New: dtc verify

```bash
dtc verify                       # verify all built-in claims
dtc verify billing-webhook-signature
dtc verify --list                # claims with last status and freshness
dtc verify billing-webhook-signature --json
```

Statuses: SUPPORTED, WEAK, CONTRADICTED, UNKNOWN. Statuses mean "per DevTime's
evidence rules", not formal proof.

Freshness is separate from truth: FRESH, STALE (an evidence file changed since
verification; only evidence files count, unrelated changes never flag), and
NEEDS_VERIFICATION.

## Contradictions show both sides, always

Found in the wild on Cal.com: the community edition ships
`pages/api/stripe/webhook.ts` as a handler that always returns 404. The file
name claims webhook handling; the implementation is a disabled stub.

```
Status: CONTRADICTED
  claimed:  apps/web/pages/api/stripe/webhook.ts is named and routed as a
            billing webhook endpoint, which implies webhook handling.
  observed: The handler's only behavior is a 404/501 response; no webhook
            processing or signature verification path exists in this snapshot.
```

## New MCP tool: verify_claim

Coding agents can ask whether the repository supports a claim and get bounded,
structured, evidence-linked output. Computed fresh, never persisted: the MCP
server stays read-only.

## Scope, deliberately narrow

- One built-in claim: billing-webhook-signature.
- No user-defined claim files yet. The claim model must earn trust on real
  repositories before it grows a configuration language.
- Rule-driven and deterministic. An LLM never decides truth.

See VERIFICATION.md for the full model and limitations.

## Compatibility

- No breaking changes. All existing commands, concepts, output, and the three
  existing MCP tools are unchanged.
- Existing local databases are upgraded lazily (one new table, created on
  first use; no migration required).
- Disabled-endpoint stubs (handlers whose only behavior is 404/501) are now
  recorded as facts and used as contradiction evidence; they still never count
  as routes for concept detection.

## Names

- PyPI distribution: `devtime-ei`. Python import: `devtime`. CLI: `dtc`.

## Notes

- 120 passing tests (13 new for verification: all four statuses, both-sided
  contradictions, freshness transitions, unrelated-change resistance,
  determinism, CLI, JSON schema, MCP).
- Verified end to end on Cal.com: the claim reports CONTRADICTED with both
  stub endpoints cited by exact path.
