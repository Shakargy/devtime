# Reality Validation - Snapilio

Repo: Snapilio (local, Next.js App Router + SST, TS)
Commands run: `dtc init`, `dtc scan`, `dtc concepts`, `dtc explain` (x6)
Files scanned: 186
Signals extracted: 649
Concepts detected: Authentication, Admin Permissions, Billing Webhooks, File Uploads, Data Export (5)

Best output:
- **Admin Permissions** - plausible. Evidence `app/admin/layout.tsx`, `lib/actions/admin.ts`, `app/admin/coupons/page.tsx`. Reasonable concept from path + action clustering. Still weak (no behavior/route), honest debt (high).
- **Billing Webhooks** naming is actually right here: `app/api/paypal/webhook/route.ts` is a real billing webhook - but see below, it was detected only as weak "dependency".

Worst output:
- **Every concept degraded to "has related dependencies present"** because no routes were detected. Snapilio is Next.js App Router (file-based `route.ts` with `export async function POST/GET`). The route extractor only understands Express/FastAPI, so it found zero routes in a repo full of API routes.

Wrong claim:
- None outright fabricated at the claim level (the weak "dependencies present" claims are honestly labeled), but confidence is propped up by path/doc keyword matches rather than behavior.

Missing concept:
- No concept is badly missing, but all are under-evidenced.

Bad evidence:
- **Double-slash path bug**: evidence shows `app/api/g//download-all/route.ts` and `app/api/app-upload//albums/route.ts` - a `//` artifact in displayed paths.
- Cross-contamination: `lib/actions/coupons.ts` cited as **Authentication** evidence (coupons is not auth; likely matched a `session` import).

Missing uncertainty:
- DevTime should note "no API route handlers were parsed (framework not recognized)" so the user understands why evidence is thin. Instead it silently falls back to dependencies.

Unsupported confidence:
- Authentication 0.68 concept "present" from `package.json` + an auth layout file, with no parsed auth behavior.

Privacy or ignore issue:
- None. `.devtime` created and removed; `.gitignore`/SST build output respected.

Risk review usefulness:
- Not exercised (no relevant diff).

New fixture needed:
5. `nextjs-app-router-routes` - `app/api/**/route.ts` with `export async function GET/POST/...` must produce route signals (path derived from directory).
6. `evidence-path-no-double-slash` - displayed/stored evidence paths must be normalized (no `//`).
7. `paypal-webhook-is-billing` - a PayPal/Stripe webhook route should be Billing Webhooks with route+behavior evidence, not weak dependency-only.

Fix priority:
- P0: Next.js route detection (#5) - affects two of three real repos.
- P1: path normalization (#6).

Notes:
- Snapilio is the clearest evidence that DevTime currently "can't see" the most common TS API stack. Fixing Next.js routing lifts Authentication, Billing, Data Export, File Uploads simultaneously.
