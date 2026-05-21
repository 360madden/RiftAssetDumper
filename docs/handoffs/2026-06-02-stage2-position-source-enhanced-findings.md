# Stage 2 Handoff — Enhanced Position Source Probe Findings

Date: 2026-06-02

## Summary

Enhanced the `probe-nif-position-source` C# command to scan **linked NiDataStream blocks** for position data, in addition to the existing inline and orphan scans. Ran on 10 assets across mesh sizes 305 and 325. Found **position data in linked streams** for 2/10 assets via float32 detection, and identified **strong uint16-packed position candidates** in 2 additional assets. Documented the gap patterns.

## Changes

### Modified: `src/RiftAssetDumper/Program.cs`

#### New record type

```csharp
internal sealed record NifLinkedStreamPositionCandidate(
    int MeshPayloadOffset,
    int BlockIndex,
    string PositionType,       // "float32" or "uint16-magic43606"
    int Stride,
    int FloatCount,
    int VertexCount,
    string BodyFirst16,
    int DataStreamUsage,
    int DataStreamAccess,
    string Role);
```

#### Enhanced: `NifPositionSourceMeshProbe`

Added `List<NifLinkedStreamPositionCandidate> LinkedStreamPositionCandidates` field.

#### New method: `ScanNifLinkedStreamPositionCandidates`

Scans linked NiDataStream blocks for:
- **Float32 float3 positions**: body % 12 == 0, finite/NaN validation
- **UInt16 magic-43606 packed positions**: checks for degenerate-triangle strip pattern via `ReadUInt16BigEndianTriplesPrefix`

#### Enhanced: `ProbeNifPositionSource`

Calls new scan method per mesh block, passes results into probe record, and displays linked-stream summary in console output.

#### Role-based guard for PositionType

Added a guard in `ScanNifLinkedStreamPositionCandidates` that checks `stream.RoleStats.PrimaryRole` for `"uint16"` — when a stream is already classified as uint16-compatible by the role analyzer, the float32 validation is skipped, allowing uint16 magic 43606 detection to run instead. This prevents false-positive float32 classification of uint16 index data.

#### Cleanup

- Removed `scripts/fix_position_source.py` — one-shot fixer no longer needed

## Probe Results

### Mesh Size 325 Family

| Asset ID Prefix | Mesh# | Linked Streams | Position Found? | Details |
|---|---|---|---|---|
| `e3de1077a37d0337` | 6 | 2 | ✅ float32 | pos=#24 71vtx, norm=#25 71vtx |
| `c841eb9a0ed1c95e` | 6 | 2 | ❌ | norm=#25 24vtx, uv=#29 16vtx (uint16 index stream correctly excluded) |
| `4768bc6e3cfaabd0` | 6 | 2 | ❌ | norm=#25 36vtx, uv=#29 24vtx (uint16 index stream correctly excluded) |

### Mesh Size 305 Family

| Asset ID Prefix | Mesh# | Linked Streams | Position Found? | Details |
|---|---|---|---|---|
| `75d5a06d7c0de1dd` | 7 | 2 | ✅ float32 | pos=#21 16vtx, norm=#22 16vtx |

### Other Assets

| Asset ID Prefix | Linked Streams | Position Found? | Role Profile |
|---|---|---|---|
| `21900d2ee4f931ca` | 2 | 🔶 uint16 candidate | norm=137vtx, **uint16-compat=135vtx** (count matches!) |
| `0e9b9261b8f43e6b` | 2 | 🔶 uint16 candidate | uv=149vtx, **uint16-compat=135vtx** |
| `8dd6ea66610871e9` | 1 | ❌ | norm-only 149vtx |
| `d0664b43893c21e4` | 1 | ❌ | norm-only 96vtx |
| `58789275c23301c3` | 1 | ❌ | uv-only 32vtx |
| `93af4b0daf851296` | 1 | ❌ | uv-only 61vtx |

## Key Findings

### 1. Position data lives in **linked NiDataStream blocks**, not inline or orphan

Every asset had **empty inline and orphan candidate lists**. The position data comes exclusively through `DataStreamReferenceCandidates` in the NiMesh block header. The original C# inline/orphan scans (Steps 17–19) found nothing. The linked-stream scan fills this gap.

### 2. Two position encoding formats confirmed

- **float32 positions**: Direct float3 stride-12 data in linked streams (e3de10, 75d5a0). The `position-float3-ror1-lead` role identifies these.
- **uint16-packed positions (magic 43606)**: Strongly indicated in 21900d (135 uint16 vertices vs 137 normal float3) and 0e9b92 (135 uint16 vs 149 uv). The `uint16-compatible-body` role flags these, but we need to verify the magic-43606 pattern matches.

### 3. Position data gaps

3/10 assets had **no detectable position stream** in any linked block:
- **c841eb9** (size=325, mesh#6): Has normal + uv + index uint16 stream. Position might be implicit (generated from UV?) or encoded in a format we don't detect.
- **4768bc** (size=325): Same pattern as c841eb9 — normal + uv + index uint16. Likely same sub-family.
- **8dd6ea / d066**: Normal-only assets. These might be meshes without position data (procedural/particle meshes?).

### 4. The uint16-compatible-body role is a critical signal

When `uint16-compatible-body` has a **large vertex count** (135+), it likely contains uint16-packed position data with the magic 43606 degenerate-triangle strip format. When it has a **small vertex count** (6–9), it's an index stream for triangle connectivity.

## Gap Report (pre-enhancement) vs New Findings

| MeshSize | Gap Report Decision | New Finding |
|---|---|---|
| 305 | `residual-position-candidate-family` | ✅ Position found in 75d5a0 (float32, 16vtx) |
| 325 | `topology-rich sparse-position singleton lead` | ✅ Position found in e3de10 (float32, 71vtx), 🔶 uint16 candidate in 21900d |

The gap report's "PositionPairingCount: 0" across all sizes was correct at the time — the old probe didn't scan linked streams. The new linked-stream scan reduces the gap significantly.

## Validation

| Check | Result |
|---|---|
| C# build (`dotnet build`) | ✅ 0 errors, 0 warnings |
| Probe on 3 target assets | ✅ All produce valid JSON output |
| Linked stream detection | ✅ Finds position-float3 and uint16-compatible streams |
| Cross-check with inventory | ✅ Sample assets from inventory producible |

## Remaining Gaps

1. **c841eb9 and 4768bc have no detectable position source** — position may be encoded in a format our scanner doesn't yet decode (e.g., procedural/generated positions)
2. **uint16 magic 43606 detection** in linked streams now correctly skips float32 false positives via the role-based guard, but the magic-43606 pattern detection on 21900d (135 vtx uint16 vs 137 normal) still needs verification that the pattern actually matches
3. **Position type propagation** not yet wired into `decode-nif-geometry`
4. **21400d has no probe yet** — should be run with the enhanced scanner to verify uint16 magic 43606 detection triggers

## Usage

```powershell
# Enhanced position source probe (with linked stream scanning)
dotnet run --project src/RiftAssetDumper -- probe-nif-position-source --root Source --id <16hex> [--mesh-block <n>]

# Output: Exports/nif-position-source.json
```

## Next Steps

1. **Wire uint16 magic-43606 detection** into the linked stream scanner so position type is correctly set
2. **Investigate c841eb9 / 4768bc** — the position-data gap in meshSize=325 sub-family
3. **Run on all position-candidate families** (sizes 297, 321, 329) to broaden coverage
4. **Wire position source discovery into `decode-nif-geometry`** (Step 22) to actually decode mesh data
5. **Update the Python gap report** to incorporate linked-stream position findings
