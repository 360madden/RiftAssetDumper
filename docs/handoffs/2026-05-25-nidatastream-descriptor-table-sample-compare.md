# Handoff — NiDataStream descriptor table sample comparison

Date: 2026-05-25

## Goal

Add a compact candidate-only comparison for known descriptor-table sample reports so the workflow can avoid stale single-report conclusions and see default, all-index, and stride-override evidence together.

## What changed

- Added `nidatastream-descriptor-table-sample-compare`.
- Added PowerShell alias wiring: `NiDataStreamDescriptorTableSampleCompare`.
- Added schema `docs/schemas/nidatastream-descriptor-table-sample-compare-v1.schema.json`.
- Added routing/schema tests using mixed nonzero/all-zero fixture reports.
- Documented compare usage in `docs/ai-driven-workflow.md`.

## Evidence / validation

- `python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_ghidra_runner.py`
- `python scripts/test_rift_workflow_command_wiring.py`
- `python scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py nidatastream-descriptor-table-sample-compare --list-json`

Current retained local comparison:

| Report | Exists | Rows | Nonzero rows | All rows zero |
|---|---:|---:|---:|---:|
| `all-indices-stride12` | true | 768 | 0 | true |
| `observed-indices-default` | true | 15 | 0 | true |
| `all-indices-stride4` | true | 768 | 0 | true |

Current blockers:

- `descriptor-table-sample-compare-all-existing-reports-zero`
- `descriptor-table-sample-compare-no-nonzero-reports`
- `descriptor-table-sample-compare-semantics-unmapped`

## Generated outputs

No new generated outputs were created by this slice. The compare command reads ignored local evidence and writes nothing.

Relevant ignored reports:

- `Exports/ghidra-reports/nidatastream_descriptor_table_all_indices.json`
- `Exports/ghidra-reports/nidatastream_descriptor_table_samples.json`
- `Exports/ghidra-reports/nidatastream_descriptor_table_all_indices_stride4.json`

## Known blockers / remaining uncertainty

- All retained descriptor-table sample reports are readable but zero-valued, so they block parser/export promotion from these candidate bases/strides.
- This comparison does not yet include reference-classification instruction operand summaries or neighborhood-scan metadata in the same packet.
- No parser/export behavior was changed.

## Next recommended actions

1. Add a candidate-only instruction operand query-plan generator from reference-classification scale/offset evidence.
2. Include reference-classification and neighborhood-scan summaries in the next higher-level descriptor dashboard.
3. Keep table evidence candidate-only until a nonzero, sample-correlated semantic mapping exists.
