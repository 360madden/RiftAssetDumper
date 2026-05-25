# NiDataStream dashboard negative fixture guards

Date: 2026-05-25

## Goal

Lock the `nidatastream-promotion-dashboard` JSON contract so dashboard output cannot silently advertise parser/export promotion, descriptor field promotion, or non-candidate status.

## What changed

- Extended `scripts/test_nidatastream_promotion_status.py` with dashboard negative schema fixtures.
- The dashboard JSON test now verifies that the existing v1 promotion-status schema rejects:
  - `ParserExportPromotionAllowed: true`,
  - `DescriptorReportStatus.FieldOrderPromoted: true`,
  - `CandidateOnly: false`.

## Evidence / validation

```powershell
python -m py_compile scripts/test_nidatastream_promotion_status.py
python scripts/test_nidatastream_promotion_status.py
ruff check scripts/test_nidatastream_promotion_status.py
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Result: all commands passed.

## Generated outputs

No copied RIFT assets or generated reports were staged. Python bytecode/cache output may have been produced locally by validation and remains ignored.

## Known blockers

- This strengthens dashboard contract tests only; it does not promote parser/export behavior.
- `ParserExportPromotionAllowed` and `FieldOrderPromoted` remain intentionally false.

## Next recommended actions

1. Add an offline Ghidra/NiDataStream quickstart that names the exact current guard sequence.
2. Keep dashboard/status schemas locked until positive parser/export proof exists.
3. Continue refreshing ignored evidence only when it answers a specific promotion question.
