# DevTime v0.3.0 - JWT claim and the docs-vs-implementation detector

Second step of the verification layer. Two changes and one honest bug fix. No
cloud, no telemetry, no AI, no code execution - unchanged.

## New built-in claim: jwt-authentication

```bash
dtc verify jwt-authentication
```

"Authentication uses JWT access tokens." Uses the JWT purpose classifier
(introduced in v0.0.6) to distinguish access tokens from invitation and
verification tokens.

## New: documentation-vs-implementation contradiction

The classic case: documentation says JWT, the code says otherwise.

```
Status: CONTRADICTED
  claimed:  docs/auth.md references JWT in a documentation or decision
            context, implying JWT-based authentication.
  observed: src/tokens/invite.ts uses JWT for invitation/verification tokens.
            Invitation tokens are not access-token authentication, and no
            access-token usage was found.
```

Honesty rule preserved: documentation with NO usage found at all is WEAK
(missing evidence), never CONTRADICTED - absence is not positive conflicting
evidence.

## Fixed: signal metadata was silently dropped at persistence

A latent V0 bug: every signal's metadata was hardcoded to `{}` when written to
the local database. Concept detection never noticed (it runs in-process on live
objects); the verification engine is the first feature that reads metadata back
from the database, and it exposed the bug. Metadata (including the JWT purpose
classification) now persists, with a regression test.

## Notes

- Two built-in claims now: billing-webhook-signature, jwt-authentication.
- Still deliberately no user-defined claim files, and no LLM in the truth path.
- 126 passing tests (6 new).
- No breaking changes.

## Names

- PyPI distribution: `devtime-ei`. Python import: `devtime`. CLI: `dtc`.
