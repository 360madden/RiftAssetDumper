# NiDataStream/Ghidra schema policy

Date: 2026-05-25

## Goal

Document schema-change rules for promotion-critical NiDataStream/Ghidra workflow outputs so future status/dashboard/schema changes stay fail-closed.

## What changed

- Added `docs/nidatastream-ghidra-schema-policy.md`.
- Linked the policy from:
  - `docs/nidatastream-promotion-readiness-checklist.md`
  - `docs/ai-driven-workflow.md`
- The policy captures candidate-only requirements, negative-fixture expectations, v2 schema rules, and parser/export promotion prerequisites.

## Evidence / validation

```powershell
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Result: passed.

## Generated outputs

No copied RIFT assets or generated reports were staged.

## Known blockers

- Documentation-only; no schema contract or parser/export behavior was changed.

## Next recommended actions

1. Keep any future schema loosening paired with explicit negative fixture updates.
2. Avoid schema v2 until a real incompatible output change is required.
3. Continue using status/dashboard schemas as promotion brakes.
