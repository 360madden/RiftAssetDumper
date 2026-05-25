# Ghidra/NiDataStream offline quickstart

Date: 2026-05-25

## Goal

Document the practical offline/static Ghidra + NiDataStream workflow so future agents can refresh candidate evidence without live game interaction or generated-output risk.

## What changed

- Added `docs/ghidra-nidatastream-offline-quickstart.md`.
- Linked the quickstart from `docs/ai-driven-workflow.md`.
- The quickstart captures:
  - tool status and Ghidra dry-run checks,
  - target registry/list/status flow,
  - serialized target execution pattern,
  - descriptor proof status,
  - local sample-byte layout refresh,
  - pairing-impact guard sequence,
  - promotion-brake command sequence,
  - promotion prerequisites.

## Evidence / validation

```powershell
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Result: passed.

## Generated outputs

No copied RIFT assets or generated reports were staged.

## Known blockers

- This is documentation only; it does not refresh ignored Ghidra reports or promote parser/export behavior.
- Live game interaction remains outside this workflow.

## Next recommended actions

1. Add a future-schema policy note for NiDataStream/Ghidra promotion payloads.
2. Refresh ignored reports only when answering a specific evidence question.
3. Keep parser/export promotion blocked until all documented gates have positive proof.
