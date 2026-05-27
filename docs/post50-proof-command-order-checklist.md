# Post-50 proof command order checklist

Status: **candidate-only workflow checklist**

Use this order when refreshing or validating the post-50 offline discovery lane. All generated JSON/Markdown outputs go under ignored `Exports/` and must not be staged.

## Refresh/proof order

```powershell
python scripts/rift_workflow.py post50-mesh329-family-proof
python scripts/rift_workflow.py post50-mesh329-source-binding-compare
python scripts/rift_workflow.py post50-mesh34-complete-binding-negative-proof
python scripts/rift_workflow.py post50-residual-strict-threshold-delta
```

## Status/order checks

```powershell
python scripts/rift_workflow.py post50-position-source-status --list-json
python scripts/rift_workflow.py post50-mesh34-negative-binding-status --list-json
python scripts/rift_workflow.py post50-promotion-readiness-status --list-json
python scripts/rift_workflow.py post50-validation-suite --list-json
python scripts/rift_workflow.py generated-output-guard
```

## Required current posture

| Check | Expected current result |
|---|---|
| Post-50 report count | `10/10` schema-backed candidate reports locally |
| Parser/export promotion | `false` |
| mesh#34 `@304/#57` | repeatable negative-binding evidence, not geometry truth |
| Residual payload `288` | best residual candidate, but `0.0056` below strict threshold |
| Generated outputs | ignored under `Exports/`; never staged |

## Promotion rule

Do not change parser/export behavior from these reports unless a future dated handoff records positive complete geometry-binding proof, guard updates, targeted tests, and a rollback plan.
