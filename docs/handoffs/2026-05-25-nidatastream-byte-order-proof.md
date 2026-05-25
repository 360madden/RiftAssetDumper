# Handoff — NiDataStream descriptor byte-order proof fields

Date: 2026-05-25

## Goal

Expand the Ghidra/NiDataStream report-only proof from uniform prefix/trailer counters into a candidate byte-order table that records exact structural offsets before any parser/export promotion.

## What changed

- `nidatastream-layout` now reports additional candidate-only byte-order evidence:
  - `TopSecondUInt32`
  - `TopPairRecordOffsets`
  - `TopFirstPairRecordBytes`
  - `TopDescriptorCountOffsets`
  - `TopDescriptorRecordOffsets`
  - `TopFirstDescriptorRecordBytes`
- Shifted sample rows now include pair/descriptor record offsets and first record byte examples.
- `nidatastream-descriptor-sample-compare` now includes:
  - `SampleCorpusStatus`
  - `DescriptorByteOrderProof`
  - 7 structural byte-order checks.
- Added negative fixture coverage for descriptor byte-order mismatches.
- Updated docs/checklists to describe the candidate byte-order proof surface.

## Evidence / validation

- `python -m py_compile scripts/nidatastream_layout_report.py scripts/rift_workflow.py scripts/test_nidatastream_layout_report.py scripts/test_nidatastream_descriptor_sample_compare.py`
- `python scripts/test_nidatastream_layout_report.py`
- `python scripts/test_nidatastream_descriptor_sample_compare.py`
- `python scripts/test_schema_registry.py`
- `ruff check scripts/rift_workflow.py scripts/nidatastream_layout_report.py scripts/test_nidatastream_layout_report.py scripts/test_nidatastream_descriptor_sample_compare.py scripts/test_schema_registry.py`
- `python scripts/rift_workflow.py nidatastream-layout --root Extracted --full`
- `python scripts/rift_workflow.py nidatastream-descriptor-sample-compare`
- `python scripts/rift_workflow.py nidatastream-promotion-preflight`
- `python scripts/rift_workflow.py generated-output-guard`
- `git diff --check`

Current ignored local evidence after refreshing `nidatastream-layout`:

- Files parsed: `8/8`
- NiDataStream blocks: `184`
- Ghidra-style-valid blocks: `184/184`
- Uniform sample-byte checks: `6/6`
- Descriptor byte-order checks: `7/7`
- Descriptor/sample ready: `true`
- Parser/export promotion remains locked: `ParserExportPromotionAllowed=false`, `FieldOrderPromoted=false`

Observed structural byte-order counters:

- `SecondUInt32`: `0` across `184/184`
- Pair record offset: `12` across `184/184`
- Descriptor count offset: `20` across `184/184`
- Descriptor record offset: `24` across `184/184`
- Payload prefix bytes: `28` across `184/184`

## Known blockers / guardrails

- This is still candidate-only and report-only.
- The proof now covers structural byte order, not final descriptor semantic promotion.
- Pairing impact remains candidate-only, with no parser/export behavior change.
- Ignored reports refreshed under `Exports/` must remain unstaged.

## Next recommended actions

1. Map first descriptor record byte examples to candidate semantic meanings only if Ghidra evidence supports it.
2. Add dashboard-level visibility for byte-order check counts.
3. Keep parser/export promotion locked until descriptor semantics, pairing impact, and negative fixtures pass together.
