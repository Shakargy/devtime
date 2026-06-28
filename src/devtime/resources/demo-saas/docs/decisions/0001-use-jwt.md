# 0001 - Use JWT for authentication

## Status
Accepted

## Context
We needed stateless authentication that works across multiple API instances
without shared session storage.

## Decision
Use JWT access tokens signed with a server secret, with a 1 hour expiry.

## Consequences
- No server-side session store required.
- Token revocation before expiry is not yet solved.
