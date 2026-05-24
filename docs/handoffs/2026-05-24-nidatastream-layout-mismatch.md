# NiDataStream layout mismatch handoff — 2026-05-24

## Status

Completed the parser-order follow-up from `docs/handoffs/2026-05-24-nidatastream-ghidra-proof.md`. This produced a concrete, bounded mismatch hypothesis and a read-only workflow command to validate it against copied/extracted NIF samples.

No decoder/export behavior was changed in this milestone.

## New workflow surface

```powershell
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
```

Outputs are generated and intentionally ignored:

- `Exports/nidatastream-layout-report.json`
- `Exports/nidatastream-layout-report.md`

The command parses copied/extracted `.nif` files, finds `NiDataStream` blocks, and compares:

1. the legacy repo assumption: `legacy payload offset = blockSize - declaredPayloadBytes`
2. the Ghidra-aligned layout: descriptor prefix bytes, then declared payload bytes, then a 1-byte trailing flag

## Evidence summary

### Ghidra static evidence

`FUN_141186980` remains the current static lead for `NiDataStream::LoadBinary()`. The read order observed from the decompile is:

1. 4-byte declared payload/data byte count
2. 4-byte field
3. descriptor-pair count
4. descriptor pairs
5. element/format descriptor count
6. element/format descriptors
7. alignment/component helper calls
8. declared payload read
9. final 1-byte flag read

Follow-up surveys were generated for helper functions called by the load path:

| Function | Report | Static finding |
|---|---|---|
| `FUN_1411821f0` | `Exports/ghidra-reports/nidatastream_descriptor_1411821f0.json` | Small descriptor-size helper. Uses a format table at `DAT_143358be0`/`DAT_143358be4`/`DAT_143358be8`, calls `FUN_141182280`, and returns a component/byte-size product. |
| `FUN_141181770` | `Exports/ghidra-reports/nidatastream_descriptor_builder_141181770.json` | Small descriptor/component helper called by `FUN_141186980` and semantic-adapter paths. |
| `FUN_1411817c0` | `Exports/ghidra-reports/nidatastream_descriptor_builder_1411817c0.json` | Small descriptor helper called by `FUN_141186980`; routes through `FUN_141182280` for table-backed format sizing. |

### Copied/extracted NIF validation

The read-only layout report was run against all currently copied/extracted `.nif` files under `Extracted/`.

| Metric | Result |
|---|---:|
| `.nif` files scanned | 8 |
| `.nif` files parsed | 8 |
| Files with `NiDataStream` blocks | 8 |
| `NiDataStream` blocks | 184 |
| Valid declared payload blocks | 184 |
| Ghidra-style layout valid blocks | 184 |
| Legacy offset shifted blocks | 184 |
| Observed payload prefix bytes | `28` for 184/184 |
| Observed payload trailer bytes | `1` for 184/184 |
| Observed trailing flag | `1` for 184/184 |
| Legacy offset minus Ghidra offset | `1` for 184/184 |

## Concrete mismatch

Current C# report/role-analysis code repeatedly uses this shape:

```csharp
declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
headerBytes = blockPayload.Length - checked((int)declaredPayloadBytes.Value);
body = blockPayload.Slice(headerBytes.Value, checked((int)declaredPayloadBytes.Value));
```

For the current copied sample set, that starts the body at byte `29`.

The Ghidra-aligned layout validated by `nidatastream-layout` is:

```text
28-byte descriptor prefix
declared payload bytes
1-byte trailing flag
```

So the candidate payload body starts at byte `28`, and the existing body slice is shifted forward by one byte and includes the trailing flag as its last byte.

## Decision

Treat this as a real parser/reporting mismatch, but do **not** silently change decoder/export behavior yet. The safe next step is a small guarded migration:

1. add a shared `NiDataStream` layout helper in C#,
2. expose both legacy and Ghidra-aligned offsets in reports,
3. compare role classification at offset 28 vs offset 29,
4. migrate consumers only after validation shows the new body slice is consistently better.

## Remaining unwired pieces

- The C# role-analysis/reporting sites still use the legacy `headerBytes = blockSize - declaredPayloadBytes` payload offset.
- `nidatastream-layout` is read-only Python evidence; it does not yet feed the C# reports.
- Helper-function Ghidra surveys identify descriptor sizing/table helpers, but exact durable field names for the descriptor table are still hypotheses.
- No OBJ/export behavior should be promoted from this evidence until the decoder patch has a guard and before/after report comparison.

## Recommended next milestone

Implement the guarded C# layout helper and report migration without changing export behavior. Keep the legacy offset visible for one milestone so old `*-ror1-*` findings can be compared against the corrected payload start.
