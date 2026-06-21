# Reality Validation — SaaSVoice

Repo: SaaSVoice (local, Next.js App Router + SST, TS)
Commands run: `dtc init`, `dtc scan`, `dtc concepts`, `dtc explain`, route inventory
Files scanned: 125
Signals extracted: 508
Concepts detected: Authentication, File Uploads, Background Jobs, Data Export (4)

Best output:
- **Authentication** is at least present, anchored on `src/app/(auth)/layout.tsx` + `package.json`. But it missed the actual auth handler.

Worst output:
- **NextAuth route handler completely missed.** The repo has `src/app/api/auth/[...nextauth]/route.ts` (NextAuth), plus `api/posts/route.ts`, `api/posts/export/route.ts`, `api/posts/[id]/approve/route.ts`, `api/github/commits/route.ts` — and DevTime detected **zero routes**. Authentication should have been a high-confidence, route-and-behavior-backed concept; instead it is weak dependency-only. Billing/Admin not detected at all.

Wrong claim:
- None fabricated, but the picture is materially incomplete: a NextAuth app reported with no auth route evidence understates what is knowable.

Missing concept:
- **Data Export** exists as `api/posts/export/route.ts` but was only weakly detected; **Billing** and **Admin** routes not surfaced as concepts.

Bad evidence:
- Authentication leans on `package.json` (dependency) rather than the real `[...nextauth]/route.ts` handler.

Missing uncertainty:
- Same as Snapilio: no signal that the API framework was unrecognized.

Unsupported confidence:
- Low overall; the tool is honest that evidence is thin (good), but it is thin only because detection missed the framework.

Privacy or ignore issue:
- None. `.devtime` created and removed.

Risk review usefulness:
- Not exercised.

New fixture needed:
8. `nextauth-route-is-authentication` — `api/auth/[...nextauth]/route.ts` must be Authentication route evidence.
9. `package-json-dep-alone-is-weak` — a concept supported ONLY by a `package.json` dependency must stay weak/low-confidence and carry uncertainty (presence is not behavior).
10. `dynamic-segment-route-path` — routes under dynamic segments (`[id]`, `[...nextauth]`) must parse without producing malformed paths.

Fix priority:
- P0: Next.js App Router detection (shared with Snapilio).
- P1: keep dependency-only concepts weak + uncertain.

Notes:
- Two independent real repos (SaaSVoice + Snapilio) fail the same way. This is the strongest signal in the whole validation pass: Next.js App Router support is the highest-leverage correctness fix.
