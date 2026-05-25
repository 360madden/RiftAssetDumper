# Handoff — NiDataStream descriptor reference memory-block metadata

Date: 2026-05-25

## Goal

Extend the descriptor reference classifier so zero-byte descriptor data references can be interpreted with memory-block context instead of only raw bytes and xrefs.

## What changed

- `DescriptorReferenceClassifier.java` now records memory-block metadata for each descriptor data address:
  - block name/start/end/size,
  - initialized/loaded flags,
  - read/write/execute flags,
  - block type/source name.
- `ghidra-descriptor-reference-classification-v1.schema.json` now requires those memory-block fields.
- The classifier Markdown table now includes block name, initialized state, and writable state.
- Tests now validate the expanded schema fixture.
- Workflow docs now state that the classifier covers reference kinds, instruction text, and memory-block metadata.

## Evidence observed

Command run against the retained Ghidra project:

```powershell
python scripts/rift_workflow.py nidatastream-descriptor-reference-classify --ghidra-execute
```

Current ignored report shows all three descriptor addresses are:

| Field | Block | Initialized | Writable | First 16 bytes |
|---|---|---:|---:|---|
| `descriptor-enable-or-special-flag` | `.data` | true | true | all zero |
| `descriptor-component-class` | `.data` | true | true | all zero |
| `descriptor-format-size-lookup` | `.data` | true | true | all zero |

Reference summary remains:

| Metric | Value |
|---|---:|
| Total references | 20 |
| Captured references | 20 |
| Ghidra DATA/address-like refs | 20 |
| Unique referencing functions | 6 |

Ignored generated outputs:

- `Exports/ghidra-reports/nidatastream_descriptor_reference_classification.json`
- `Exports/ghidra-reports/nidatastream_descriptor_reference_classification.md`

## Interpretation

The descriptor addresses are in an initialized, writable `.data` block and currently read as zero in static image bytes. Combined with indexed DATA references, this keeps the evidence candidate-only: static bytes are not enough to promote parser/export behavior, and the next safe question is still a guarded stride/base-model review plus an explanation for why referenced initialized data is all zero.

## Validation / safety

Validated in this stage:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/test_ghidra_runner.py
python scripts/test_ghidra_runner.py
python scripts/test_schema_registry.py
<Ghidra JDK javac compile of DescriptorReferenceClassifier.java>
python scripts/rift_workflow.py nidatastream-descriptor-reference-classify --ghidra-execute
ruff check scripts/rift_workflow.py scripts/test_ghidra_runner.py
mypy scripts/ --no-error-summary
python scripts/rift_workflow.py generated-output-guard
git diff --check
```

Generated classifier outputs remain ignored under `Exports/ghidra-reports/` and must not be staged.

## Known blockers

- Static descriptor stride/base semantics remain unresolved.
- Static bytes remain all zero despite indexed references.
- Ghidra reference types are DATA/address-like, so instruction text and memory-block metadata must stay sidecar evidence until a stronger proof is added.
- Parser/export promotion remains locked.

## Next recommended actions

1. Add a candidate-only descriptor stride/base-model review that uses reference instruction text and memory-block metadata.
2. Add a guarded resample mode only after the review identifies explicit candidate strides/bases.
3. Keep the classifier report ignored and schema-backed; do not consume it from parser/export code.
