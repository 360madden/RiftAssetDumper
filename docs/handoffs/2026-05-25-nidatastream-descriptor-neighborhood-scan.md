# Handoff — NiDataStream descriptor-table neighborhood scan

Date: 2026-05-25

## Goal

Add and run a bounded nonzero-byte neighborhood scan around the candidate descriptor-table data references after the all-index scan showed the current base/stride model is all zero.

## What changed

- Added `scripts/ghidra/DescriptorTableNeighborhoodScanner.java`.
- Added workflow command `nidatastream-descriptor-neighborhood-scan` with dry-run, `--list-json`, and `--ghidra-execute` modes.
- Added schema `docs/schemas/ghidra-descriptor-table-neighborhood-scan-v1.schema.json`.
- Added PowerShell alias `NiDataStreamDescriptorNeighborhoodScan` and command-wiring tests.
- Added routing/schema tests for the new scanner.
- Kept read failures non-fatal inside the bounded scan so unmapped/problem rows are counted as skipped instead of aborting the whole report.

## Evidence observed

Command run against the retained Ghidra project:

```powershell
python scripts/rift_workflow.py nidatastream-descriptor-neighborhood-scan --ghidra-execute
```

Result:

| Metric | Value |
|---|---:|
| Fields | 3 |
| Window before | 1024 bytes |
| Window after | 8192 bytes |
| Step | 4 bytes |
| Rows scanned | 6915 |
| Memory-backed rows | 6915 |
| Skipped rows | 0 |
| Nonzero hits | 0 |
| Truncated | false |

Ignored generated outputs:

- `Exports/ghidra-reports/nidatastream_descriptor_neighborhood_scan.json`
- `Exports/ghidra-reports/nidatastream_descriptor_neighborhood_scan.md`

## Interpretation

The neighborhood scan found no nonzero 4-byte reads in a bounded window from 1024 bytes before through 8192 bytes after each candidate descriptor-table data reference. Together with the all-index scan, this makes the current candidate data-reference model unlikely to be the raw static descriptor semantics source. The useful next step is to inspect decompiler/reference semantics rather than expanding parser/export behavior.

## Validation / safety

Validated in this stage:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_ghidra_runner.py
python scripts/test_rift_workflow_command_wiring.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
mypy scripts/ --no-error-summary
<Ghidra JDK javac compile of FunctionSiteSurvey.java, DescriptorTableSampler.java, and DescriptorTableNeighborhoodScanner.java>
python scripts/rift_workflow.py nidatastream-descriptor-neighborhood-scan --list-json
python scripts/rift_workflow.py nidatastream-descriptor-neighborhood-scan --ghidra-execute
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Generated scan outputs remain ignored under `Exports/ghidra-reports/` and must not be staged.

## Known blockers

- No nonzero neighborhood hits were found around the current candidate references.
- Descriptor bytes 1-2 remain unmapped for parser/export semantics.
- Parser/export promotion remains locked.

## Next recommended actions

1. Inspect the descriptor helper decompile/reference shape to determine whether `143358be0`/`be4`/`be8` are sentinel/global slots rather than table bases.
2. Add a reference-kind/classification summary for descriptor data refs so future scans distinguish READ, WRITE, address-taken, relocation, and decompiler artifact cases.
3. Keep all descriptor-table evidence candidate-only until a nonzero source is semantically mapped and guarded.
