# Handoff — NiDataStream descriptor table stride override

Date: 2026-05-25

## Goal

Add a safe candidate-only way to resample the Ghidra descriptor table with an explicit stride from the base-model review, then run a stride-4 all-index check without touching parser/export behavior.

## What changed

- Added `--descriptor-table-stride <bytes>` to `nidatastream-descriptor-table-sample`.
- Kept the default behavior on the existing candidate field-map stride (`12` bytes).
- Added plan metadata that distinguishes `StrideSource: candidate-field-map`, `override`, or `ambiguous-candidate-field-map`.
- Added routing tests for:
  - stride override value,
  - computed-address recalculation,
  - invalid negative stride blocker,
  - default Ghidra script argument still using stride `12`.
- Documented the override as an explicit candidate-resampling tool, not a promotion path.

## Evidence / validation

- `python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_ghidra_runner.py`
- `python scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py nidatastream-descriptor-table-sample --descriptor-table-stride 4 --descriptor-table-all-byte-indices --list-json`
- Actual retained-project Ghidra execution:
  - `python scripts/rift_workflow.py nidatastream-descriptor-table-sample --descriptor-table-stride 4 --descriptor-table-all-byte-indices --descriptor-table-report Exports/ghidra-reports/nidatastream_descriptor_table_all_indices_stride4.json --descriptor-table-summary Exports/ghidra-reports/nidatastream_descriptor_table_all_indices_stride4.md --ghidra-execute`

Actual stride-4 Ghidra result:

- Schema: `ghidra-descriptor-table-sample/v1`
- Candidate-only: `true`
- Parser/export promotion allowed: `false`
- Stride: `4`
- Fields: `3`
- Indices: `256`
- Rows: `768`
- Nonzero rows: `0`
- Skipped rows: `0`

## Generated outputs

Generated/updated ignored local evidence:

- `Exports/ghidra-reports/nidatastream_descriptor_table_all_indices_stride4.json`
- `Exports/ghidra-reports/nidatastream_descriptor_table_all_indices_stride4.md`

Both files remain ignored by `.gitignore` via `Exports/`.

## Known blockers / remaining uncertainty

- The stride-4 all-index resample also produced all-zero bytes, so it does not support parser/export promotion.
- `nidatastream-descriptor-table-sample-status` still reports the default retained table-sample path and does not summarize alternate explicit-stride report files yet.
- The current evidence still points away from "static bytes at candidate data references contain the stream semantic table"; the next useful lane is to correlate the indexed instruction operands and candidate descriptor byte values without changing parser behavior.

## Next recommended actions

1. Add a compact status/compare hook for alternate descriptor-table sample reports such as the stride-4 resample.
2. Compare stride-12, stride-4, neighborhood-scan, and reference-classification evidence in one candidate-only dashboard section.
3. Derive operand-scale/offset candidates from reference-classifier instruction text and use them to generate the next bounded Ghidra query plan.
4. Keep parser/export promotion blocked until a nonzero, schema-validated, sample-correlated mapping exists.
