# NiDataStream parser/export promotion decision template

Date: 2026-05-25

## Goal

Add a reusable decision-record template for any future NiDataStream parser/export behavior change so promotion decisions cannot skip evidence gates, negative checks, or rollback planning.

## What changed

- Added `docs/nidatastream-parser-export-promotion-decision-template.md`.
- Linked it from:
  - `docs/nidatastream-promotion-readiness-checklist.md`
  - `docs/ai-driven-workflow.md`
- The template requires current-truth commands, gate evidence, negative checks, parser/export tests, rollback plan, and final decision status.

## Evidence / validation

```powershell
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Result: passed.

## Generated outputs

No copied RIFT assets or generated reports were staged.

## Known blockers

- Documentation-only. Parser/export behavior remains unchanged and promotion remains blocked.

## Next recommended actions

1. Add stale-evidence timestamp/status reporting if ignored reports become hard to trust.
2. Keep using the preflight command before any parser/export patch.
3. Do not fill the template in place; copy it into a dated handoff/decision record.
