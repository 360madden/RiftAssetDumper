# Handoff — NiDataStream descriptor/sample-byte comparison

Date: 2026-05-25

## Goal

Add a compact, machine-readable report that joins candidate-only Ghidra descriptor-helper evidence with copied-sample `NiDataStream` byte-counter evidence, without changing parser/export behavior.

## What changed

- Added `nidatastream-descriptor-sample-compare` to the Python workflow and PowerShell wrapper alias map.
- Added ignored JSON/Markdown output:
  - `Exports/nidatastream-descriptor-sample-compare.json`
  - `Exports/nidatastream-descriptor-sample-compare.md`
- Added schema `docs/schemas/nidatastream-descriptor-sample-compare-v1.schema.json`.
- Included the new compare artifacts in `nidatastream-evidence-status`.
- Added regression coverage for:
  - command wiring,
  - schema validation,
  - parser/export promotion lock rejection,
  - descriptor field-order promotion lock rejection,
  - ignored report writing.
- Updated the Ghidra/NiDataStream docs and promotion checklist to use the new comparison command.

## Evidence / validation

- `python -m py_compile scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py scripts/test_rift_workflow_command_wiring.py scripts/test_schema_registry.py`
- Full Python smoke suite: `foreach ($test in Get-ChildItem scripts/test_*.py | Sort-Object Name) { python $test.FullName }`
- `ruff check scripts/rift_workflow.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_nidatastream_promotion_status.py scripts/test_rift_workflow_command_wiring.py scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py nidatastream-descriptor-sample-compare`
- `python scripts/rift_workflow.py nidatastream-promotion-preflight`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

Current local ignored evidence after the compare run:

- Descriptor helper evidence: `4/4`
- Layout Ghidra-style-valid sample blocks: `184/184`
- Descriptor/sample uniform byte checks: `6/6`
- Evidence artifacts listed by `nidatastream-evidence-status`: `24/24`
- Parser/export promotion: still locked (`ParserExportPromotionAllowed=false`, `FieldOrderPromoted=false`)

## Known blockers / guardrails

- This is still candidate-only evidence.
- The command confirms descriptor/sample agreement at the current counter level, not exact byte-level descriptor field order.
- Pairing impact remains report-only with `0` complete position+normal+UV Ghidra-only groups in the current grouped candidate baseline.
- No parser/export behavior should change until a separate narrow proof patch passes promotion gates.

## Generated output status

Generated ignored files were refreshed under `Exports/`. They remain local/generated and must not be staged or committed.

## Next recommended actions

1. Add an exact descriptor byte-order proof table when Ghidra/sample evidence can support it.
2. Add a negative fixture for descriptor/sample compare mismatch.
3. Add the compare command to any future promotion preflight expansion only if it stays report-only.
4. Keep pairing-impact and export-isolation guards blocking parser/export promotion.
