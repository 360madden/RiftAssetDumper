# Handoff — NiDataStream descriptor FunctionSiteSurvey data-ref refresh

Date: 2026-05-25

## Goal

Populate ignored NiDataStream descriptor-helper FunctionSiteSurvey reports with the new bounded `dataRefByteSamples` field and capture what the first refresh proves.

## Commands run

```powershell
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-descriptor-helper --ghidra-execute
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-descriptor-builder-1770 --ghidra-execute
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-descriptor-builder-17c0 --ghidra-execute
python scripts/rift_workflow.py ghidra-function-site-status --list-json
```

## What changed

- Refreshed ignored local reports and summaries under `Exports/ghidra-reports/` for the three NiDataStream descriptor helper/builder targets.
- Tracked source/assets were not changed by the refresh.
- FunctionSite evidence status remains 7/7 evidence-ready.

## Evidence observed

Refreshed ignored reports now include `dataRefByteSamples`:

| Target report | Samples | Sampled addresses | Current sampled bytes |
|---|---:|---|---|
| `nidatastream_descriptor_1411821f0.json` | 3 | `143358be0`, `143358be4`, `143358be8` | first 32 bytes at each sampled address are zero |
| `nidatastream_descriptor_builder_141181770.json` | 3 | `143358be0`, `143358be4`, `143358b01` | first 32 bytes at each sampled address are zero |
| `nidatastream_descriptor_builder_1411817c0.json` | 3 | `143358be0`, `143358b04`, `143358be8` | first 32 bytes at each sampled address are zero |

## Interpretation

This refresh proves the new FunctionSiteSurvey field works in retained-project Ghidra runs, but the sampled base/static addresses alone do **not** explain descriptor bytes 1-2. The descriptor helper decompile indexes a stride-12 table using `param_1 & 0xff`; the next useful static step is sampling computed table entries for observed descriptor indices such as `0x37`, `0x36`, `0x15`, `0x10`, and `0x3c` at the referenced base addresses.

## Validation / safety

- Each Ghidra run completed successfully through the repo workflow command.
- `generated-output-guard` ran before each Ghidra command and reported 0 tracked/staged generated output paths.
- `ghidra-function-site-status --list-json` reports 7/7 evidence-ready targets.
- Refreshed report/summary outputs remain ignored under `Exports/ghidra-reports/` and are not staged.

## Known blockers

- Existing `dataRefByteSamples` capture direct referenced base addresses, not computed indexed entries.
- Descriptor bytes 1-2 remain unmapped for parser/export semantics.
- Parser/export promotion remains locked.

## Next recommended actions

1. Add a bounded explicit-address byte-sampling mode or targeted descriptor-table sampler for computed table entries.
2. Sample descriptor table entries for review-queue indices `0x37`, `0x36`, `0x15`, `0x10`, and `0x3c` using stride `0x0c`.
3. Compare sampled static entries against copied-sample descriptor records and context rows; keep results candidate-only.
