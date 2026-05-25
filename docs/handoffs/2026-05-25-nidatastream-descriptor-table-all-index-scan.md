# Handoff — NiDataStream descriptor-table all-index scan

Date: 2026-05-25

## Goal

Add a practical bounded all-byte-index scan for candidate descriptor-table bases and run it against the retained Ghidra project to test whether any one-byte descriptor index yields nonzero static-table bytes.

## What changed

- Added `--descriptor-table-all-byte-indices` to `nidatastream-descriptor-table-sample`.
- The all-index plan samples all 256 one-byte indices across the three candidate descriptor-table fields.
- `DescriptorTableSampleStatus` now prefers `Exports/ghidra-reports/nidatastream_descriptor_table_all_indices.json` when it exists, otherwise it falls back to the observed-index default report.
- Added tests for all-index planning and all-index status preference.

## Evidence observed

Command run against the retained Ghidra project:

```powershell
python scripts/rift_workflow.py nidatastream-descriptor-table-sample --descriptor-table-all-byte-indices --descriptor-table-report Exports/ghidra-reports/nidatastream_descriptor_table_all_indices.json --descriptor-table-summary Exports/ghidra-reports/nidatastream_descriptor_table_all_indices.md --ghidra-execute
```

Result:

| Metric | Value |
|---|---:|
| Fields | 3 |
| Indices | 256 |
| Rows | 768 |
| Nonzero rows | 0 |
| Error rows | 0 |
| Address span | `143358be0` through `1433597dc` |

Per-field result:

| Field | Rows | Nonzero rows | First address | Last address |
|---|---:|---:|---|---|
| `descriptor-enable-or-special-flag` | 256 | 0 | `143358be0` | `1433597d4` |
| `descriptor-component-class` | 256 | 0 | `143358be4` | `1433597d8` |
| `descriptor-format-size-lookup` | 256 | 0 | `143358be8` | `1433597dc` |

## Interpretation

The all-index scan is stronger than the observed-index-only sample: every candidate entry in the current stride-12/base-address model is readable and zero. This strongly suggests the current candidate static addresses are not the raw descriptor semantics table needed to explain stream descriptor bytes 1-2. Keep the evidence candidate-only and treat it as a fail-closed blocker, not as parser truth.

## Validation / safety

Validated in this stage:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/test_ghidra_runner.py
python scripts/test_nidatastream_descriptor_sample_compare.py
python scripts/rift_workflow.py nidatastream-descriptor-table-sample --descriptor-table-all-byte-indices --list-json
python scripts/rift_workflow.py nidatastream-descriptor-table-sample --descriptor-table-all-byte-indices --descriptor-table-report Exports/ghidra-reports/nidatastream_descriptor_table_all_indices.json --descriptor-table-summary Exports/ghidra-reports/nidatastream_descriptor_table_all_indices.md --ghidra-execute
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare --list-json
```

Ignored generated outputs created/refreshed:

- `Exports/ghidra-reports/nidatastream_descriptor_table_all_indices.json`
- `Exports/ghidra-reports/nidatastream_descriptor_table_all_indices.md`

They remain ignored and must not be staged.

## Known blockers

- All 768 all-index rows are zero for the current candidate base/stride model.
- The candidate base addresses may be table-adjacent references, zero-filled sentinels, or otherwise not the raw semantic table.
- Descriptor bytes 1-2 remain unmapped for parser/export semantics.

## Next recommended actions

1. Add a bounded Ghidra neighborhood/nonzero scanner around the candidate data references to find nearby nonzero tables without dumping broad binary data.
2. Compare decompile data references against raw memory block boundaries and relocations to determine whether the current addresses are table bases or sentinel references.
3. Keep parser/export promotion blocked until a nonzero static source is semantically joined with sample descriptor bytes and guarded.
