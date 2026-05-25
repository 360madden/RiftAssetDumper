# Handoff — NiDataStream descriptor base-model review

Date: 2026-05-25

## Goal

Turn the descriptor reference-classifier output into a candidate-only base/stride model review so future sampling is guided by current evidence instead of the stale stride-12 assumption alone.

## What changed

- Added workflow command `nidatastream-descriptor-base-model-review`.
- Added schema `docs/schemas/nidatastream-descriptor-base-model-review-v1.schema.json`.
- Added PowerShell alias `NiDataStreamDescriptorBaseModelReview` and command-wiring tests.
- Added tests that validate the base-model review report against the schema.
- Documented the command in the Ghidra/NiDataStream workflow docs and promotion checklist.

## Evidence observed

Command run:

```powershell
python scripts/rift_workflow.py nidatastream-descriptor-base-model-review
```

Result:

| Metric | Value |
|---|---:|
| Fields | 3 |
| Writable fields | 3 |
| Static bytes all zero | true |
| Indexed instruction count | 12 |
| Blocking items | 4 |

Instruction-derived scale candidates:

| Scale bytes | Count |
|---:|---:|
| 4 | 9 |
| 1 | 3 |

Offset candidates:

| Offset bytes | Count |
|---:|---:|
| 4 | 3 |
| 8 | 3 |

Candidate model outcomes:

| Model | Status | Why |
|---|---|---|
| `current-field-map-stride-12` | blocked | Existing all-index sample has 768 rows, 0 nonzero rows |
| `reference-instruction-index-scale` | candidate | Classifier instruction text contains indexed memory operands |
| `static-image-byte-source` | blocked | Descriptor static image bytes are all zero |

Ignored generated outputs:

- `Exports/ghidra-reports/nidatastream_descriptor_base_model_review.json`
- `Exports/ghidra-reports/nidatastream_descriptor_base_model_review.md`

## Interpretation

The current stride-12 static sample is now explicitly a blocked hypothesis. Reference instruction text provides candidate index-scale leads, but static image bytes remain zero, so no parser/export behavior can be promoted. The next safe slice is a guarded resample mode that can test explicitly named candidate strides/bases while keeping all evidence report-only.

## Validation / safety

Validated in this stage:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
python scripts/test_ghidra_runner.py
python scripts/test_rift_workflow_command_wiring.py
python scripts/test_schema_registry.py
python scripts/rift_workflow.py nidatastream-descriptor-base-model-review
ruff check scripts/rift_workflow.py scripts/test_ghidra_runner.py scripts/test_rift_workflow_command_wiring.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Generated base-model review outputs remain ignored under `Exports/ghidra-reports/` and must not be staged.

## Known blockers

- Static descriptor bytes remain zero.
- The stride/base model is not promoted.
- Parser/export promotion remains locked.
- The model review is not yet integrated into `nidatastream-promotion-status`.

## Next recommended actions

1. Add guarded descriptor-table resampling options for explicit candidate stride/base hypotheses.
2. Integrate base-model review status into promotion/dashboard surfaces after the resample path exists.
3. Keep parser/export code unchanged until a full proof packet exists.
