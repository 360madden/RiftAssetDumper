# 2026-05-26 Post-50 promotion-readiness checklists handoff

## Goal

Convert the current schema-backed post-50 evidence into explicit non-promotion
guardrails so future parser/export work has clear gates.

## What changed

- Added `docs/post50-mesh34-negative-binding-proof-checklist.md`.
- Added `docs/post50-parser-export-promotion-readiness-checklist.md`.

## Why it matters

The repo now has schema-backed reports for the current post-50 lanes, but
schema-backed candidate evidence is still not export truth. These checklists
make the promotion blockers durable and reviewable:

- mesh#34 `@304/#57` is repeatable but lacks complete binding.
- residual meshSize `305` remains below strict classifier threshold.
- parser/export promotion stays locked until a dated decision record and guard
  updates exist.

## Validation

- `python scripts/rift_workflow.py post50-position-source-status --list-json`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

## Generated-output status

No generated output was staged. The checklists are tracked documentation only.

## Next recommended actions

1. Add a tiny Markdown-link smoke check if docs link drift becomes a recurring
   issue.
2. Keep schema-backed report refreshes separate from parser/export promotion.
3. Use the readiness checklist before any decode/export behavior change.
