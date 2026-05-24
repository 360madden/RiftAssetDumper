# NiDataStream / NiMesh Ghidra proof handoff — 2026-05-24

## Status

Completed the first bounded Ghidra follow-up on the `NiDataStream` / `NiMesh` anchors from the retained `rift_x64.exe` project. This is static evidence only: no parser behavior was changed, and generated reports remain ignored under `Exports/`.

## Scope and safety

- Retained generated Ghidra project reused: `Exports/ghidra-projects/RiftAnchorSurvey`
- Ghidra reports written under ignored `Exports/ghidra-reports/`
- Reusable tracked survey script renamed to `scripts/ghidra/FunctionSiteSurvey.java`
- No `Source/`, `Extracted/`, or `Exports/` files should be staged or committed.
- Function names remain Ghidra auto-analysis labels and should be treated as non-durable until backed by byte/parser proof.

## Workflow note

Retained-project Ghidra runs must be serialized. A parallel attempt against the same `RiftAnchorSurvey` project failed with a project-lock error while another script-only run was active. Sequential rerun succeeded.

Preferred command shape:

```powershell
python scripts/rift_workflow.py ghidra-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project --ghidra-timeout 900 --ghidra-script scripts/ghidra/FunctionSiteSurvey.java --ghidra-script-arg 0x141186980 --ghidra-script-arg Exports/ghidra-reports/nidatastream_loadbinary_141186980.json
```

## Reports generated

| Report | Target | Status |
| --- | --- | --- |
| `Exports/ghidra-reports/nidatastream_semantic_adapter_14111e910.json` | `0x14111e910` | generated after serialized retry |
| `Exports/ghidra-reports/nidatastream_loadbinary_141186980.json` | `0x141186980` | generated |
| `Exports/ghidra-reports/nimesh_material_binding_caller_14111f570.json` | `0x14111f570` | generated with tracked generic script |

## Static findings

### `FUN_141186980` — `NiDataStream::LoadBinary()` path

| Item | Evidence |
| --- | --- |
| Function | `FUN_141186980` |
| Entry | `0x141186980` |
| Body range | `0x141186980`..`0x141186f4b` |
| Caller refs | 7 data/vtable-like refs, no direct code caller in this survey |
| Role hypothesis | `NiDataStream::LoadBinary()` binary load routine |

Key observations:

- The decompiler signature resolves as `void FUN_141186980(longlong *param_1,longlong param_2)`.
- The function reads several 4-byte fields/counts from the binary stream and grows internal arrays before reading payload data.
- It builds an element/component accumulator from stream-element descriptors before reading payload bytes.
- It calls through object/vtable offsets around the load path, including checks consistent with alignment compatibility and data-stream locking.
- Error text in the function identifies the path as `NiDataStream::LoadBinary()` and includes failures for incompatible data alignment and lock failure.

Parser relevance:

- This supports the repo's current focus on `NiDataStream` element descriptors and usage/access metadata.
- Exact field naming is not yet proven enough for parser changes.
- Best next parser-facing work is a read-only alignment between current `NiDataStream` parser fields and the Ghidra load order, not extraction/export promotion.

### `FUN_14111e910` — semantic adapter validation path

| Item | Evidence |
| --- | --- |
| Function | `FUN_14111e910` |
| Entry | `0x14111e910` |
| Body range | `0x14111e910`..`0x14111f21c` |
| Code caller | `FUN_14111f570` at `0x14111f73e` |
| Role hypothesis | validates semantic adapter entries during mesh material binding creation |

Key observations:

- Error/report text identifies the higher-level path as `NiMeshMaterialBinding::CreateBinding`.
- The function validates semantic adapter table ordering and consistency against `NiDataStream` element order.
- It checks that shared semantic adapter entries are monotonic from zero, ordered like the corresponding `NiDataStream` elements, share a common data format, and fit component-count limits.
- It also detects shader-expected values missing from the corresponding data stream.

Parser relevance:

- This is static confirmation that stream element order and semantic adapter order matter.
- The repo's current role/attribute work should continue to preserve both raw order and semantic grouping rather than collapsing repeated stream entries too early.
- No direct parser behavior change is justified from this alone.

### `FUN_14111f570` — DX9 material binding caller

| Item | Evidence |
| --- | --- |
| Function | `FUN_14111f570` |
| Entry | `0x14111f570` |
| Body range | `0x14111f570`..`0x14111f9f1` |
| Caller | `FUN_14111ac30` at `0x14111ac7c` |
| Calls target | `FUN_14111e910` at `0x14111f73e` |
| Role hypothesis | DX9 mesh material binding creation path |

Key observations:

- This caller invokes the semantic-adapter validator and emits/reporting text tied to `NiDX9MeshMaterialBinding::Create`.
- This places the semantic validation evidence in the renderer/material-binding path, not the archive/TWAD path.

## Confidence classification

| Claim | Confidence | Reason |
| --- | --- | --- |
| `FUN_141186980` is a `NiDataStream::LoadBinary()` path | High | embedded diagnostic text names `NiDataStream::LoadBinary()` and the function reads binary fields/payload data |
| `FUN_14111e910` validates mesh semantic adapter data against `NiDataStream` elements | High | multiple diagnostics mention semantic adapter entries, renderer semantics, and `NiDataStream` element order |
| `FUN_14111f570` is in the DX9 mesh material-binding creation path | Medium-high | diagnostics mention `NiDX9MeshMaterialBinding::Create` and it calls the semantic validator |
| Current parser should change now | Low / blocked | evidence supports ordering/field-alignment review but does not prove a bounded parser behavior gap yet |
| Ghidra retained-project runs can be parallelized | False | observed project-lock failure when two headless runs targeted the same retained project concurrently |

## Decision

The next durable truth is static/architectural: client-side `NiDataStream` loading and mesh semantic adapter validation are separate but connected parts of the NIF render/material pipeline. The repo parser should continue preserving raw stream element order, usage/access metadata, and semantic grouping evidence. No parser behavior change is recommended in this milestone.

## Recommended next milestone

1. Compare the current C# `NiDataStream` parser's field read order against the `FUN_141186980` load order and document mismatches as hypotheses only.
2. Add a small report summarizer for `FunctionSiteSurvey` JSON so future Ghidra evidence can be reviewed without hand-inspecting large decompiler output.
3. Then inspect `FUN_1411821f0`, `FUN_141181770`, and `FUN_1411817c0`, because `FUN_141186980` calls them while handling stream element descriptors/component counts.
