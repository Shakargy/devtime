# DevTime v0.4.0 - diff-aware claim impact

A pull request should tell you which verified claims it destabilizes. Now it
does. No cloud, no telemetry, no AI, no code execution - unchanged.

## dtc risk --diff now reports claim impact

```
Claim impact:
  - billing-webhook-signature (previous status: SUPPORTED)
      changed evidence: src/billing/stripe-webhook.ts
      re-verify: dtc verify billing-webhook-signature
```

The rules:

- Only a claim's recorded evidence files count. A diff touching unrelated
  files never flags a claim.
- Nothing is printed when no verified claim is affected. Advisory, never noisy.
- The output names the exact changed evidence and the exact command to
  re-verify.

This connects the verification layer (v0.2, v0.3) to the risk layer: risk
review says "this change class needs review"; claim impact says "this specific
verified claim may no longer hold, check it."

## Notes

- 129 passing tests (3 new: affected claim reported with previous status and
  changed evidence; unrelated diffs affect nothing; no verifications means no
  impact output).
- No breaking changes. Risk output gains a section only when relevant.

## Names

- PyPI distribution: `devtime-ei`. Python import: `devtime`. CLI: `dtc`.
