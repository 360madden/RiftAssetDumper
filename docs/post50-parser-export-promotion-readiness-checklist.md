# Post-50 parser/export promotion readiness checklist

Status: **not ready / candidate-only**

This checklist is the durable gate for any future parser/export change based on
post-50 position-source evidence.

## Current status snapshot

Run before any decision:

```powershell
python scripts/rift_workflow.py post50-position-source-status --list-json
python scripts/rift_workflow.py generated-output-guard
```

Current expected posture:

| Gate | Required before promotion | Current status |
|---|---|---|
| All post-50 reports schema-backed | yes | ✅ all current inputs report `EvidenceLevel=schema-backed-candidate` |
| Candidate-only reports present | yes | ✅ 8/8 current inputs present locally |
| mesh329 family proof | required | ✅ candidate-only proof exists |
| mesh329 mesh#34 extra compare | required | ✅ candidate-only compare exists |
| mesh#34 complete binding | required | ❌ missing |
| residual classifier strict pass | required for residual promotion | ❌ strict pass false |
| residual cluster complete binding | required for residual promotion | ❌ missing |
| parser/export promotion allowed | must be explicitly true | ❌ false |

## Promotion blockers that must be cleared

The current blockers are intentional:

- `mesh329-family-proof-candidate-only`
- `mesh329-extra-position-like-stream-candidate-only`
- `mesh329-source-binding-compare-export-blocked`
- `mesh34-complete-geometry-binding-not-proven`
- `residual-position-strict-threshold-not-met`
- `residual-cluster-no-complete-geometry-binding`
- `mesh325-position-source-sparse-no-residuals`
- `parser-export-promotion-not-allowed`

## Required decision record before code changes

Before changing parser/export behavior, create a dated decision handoff under
`docs/handoffs/` that includes:

1. Exact `post50-position-source-status --list-json` summary.
2. The proof packet names and schema versions used.
3. A before/after explanation of parser/export behavior.
4. A generated-output safety statement.
5. Targeted tests proving the new behavior.
6. Non-consumption guard updates, if candidate fields are promoted.
7. A rollback plan.

## Current decision

No parser/export promotion is allowed from the current evidence. The practical
next work is more proof/report hardening, not decode/export behavior changes.
