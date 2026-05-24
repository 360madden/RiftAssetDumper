# NiDataStream parser-field comparison — Ghidra sidecar status

Status: **candidate-only / report-only**. This note compares current repo parser/report fields with the retained-project Ghidra `NiDataStream` static evidence. It is not a parser promotion plan.

## Evidence inputs

| Evidence | Current source |
|---|---|
| Load routine anchor | `ghidra-function-site-survey --ghidra-target nidatastream-loadbinary` |
| Descriptor/helper anchors | `nidatastream-descriptor-helper`, `nidatastream-descriptor-builder-1770`, `nidatastream-descriptor-builder-17c0` |
| Semantic adapter anchor | `ghidra-function-site-survey --ghidra-target nidatastream-semantic-adapter` |
| Parser-side comparison reports | `nidatastream-layout`, `inventory-nif-stream-bodies`, `inventory-nif-mesh-bindings` |

All Ghidra reports/summaries are ignored local evidence under `Exports/ghidra-reports/`.

## Current field alignment

| Concept | Ghidra static read | Current repo surface | Promotion state |
|---|---|---|---|
| Declared payload byte count | Load path reads stream binary fields/counts before payload data | `DeclaredPayloadBytes` from the first 4 payload bytes | Reported and used for bounds checks |
| Payload prefix | Load path evidence supports payload beginning before the old legacy body offset | `PayloadPrefixBytes`, `GhidraStyleLayoutValid` | Sidecar/report-only |
| Legacy payload offset | Historical parser consumed the body after the older offset | `LegacyPayloadOffset`, `LegacyOffsetMinusPayloadPrefixBytes` | Still preserved for backward compatibility |
| Trailing flag | Ghidra-aligned layout leaves a 1-byte trailer after declared payload | `PayloadTrailerBytes`, `TrailingFlag` | Sidecar/report-only |
| Usage/access metadata | Gamebryo block names encode usage/access variants | `DataStreamUsage`, `DataStreamAccess` | Reported and used for ranking/grouping |
| Semantic adapter ordering | Ghidra semantic adapter path checks stream-element/semantic ordering | Role/grouping reports preserve stream order and semantic grouping | Reported only |

## Current decision

- Keep `NiDataStream` Ghidra evidence as a sidecar until a narrow parser patch has a proof guard.
- Do not switch geometry decode/export consumers from legacy body slicing to Ghidra-aligned slicing in this stage.
- Continue using `nidatastream-layout` and Ghidra target summaries to identify a minimal, guardable parser-field promotion if one becomes necessary.

## Next safe proof questions

1. Do descriptor-helper targets prove a field count/order that the C# parser is currently missing?
2. Can a guard assert that every promoted field interpretation matches copied NIF samples before any exporter uses it?
3. Does any current Ghidra-only mesh candidate become a complete position/normal/UV group after a field interpretation change?

Until those are answered with tests and guards, parser/export behavior remains unchanged.
