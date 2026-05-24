# Ghidra anchor survey handoff — 2026-05-24

> Status note: the TWAD-specific next step in this historical handoff is superseded by `docs/handoffs/2026-05-24-twad-ghidra-proof.md`. Keep this file as the anchor-survey evidence packet for the broader NIF, NiDataStream, NiMesh, and decompression leads.

## Status

Completed a narrow offline Ghidra survey against `rift_x64.exe` for asset/parser anchors. Treat every address and function name below as a static-analysis hypothesis only.

## What was validated

- Ghidra full auto-analysis completed successfully with a 4-hour timeout.
- The analyzed project was retained under ignored generated output:
  - `Exports/ghidra-projects/RiftAnchorSurvey`
- The survey report was generated under ignored generated output:
  - `Exports/ghidra-reports/rift_x64_anchor_survey.json`
- Ghidra 12.1 headless did not execute `.py` scripts in this launch mode; the survey was moved to a Java Ghidra script and executed through `-scriptPath`.
- Script-only reruns now work against the retained project with `--process rift_x64.exe --no-analysis`.

## Anchor findings

| Anchor | Result | Hypothesis |
| --- | ---: | --- |
| `TWAD` | 0 Ghidra string hits; 1 raw byte hit in `.text` | `TWAD` is likely used as an immediate header/magic compare, not as a defined string. |
| `TWAM` | 0 hits | No direct static evidence in `rift_x64.exe` from this survey. |
| `NIF` | 38 string hits / 82 refs | Client has NIF path/type/runtime references, including `.nif`, `_lod.nif`, `DEFAULTNIFPATH`, and Gamebryo Ni type strings. |
| `Gamebryo` | 8 string hits / 14 refs | Embedded Gamebryo 2.6 / runtime-type evidence exists. |
| `NiDataStream` | 4 string hits / 7 refs | Mesh semantic/data-stream validation and `NiDataStream::LoadBinary()` evidence exists. |
| `NiMesh` | 11 string hits / 28 refs | Mesh/material-binding/morph/culling runtime evidence exists. |
| `NiNode` | 1 string hit / 4 refs | Ni object type registration or RTTI-like evidence exists. |
| `NiTriShape` | 3 string hits / 12 refs | TriShape type evidence exists. |
| `zlib` | 10 string hits / 13 refs | zlib is present, including addon Lua zlib and runtime zlib errors. |
| `lzma` | 0 hits | No direct static evidence in this survey. |
| `inflate` | 3 string hits / 6 refs | Lua zlib inflate-related evidence exists. |
| `decompress` | 14 string hits / 20 refs | Client-data/blob/KFB/Tsunami decompressor strings exist. |

## Highest-value static leads

- `TWAD` raw magic:
  - file offset: `0x6e8460`
  - virtual address: `0x1406e9060`
  - probable instruction site: `0x1406e905e`
  - nearby bytes decode as a compare against `0x44415754` (`TWAD` little-endian in code bytes).
- Asset manifest/NIF lead:
  - `assets64.manifest`, `AssetManifestName64`, and `AssetManifestPath64` all reference `FUN_1408900c0`.
- NiDataStream/NiMesh lead:
  - semantic adapter / renderer semantic errors reference `FUN_14111e910`.
  - `NiDataStream::LoadBinary()` lock failure references `FUN_141186980`.
- Ni object type lead:
  - `NiNode`, `NiTriShape`, `NiTriShapeData`, and `NiTriShapeDynamicData` cluster around `FUN_141161ab0` and `FUN_141161fa0`, with additional no-function data refs.
- Decompression lead:
  - decompression metrics cluster at `FUN_14124fdc4`.
  - chunk decompression memory strings reference `FUN_1415789b0`.
  - client data recovery strings mention blob and KFB decompressor failures.

## Important caveats

- These are not parser truths yet.
- The function names are Ghidra auto-analysis names and may drift if the project is rebuilt.
- The report is intentionally ignored/generated; do not commit `Exports/`.
- The retained Ghidra project is useful for fast script-only follow-up but is also ignored/generated.

## Recommended next proof step

Use the retained project to inspect the `TWAD` compare site and its caller/callee path first. The goal should be to determine whether the code is validating archive magic, chunk magic, table magic, or an unrelated embedded constant before changing any parser code.
