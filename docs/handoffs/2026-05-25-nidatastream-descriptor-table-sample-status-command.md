# Handoff — NiDataStream descriptor table sample status command

Date: 2026-05-25

## Goal

Wire a machine-readable status command for descriptor-table sample reports so the workflow can inspect default retained evidence or explicit alternate reports such as stride-override resamples.

## What changed

- Added `nidatastream-descriptor-table-sample-status`.
- Added PowerShell alias wiring: `NiDataStreamDescriptorTableSampleStatus`.
- Added schema `docs/schemas/nidatastream-descriptor-table-sample-status-v1.schema.json`.
- Added routing/schema tests for explicit report-path status output.
- Documented status usage in `docs/ai-driven-workflow.md`.

## Evidence / validation

- `python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_ghidra_runner.py`
- `python scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py nidatastream-descriptor-table-sample-status --descriptor-table-report Exports/ghidra-reports/nidatastream_descriptor_table_all_indices_stride4.json --list-json`

Current explicit stride-4 status result:

- Schema: `nidatastream-descriptor-table-sample-status/v1`
- Exists: `true`
- Rows: `768`
- Nonzero rows: `0`
- All rows zero: `true`
- Blockers: `descriptor-table-sample-all-zero`, `descriptor-table-sample-semantics-unmapped`

## Generated outputs

No new generated outputs were created by this slice. The command reads ignored local evidence and writes nothing.

Previously generated stride-4 evidence remains ignored:

- `Exports/ghidra-reports/nidatastream_descriptor_table_all_indices_stride4.json`
- `Exports/ghidra-reports/nidatastream_descriptor_table_all_indices_stride4.md`

## Known blockers / remaining uncertainty

- The status command makes alternate reports inspectable, but promotion remains blocked because the stride-4 report is all zero and semantics are unmapped.
- The broader promotion dashboard still summarizes the default table sample path unless an explicit report path is passed through workflows that support it.
- No parser/export behavior was changed.

## Next recommended actions

1. Add a compact multi-report table-sample comparison that reads stride-12 default, stride-4 override, neighborhood scan, and reference classification together.
2. Use the comparison to rank the next bounded Ghidra query plan from instruction-derived scale/offset candidates.
3. Keep all table evidence candidate-only until a nonzero, sample-correlated semantic mapping exists.
