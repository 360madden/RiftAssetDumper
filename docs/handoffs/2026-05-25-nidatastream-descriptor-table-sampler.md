# Handoff — NiDataStream descriptor table sampler

Date: 2026-05-25

## Goal

Add a repeatable, candidate-only Ghidra workflow command that samples computed descriptor-table entries for observed stream descriptor indices without changing parser/export behavior.

## What changed

- Added `scripts/ghidra/DescriptorTableSampler.java` to read bounded bytes from computed `base + index * stride` descriptor-table addresses.
- Added `nidatastream-descriptor-table-sample` to `scripts/rift_workflow.py` with dry-run, `--list-json`, and `--ghidra-execute` modes.
- Added PowerShell alias wiring: `NiDataStreamDescriptorTableSample`.
- Added schema `docs/schemas/ghidra-descriptor-table-sample-v1.schema.json` for candidate-only sample reports.
- Added routing/schema tests in `scripts/test_ghidra_runner.py` and command-alias coverage in `scripts/test_rift_workflow_command_wiring.py`.

## Evidence observed

Command run against the retained Ghidra project:

```powershell
python scripts/rift_workflow.py nidatastream-descriptor-table-sample --ghidra-execute
```

The command derived observed descriptor indices from the current descriptor/sample matrix and sampled three candidate static descriptor fields:

| Field | Base | Offset | Indices sampled | Result |
|---|---|---:|---|---|
| `descriptor-enable-or-special-flag` | `143358be0` | 0 | `0x37`, `0x36`, `0x15`, `0x3c`, `0x10` | 5 rows, all `00 00 00 00` |
| `descriptor-component-class` | `143358be4` | 4 | `0x37`, `0x36`, `0x15`, `0x3c`, `0x10` | 5 rows, all `00 00 00 00` |
| `descriptor-format-size-lookup` | `143358be8` | 8 | `0x37`, `0x36`, `0x15`, `0x3c`, `0x10` | 5 rows, all `00 00 00 00` |

Local ignored outputs:

- `Exports/ghidra-reports/nidatastream_descriptor_table_samples.json`
- `Exports/ghidra-reports/nidatastream_descriptor_table_samples.md`

## Interpretation

The sampler is now useful and repeatable, but the first retained-project sample does **not** prove descriptor bytes 1-2 or parser/export semantics. The computed rows for the current candidate table bases are memory-backed and readable, but all sampled bytes are zero for the observed indices. Treat that as evidence against immediate promotion from these bases, not as a parser field map.

Likely next proof needs are:

1. Join descriptor-table sample status into `nidatastream-descriptor-sample-compare` so zero/nonzero row counts become durable machine-readable blocker evidence.
2. Re-check whether the candidate addresses are table bases, table-adjacent sentinels, relocated references, or decompiler-selected addresses that need a different indexing model.
3. Keep `FieldOrderPromoted=false` and `ParserExportPromotionAllowed=false` until a future proof maps stream bytes to semantics.

## Validation / safety

Validated before commit:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_ghidra_runner.py
python scripts/test_rift_workflow_command_wiring.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py nidatastream-descriptor-table-sample --list-json
python scripts/rift_workflow.py nidatastream-descriptor-table-sample --ghidra-execute
<Ghidra JDK javac compile of FunctionSiteSurvey.java and DescriptorTableSampler.java>
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Generated report outputs remain ignored under `Exports/` and must not be staged.

## Known blockers

- Current descriptor-table samples are all zero for observed indices.
- Descriptor record bytes 1-2 remain unmapped for parser/export semantics.
- No parser/export behavior should consume this report yet.

## Next recommended actions

1. Integrate descriptor-table sample summaries into `nidatastream-descriptor-sample-compare` as candidate-only blocker/status evidence.
2. Add negative fixture coverage for malformed descriptor-table sample reports if/when the report is consumed by status logic.
3. Investigate alternate static address/indexing interpretations only through ignored reports and schema-backed summaries.
