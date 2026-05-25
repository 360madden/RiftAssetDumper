# Handoff — NiDataStream descriptor reference classification

Date: 2026-05-25

## Goal

Add and run a candidate-only Ghidra reference classifier for the descriptor data addresses after the stride-12 all-index sample and bounded neighborhood scan both produced zero-byte evidence.

## What changed

- Added `scripts/ghidra/DescriptorReferenceClassifier.java`.
- Added workflow command `nidatastream-descriptor-reference-classify` with dry-run, `--list-json`, and `--ghidra-execute` modes.
- Added schema `docs/schemas/ghidra-descriptor-reference-classification-v1.schema.json`.
- Added PowerShell alias `NiDataStreamDescriptorReferenceClassify` and command-wiring tests.
- Added routing/schema tests for the new classifier.
- Documented the command in the Ghidra/NiDataStream workflow docs and promotion checklist.

## Evidence observed

Command run against the retained Ghidra project:

```powershell
python scripts/rift_workflow.py nidatastream-descriptor-reference-classify --ghidra-execute
```

Result:

| Metric | Value |
|---|---:|
| Fields | 3 |
| Total references | 20 |
| Captured references | 20 |
| Fields with references | 3 |
| Ghidra READ refs | 0 |
| Ghidra WRITE refs | 0 |
| Ghidra DATA refs | 20 |
| Address-like DATA refs | 20 |
| Unique referencing functions | 6 |

Field summary:

| Field | References | Functions | First 16 bytes |
|---|---:|---:|---|
| `descriptor-enable-or-special-flag` | 14 | 6 | all zero |
| `descriptor-component-class` | 3 | 3 | all zero |
| `descriptor-format-size-lookup` | 3 | 3 | all zero |

Ignored generated outputs:

- `Exports/ghidra-reports/nidatastream_descriptor_reference_classification.json`
- `Exports/ghidra-reports/nidatastream_descriptor_reference_classification.md`

## Interpretation

The classifier changed the next-best question. Ghidra classifies all references to these addresses as DATA/address-like rather than READ/WRITE, but the captured instruction text shows indexed memory operands against the candidate bases and offsets. That means the prior stride-12 all-index sample is best treated as a failed hypothesis, not as proof that no descriptor lookup data exists. The next useful slice is a candidate-only stride/base-model review and a guarded resample plan.

Parser/export promotion remains locked.

## Validation / safety

Validated in this stage:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_ghidra_runner.py
python scripts/test_rift_workflow_command_wiring.py
python scripts/test_schema_registry.py
ruff check scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
mypy scripts/ --no-error-summary
<Ghidra JDK javac compile of FunctionSiteSurvey.java, DescriptorTableSampler.java, DescriptorTableNeighborhoodScanner.java, and DescriptorReferenceClassifier.java>
python scripts/rift_workflow.py nidatastream-descriptor-reference-classify --list-json
python scripts/rift_workflow.py nidatastream-descriptor-reference-classify --ghidra-execute
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Generated classifier outputs remain ignored under `Exports/ghidra-reports/` and must not be staged.

## Known blockers

- The static descriptor stride/base model is not resolved.
- Stream descriptor bytes 1-2 remain unmapped for parser/export semantics.
- Ghidra reference type alone is too coarse here because indexed memory reads are reported as DATA/address-like references.
- Parser/export promotion remains locked.

## Next recommended actions

1. Add a candidate-only stride/base-model review that derives sample plans from reference instruction text instead of assuming stride 12.
2. Resample the descriptor bases with the revised candidate stride(s), keeping outputs ignored and schema-backed.
3. Keep all descriptor evidence report-only until a field map is backed by Ghidra references, sample bytes, schemas, guards, and parser/export non-consumption checks.
