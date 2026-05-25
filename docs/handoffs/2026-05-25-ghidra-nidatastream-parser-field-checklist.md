# 2026-05-25 Ghidra NiDataStream parser-field checklist handoff

## Goal

Turn the NiDataStream Ghidra/parser comparison note into a concrete promotion checklist so future agents do not accidentally treat candidate-only field evidence as parser/export truth.

## What changed

- Added a parser-field promotion checklist to `docs/ghidra-nidatastream-parser-field-comparison.md`.
- The checklist separates guarded items from partial/report-only items and hard blockers.
- Linked the new handoff from `docs/ai-driven-workflow.md` current Ghidra lane state.

## Why it matters

The comparison doc previously explained the field mismatch and current decision, but it did not provide a gate-by-gate checklist for promotion. The new checklist makes the next decoder-related work explicit: target registry safety and export isolation are guarded; descriptor field order, sample-byte agreement, and pairing impact remain candidate/report-only; parser/export behavior stays blocked.

## Evidence / validation

Validation for this docs-only slice:

```powershell
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

The checklist also references already-validated commands from the previous slice:

```powershell
python scripts/rift_workflow.py ghidra-function-site-target-guard
python scripts/rift_workflow.py ghidra-function-site-status --list-json
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
```

## Known blockers / limits

- No parser/export behavior changed.
- Descriptor field order is still candidate-only until a future serialized Ghidra target run plus parser-side sample proof makes it guardable.
- `ghidra-attribute-candidate-guard` still expects zero complete Ghidra-only position+normal+UV groups.

## Generated-output handling

No generated report files were created, staged, or committed in this docs-only slice.

## Next recommended actions

1. Add an aggregate schema validation smoke test for tracked Ghidra JSON docs and schemas.
2. Refresh missing Markdown summaries for existing FunctionSiteSurvey reports if the retained Ghidra project is available.
3. Run one serialized descriptor-helper target only when the retained project is available and unlocked.
4. Keep decoder/export promotion blocked until the checklist has green proof gates.
