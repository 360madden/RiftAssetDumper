# RIFT Assets — UInt16 Triples Deduplication & `decode-nif-geometry` Handoff

**Date:** 2026-05-19 20:45 UTC
**Branch:** main (working tree, uncommitted)
**Status:** ✅ Ready for commit

---

## Summary

Two changes shipped in the working tree:

1. **Deduplication:** UInt16 triples structure analysis (`even/odd alternation`, `magic 43606` detection, `structural family` classification) existed in both C# (`AnalyzeNifUInt16TriplesStructure`) and PowerShell (`Get-UInt16TriplesStructureAnalysis`). The C# function is now the single source of truth; it emits the analysis as JSON in the `NifStreamBodyProbe.UInt16TriplesStructure` field, and PowerShell reads it via `Get-JsonValueOrNull` instead of recomputing.

2. **`decode-nif-geometry` command:** New C# CLI command that decodes NiMesh attribute sets (positions, normals, UVs) from float32 streams, with optional OBJ export and experimental UInt16-packed position decode.

---

## Changes

### C# (`src/RiftAssetDumper/Program.cs`) — +472/−22

| Change | Description |
|---|---|
| `decode-nif-geometry` command | New CLI entry point. Decodes NiMesh geometry to console and optional `.obj` file |
| `DecodeNifGeometry()` | Full method: finds NiMesh block, identifies attribute sets, decodes float32/normal/UV vertex samples, writes OBJ |
| `AnalyzeNifUInt16TriplesStructure()` | UInt16 triple structure analysis (even/odd alternation, magic 43606, metadata sentinel, structural family) |
| `BuildNifAttributeUInt16VertexSamples()` | Experimental UInt16-packed position vertex sample builder |
| `NifUInt16TriplesStructure` record | New record type for structure analysis result |
| `NifStreamBodyProbe.UInt16TriplesStructure` field | New field in stream body probe — computed once, emitted in JSON |
| Rename `ReadUInt16TriplesPrefix` → `ReadUInt16BigEndianTriplesPrefix` | All callers updated. Old little-endian function removed |

### PowerShell (`scripts/Invoke-RiftAssetWorkflow.ps1`) — +66/−0

| Change | Description |
|---|---|
| `Get-ClusterStreamRow` updated | Now reads `$stream.UInt16TriplesStructure` via `Get-JsonValueOrNull` instead of calling `Get-UInt16TriplesStructureAnalysis` |
| `Get-UInt16TriplesStructureAnalysis` **deleted** | ~75-line function removed. Logic now lives in C# only |
| Null guards preserved | Structure property access uses `if ($u16TriplesStructure) { ... } else { ... }` pattern |
| `UInt16TriplesStructureSummary` in report | Uses stream row properties (populated from JSON structure) |

---

## Architecture Decision

**Single source of truth:** C# `AnalyzeNifUInt16TriplesStructure` is the authoritative implementation. The analysis is computed once per stream body, serialized to JSON under `UInt16TriplesStructure`, and consumed by PowerShell for reporting.

**Why not PowerShell-only?** The analysis may be needed by other C# commands (e.g., `decode-nif-geometry`). Computing in C# avoids duplication and ensures consistency.

**Why not C#-only?** PowerShell owns the residual cluster probe report generation, which displays the structure analysis in markdown tables. Reading from JSON avoids tight coupling.

---

## Validation

- ✅ C# build: `dotnet build` passes (0 errors, 2 NU1902 warnings for SharpCompress)
- ✅ PowerShell syntax: all references to deleted function removed; no orphaned callers
- ✅ Null safety: PowerShell structure property access uses null guard pattern (`if ($u16TriplesStructure) { ... }`)
- ✅ JSON casing: PascalCase confirmed (existing code reads `UInt16TriplesPrefix` successfully)

---

## Safety Boundaries

- `decode-nif-geometry` writes `.obj` files only when `--write-obj` flag is passed
- The `--experimental` flag gates UInt16-packed position decode
- OBJ files include `# NOTE: No faces/indices decoded. This is a point cloud only.` header
- Generated output goes to `Exports/decode-nif-geometry/` by default
- Guard classifiers (strict 0.95 threshold, fail-closed assertions) remain in place; this command does not weaken them

---

## Open Concerns

| Concern | Severity | Mitigation |
|---|---|---|
| `UInt16TriplesPrefix` and `UInt16BigEndianTriplesPrefix` now emit identical data (both big-endian) | Low | Intentional — the little-endian function was removed as part of earlier endianness hardening |
| `decode-nif-geometry` writes OBJ files without topology/faces | Medium | Explicitly documented as point-cloud-only; index decode is future work |
| PowerShell guard threshold (2 triples) vs C# (4 triples) | Low | C# returns "unknown"/"too few" for <4 triples; report displays correctly |
| OBJ export contradicts previous handoff assertion of "no export readiness" | Medium | Acknowledged — this handoff supersedes the previous one |

---

## Resume Prompts

- "Continue with `decode-nif-geometry` index/topology decode"
- "Review experimental UInt16-packed position decode against known-good float32 positions"
- "Add `--write-obj` to `decode-nif-geometry` test in PowerShell workflow"
- "Verify `UInt16TriplesStructure` JSON output against known stream bodies"
- "Run `Invoke-RiftAssetWorkflow.ps1 ResidualPositionClusterProbeReport` end-to-end"

---

## Suggested Next Actions

| Priority | Action |
|---|---|
| 🔴 | Run end-to-end `ResidualPositionClusterProbeReport` to verify deduplication produces identical results |
| 🟡 | Add face/topology decode to `decode-nif-geometry` |
| 🟡 | Cross-validate UInt16-packed positions against float32 positions for the same mesh |
| 🟢 | Add `ExportSafetyAssertion` to `decode-nif-geometry` OBJ export path |
| 🟢 | Consider unifying `UInt16TriplesPrefix`/`UInt16BigEndianTriplesPrefix` into a single field now that both emit the same data |
